"""Fonte sintética e determinística: permite ver o bot funcionando sem nenhuma credencial.

Os preços seguem sazonalidade plausível (alta em dezembro/janeiro e julho, fim de
semana mais caro) e algumas datas "promocionais", para exercitar as sugestões.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from ..models import FareKind, FareQuote
from .base import Provider

CASH_AIRLINES = [("TP", "TAP Air Portugal"), ("LA", "LATAM"), ("AD", "Azul"), ("IB", "Iberia"), ("UX", "Air Europa")]
PROGRAMS = [("smiles", 1.00), ("latampass", 1.15), ("azul", 1.30)]


def _rand(*parts) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _season(day: date) -> float:
    if (day.month == 12 and day.day >= 15) or (day.month == 1 and day.day <= 10):
        return 1.45
    if day.month == 7:
        return 1.30
    if day.month in (6, 8, 1):
        return 1.12
    return 1.0


class DemoProvider(Provider):
    key = "demo"
    label = "Demonstração"
    supports_range = True
    max_range_days = 400
    delay_factor = 0.0

    async def search(self, origin, destination, day, adults, cabin):
        return self._quotes(origin, destination, day, adults, cabin)

    async def search_range(self, origin, destination, start, end, adults, cabin):
        out: list[FareQuote] = []
        day = start
        while day <= end:
            out.extend(self._quotes(origin, destination, day, adults, cabin))
            day += timedelta(days=1)
        return out

    def _quotes(self, origin: str, destination: str, day: date, adults: int, cabin: str) -> list[FareQuote]:
        route = f"{origin}{destination}"
        cabin_factor = {"economy": 1.0, "premium": 1.7, "business": 3.4, "first": 5.0}.get(cabin, 1.0)
        weekend = 1.08 if day.weekday() in (4, 5, 6) else 1.0
        promo = 0.68 if _rand(route, day, "promo") < 0.06 else 1.0
        base = 2600 * _season(day) * weekend * cabin_factor * (0.85 + 0.35 * _rand(route, day))
        url = f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{destination}%20on%20{day}"
        quotes: list[FareQuote] = []
        for code, name in CASH_AIRLINES:
            r = _rand(route, day, code)
            if r < 0.35:
                continue
            stops = 0 if code in ("TP", "LA", "AD") and r > 0.6 else 1
            quotes.append(
                FareQuote(
                    provider=self.key, program="cash", kind=FareKind.CASH, origin=origin, destination=destination,
                    date=day, price_brl=round(base * promo * (0.9 + 0.3 * r) * (1.0 if stops == 0 else 0.92), 2),
                    airline=name, stops=stops, duration_min=660 + 180 * stops, flight_numbers=f"{code}{1000 + int(r * 8000)}",
                    cabin=cabin, departure_time=f"{18 + int(r * 5):02d}:{int(r * 60) % 60:02d}", booking_url=url,
                )
            )
        for program, factor in PROGRAMS:
            r = _rand(route, day, program)
            if r < 0.25:
                continue
            award_promo = 0.6 if _rand(route, day, program, "award") < 0.08 else 1.0
            miles = int(round(60000 * _season(day) * cabin_factor * factor * award_promo * (0.85 + 0.4 * r), -3))
            quotes.append(
                FareQuote(
                    provider=self.key, program=program, kind=FareKind.MILES, origin=origin, destination=destination,
                    date=day, miles=miles, taxes_brl=round(280 + 400 * r, 2), airline="Parceira",
                    stops=1 if r < 0.5 else 0, duration_min=700, cabin=cabin, seats=max(1, int(r * 9)),
                    booking_url=url,
                )
            )
        return quotes
