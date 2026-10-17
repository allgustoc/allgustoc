"""Resumo diário em texto (Telegram, e-mail e console)."""

from __future__ import annotations

import asyncio
import html
import re
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

import httpx

from .airports import country_flag
from .alerts import Alert, evaluate, only_new
from .config import Settings
from .models import Analysis, FareKind, Leg, Trip, program_label

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4000


def brl(value: float | None) -> str:
    if value is None:
        return "—"
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def miles_fmt(value: int | None) -> str:
    return f"{value or 0:,}".replace(",", ".")


def fmt_date(d) -> str:
    return d.strftime("%d/%m/%y")


def leg_text(leg: Leg) -> str:
    q = leg.quote
    stops = "direto" if q.stops == 0 else f"{q.stops} parada" + ("s" if q.stops > 1 else "")
    hour = f" {q.departure_time}" if q.departure_time else ""
    route = f"{q.origin}→{q.destination}{country_flag(q.destination)}"
    if q.kind == FareKind.CASH:
        price = brl(q.price_brl)
    else:
        tilde = "~" if q.taxes_estimated else ""
        price = f"{miles_fmt(q.miles)} {program_label(q.program)} + {tilde}{brl(q.taxes_brl)}"
    airline = f" · {q.airline}" if q.airline else ""
    return f"{fmt_date(q.date)}{hour} {route} · {price}{airline} · {stops}"


def trip_text(trip: Trip, adults: int) -> list[str]:
    total = brl(trip.cost_brl * adults)
    head = f"<b>{total}</b>"
    if trip.total_miles:
        head += f" (≈ {miles_fmt(trip.total_miles * adults)} milhas + {brl(trip.cash_out_of_pocket * adults)})"
    if trip.nights is not None:
        head += f" · {trip.nights} noites"
    if trip.saving_vs_window:
        head += f" · <b>{trip.saving_vs_window:.0%} mais barato</b> que sua janela"
    lines = [head]
    lines.append("   ida: " + html.escape(leg_text(trip.outbound)))
    if trip.inbound:
        lines.append("   volta: " + html.escape(leg_text(trip.inbound)))
    if trip.open_jaw:
        lines.append(f"   ↔️ chega em {trip.outbound.quote.destination} e volta de {trip.inbound.quote.origin}")
    return lines


def _trend_text(trend: dict | None) -> str:
    if not trend or trend.get("pct") is None:
        return ""
    if trend["is_record"]:
        return " 🔥 menor preço já visto"
    pct = trend["pct"]
    if pct <= -0.10:
        return f" 🔥 {abs(pct):.0%} abaixo da média"
    if pct >= 0.10:
        return f" 📈 {pct:.0%} acima da média"
    return " ➖ estável"


def format_digest(analysis: Analysis, settings: Settings) -> str:
    w = analysis.watch
    people = f" · {w.adults} adultos" if w.adults > 1 else ""
    trip_kind = f"ida e volta, {w.min_nights}–{w.max_nights} noites" if w.round_trip else "só ida"
    lines = [
        f"✈️ <b>{html.escape(w.name)}</b>",
        f"{','.join(w.origins)} → {','.join(w.destinations)} · {fmt_date(w.start_date)} a {fmt_date(w.end_date)}"
        f" · {trip_kind}{people}",
    ]
    if analysis.is_empty:
        lines.append("\nAinda sem tarifas disponíveis na sua janela. O bot segue procurando.")
    sections = (
        ("💵 Melhor em dinheiro", analysis.best_cash, "cash"),
        ("🎯 Melhor em milhas", analysis.best_miles, "miles"),
        ("🏆 Melhor combinação (dinheiro + milhas)", analysis.best_overall, "overall"),
    )
    for title, trips, trend_key in sections:
        if not trips:
            continue
        lines.append(f"\n<b>{title}</b>{_trend_text(analysis.trend.get(trend_key))}")
        for trip in trips[:2]:
            lines.extend(trip_text(trip, w.adults))
    if analysis.miles_value:
        lines.append("\n<b>💡 Vale usar milhas?</b>")
        for mv in analysis.miles_value:
            lines.append(
                f"• {mv['label']}: rendendo {brl(mv['median_value'])}/milheiro "
                f"(seu custo {brl(mv['your_cost'])}) → {mv['verdict']}"
            )
    if analysis.suggestions:
        lines.append("\n<b>📅 Datas fora do seu radar com bom preço</b>")
        for trip in analysis.suggestions[:3]:
            lines.extend(trip_text(trip, w.adults))
    current = evaluate(analysis, settings)
    if current:
        lines.append("\n⚡ " + " · ".join(a.title for a in current))
    if any(t.taxes_estimated for t in analysis.best_miles + analysis.best_overall):
        lines.append("<i>~ taxas estimadas; confirme no site antes de emitir.</i>")
    lines.append("<i>Valores em R$ convertem milhas pelo seu custo do milheiro (RADAR_MILHEIRO).</i>")
    return "\n".join(lines)


def _split(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    parts, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit and current:
            parts.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        parts.append(current)
    return parts


async def send_telegram(text: str, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        for part in _split(text):
            resp = await client.post(
                url,
                json={"chat_id": settings.telegram_chat_id, "text": part, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
            )
            if resp.status_code >= 400:
                log.error("Telegram respondeu %s: %s", resp.status_code, resp.text[:300])
    finally:
        if own:
            await client.aclose()


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def send_email(subject: str, text: str, settings: Settings) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = settings.email_to
    msg.set_content(_strip_html(text))
    msg.add_alternative("<html><body><pre style='font-family:inherit'>" + text + "</pre></body></html>", subtype="html")
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        server.starttls()
    with server:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def format_alerts(analysis: Analysis, alerts: list[Alert]) -> str:
    w = analysis.watch
    lines = [f"🚨 <b>Alerta de preço: {html.escape(w.name)}</b>"]
    for alert in alerts:
        lines.append(f"\n<b>{alert.title}</b>: {html.escape(alert.detail)}")
        lines.extend(trip_text(alert.trip, w.adults))
    links = [l.quote.booking_url for l in alerts[0].trip.legs if l.quote.booking_url]
    if links:
        lines.append(f'\n<a href="{html.escape(links[0])}">Abrir no site</a> · confirme antes de emitir')
    return "\n".join(lines)


async def _deliver(subject: str, text: str, settings: Settings) -> None:
    print(_strip_html(text) + "\n")
    if settings.telegram_token and settings.telegram_chat_id:
        try:
            await send_telegram(text, settings)
        except httpx.HTTPError as exc:
            log.error("Falha ao enviar Telegram: %s", exc)
    if settings.smtp_host and settings.email_to:
        try:
            await asyncio.to_thread(send_email, subject, text, settings)
        except (OSError, smtplib.SMTPException) as exc:
            log.error("Falha ao enviar e-mail: %s", exc)


async def notify_results(results, settings: Settings, db=None) -> None:
    """Envia primeiro os alertas novos (sem repetir os já avisados) e, no modo digest, o resumo do dia."""
    now = datetime.now()
    for result in results:
        analysis = result.analysis
        watch = analysis.watch
        alerts = evaluate(analysis, settings)
        if db is not None:
            alerts = only_new(alerts, db.last_alerts(watch.id), now)
        if alerts:
            await _deliver(f"🚨 Alerta de preço: {watch.name}", format_alerts(analysis, alerts), settings)
            if db is not None:
                for alert in alerts:
                    db.record_alert(watch.id, alert.rule, alert.value, f"{alert.title}: {alert.detail}", now)
        if settings.notify_mode == "deals":
            if not alerts:
                log.info("Radar #%s: nenhum alerta novo", watch.id)
            continue
        text = format_digest(analysis, settings)
        stopped = [s for s in result.stats if s.stopped]
        if stopped:
            text += "\n⚠️ Fontes com problema: " + ", ".join(html.escape(f"{s.provider} ({s.stopped})") for s in stopped)
        await _deliver(f"Radar de passagens: {watch.name}", text, settings)
