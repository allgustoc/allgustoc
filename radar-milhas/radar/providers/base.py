from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..config import Settings
from ..models import FareQuote

log = logging.getLogger(__name__)

CABIN_CODES = {"economy": "Y", "premium": "W", "business": "J", "first": "F"}


class ProviderError(Exception):
    """Falha numa consulta. `transient=True` indica que vale tentar de novo."""

    def __init__(self, message: str, transient: bool = True):
        super().__init__(message)
        self.transient = transient


class ProviderBlocked(ProviderError):
    """A fonte bloqueou o bot (captcha, 403, limite). Paramos essa fonte nesta execução."""

    def __init__(self, message: str):
        super().__init__(message, transient=False)


class Provider(ABC):
    key: str = ""
    label: str = ""
    # Fontes "range" respondem várias datas numa única chamada (ex.: seats.aero).
    supports_range: bool = False
    max_range_days: int = 1
    # Pausa extra entre consultas (multiplica RADAR_REQUEST_DELAY).
    delay_factor: float = 1.0

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    async def search(self, origin: str, destination: str, day: date, adults: int, cabin: str) -> list[FareQuote]:
        """Tarifas só de ida para uma data."""

    async def search_range(
        self, origin: str, destination: str, start: date, end: date, adults: int, cabin: str
    ) -> list[FareQuote]:
        raise NotImplementedError

    async def close(self) -> None:
        return None

    def dump(self, name: str, payload: Any) -> None:
        """Salva a resposta bruta (RADAR_DEBUG_DUMP_DIR) para ajustar os parsers."""
        if not self.settings.debug_dump_dir:
            return
        folder = Path(self.settings.debug_dump_dir)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = folder / f"{self.key}-{name}-{stamp}.json"
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except (TypeError, ValueError):
            path.write_text(str(payload), encoding="utf-8")


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(str(value).replace(",", "."))))
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def hhmm(value: str | None) -> str:
    """'2026-12-01T22:10:00' / '2026-12-01 22:10' -> '22:10'"""
    if not value:
        return ""
    text = str(value).replace("T", " ")
    parts = text.split(" ")
    return parts[1][:5] if len(parts) > 1 else ""
