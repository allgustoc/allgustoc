"""Alertas de preço baixo: dispara quando uma meta é atingida ou o preço despenca,
sem repetir o mesmo aviso todo dia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import Settings
from .models import Analysis, Trip

# Um alerta da mesma regra só se repete se o preço cair mais 3% ou após 7 dias.
REALERT_DROP = 0.03
REALERT_AFTER = timedelta(days=7)

RULE_LABELS = {
    "meta_dinheiro": "Meta em dinheiro atingida",
    "meta_milhas": "Meta em milhas atingida",
    "recorde": "Menor preço já visto",
    "queda": "Preço caiu",
    "sugestao": "Data fora do radar bem mais barata",
}


def _num(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


@dataclass
class Alert:
    rule: str
    value: float  # R$ por pessoa, ou milhas por pessoa em "meta_milhas"
    trip: Trip
    detail: str

    @property
    def title(self) -> str:
        return RULE_LABELS[self.rule]


def evaluate(analysis: Analysis, settings: Settings) -> list[Alert]:
    """Condições de alerta presentes agora (sem considerar o que já foi avisado)."""
    w = analysis.watch
    alerts: list[Alert] = []
    if w.target_cash_brl and analysis.best_cash:
        trip = analysis.best_cash[0]
        if trip.cost_brl <= w.target_cash_brl:
            alerts.append(Alert("meta_dinheiro", trip.cost_brl, trip,
                                f"R$ {_num(trip.cost_brl)} por pessoa (sua meta: R$ {_num(w.target_cash_brl)})"))
    trip = analysis.fewest_miles
    if w.target_miles and trip and trip.total_miles <= w.target_miles:
        alerts.append(Alert("meta_milhas", trip.total_miles, trip,
                            f"{_num(trip.total_miles)} milhas + R$ {_num(trip.cash_out_of_pocket)} por pessoa "
                            f"(sua meta: {_num(w.target_miles)} milhas)"))
    trend = analysis.trend.get("overall")
    if trend and trend["median"] is not None and analysis.best_overall:
        trip = analysis.best_overall[0]
        if trend["is_record"]:
            alerts.append(Alert("recorde", trip.cost_brl, trip,
                                f"R$ {_num(trip.cost_brl)} por pessoa, abaixo de tudo que o radar já viu"))
        elif trend["pct"] <= -settings.deal_threshold:
            alerts.append(Alert("queda", trip.cost_brl, trip,
                                f"R$ {_num(trip.cost_brl)} por pessoa, {abs(trend['pct']):.0%} abaixo da média recente"))
    if analysis.suggestions:
        trip = analysis.suggestions[0]
        alerts.append(Alert("sugestao", trip.cost_brl, trip,
                            f"R$ {_num(trip.cost_brl)} por pessoa, {trip.saving_vs_window or 0:.0%} mais barato "
                            f"que a melhor opção da sua janela"))
    return alerts


def only_new(alerts: list[Alert], last: dict[str, tuple[float, datetime]], now: datetime) -> list[Alert]:
    """Remove alertas já enviados que não melhoraram o suficiente."""
    fresh = []
    for alert in alerts:
        previous = last.get(alert.rule)
        if previous is None:
            fresh.append(alert)
            continue
        value, sent_at = previous
        if alert.value <= value * (1 - REALERT_DROP) or now - sent_at >= REALERT_AFTER:
            fresh.append(alert)
    return fresh
