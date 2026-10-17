"""Agendador diário: roda todos os radares ativos uma vez por dia no horário RADAR_RUN_AT."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import Settings
from .db import Database
from .runner import run_all

log = logging.getLogger(__name__)


def parse_run_times(raw: str) -> list[time]:
    """'07:00' ou '07:00,19:00' (mais de uma varredura por dia)."""
    out = []
    for part in raw.split(","):
        hh, mm = part.strip().split(":")
        out.append(time(int(hh), int(mm)))
    return sorted(out)


def next_run(now: datetime, run_times: list[time]) -> datetime:
    for t in run_times:
        candidate = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if candidate > now:
            return candidate
    first = run_times[0]
    return (now + timedelta(days=1)).replace(hour=first.hour, minute=first.minute, second=0, microsecond=0)


async def scheduler_loop(settings: Settings, db: Database, run_now: bool = False) -> None:
    tz = ZoneInfo(settings.timezone)
    run_times = parse_run_times(settings.run_at)
    if run_now:
        await _safe_run(settings, db)
    while True:
        now = datetime.now(tz)
        target = next_run(now, run_times)
        log.info("Próxima varredura: %s", target.strftime("%d/%m/%Y %H:%M %Z"))
        await asyncio.sleep(max(1.0, (target - now).total_seconds()))
        await _safe_run(settings, db)


async def _safe_run(settings: Settings, db: Database) -> None:
    try:
        await run_all(db, settings)
    except Exception:
        log.exception("Falha na varredura diária; nova tentativa no próximo horário")
