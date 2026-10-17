"""Tarifas em dinheiro via Google Flights (SerpApi: https://serpapi.com/google-flights-api).

Cobre TAP, LATAM, Azul, Iberia, Air Europa etc. com preço em BRL. É a fonte de
dinheiro mais estável, já que usa uma API oficial e paga (há plano gratuito).
"""

from __future__ import annotations

from datetime import date

import httpx

from ..models import FareKind, FareQuote
from .base import Provider, ProviderBlocked, ProviderError, hhmm, to_float

ENDPOINT = "https://serpapi.com/search.json"
TRAVEL_CLASS = {"economy": 1, "premium": 2, "business": 3, "first": 4}


def parse_google_flights(payload: dict, origin: str, destination: str, day: date, cabin: str) -> list[FareQuote]:
    url = (payload.get("search_metadata") or {}).get("google_flights_url", "")
    quotes: list[FareQuote] = []
    for option in (payload.get("best_flights") or []) + (payload.get("other_flights") or []):
        price = to_float(option.get("price"))
        segments = option.get("flights") or []
        if not price or not segments:
            continue
        airlines: list[str] = []
        for seg in segments:
            name = seg.get("airline")
            if name and name not in airlines:
                airlines.append(name)
        quotes.append(
            FareQuote(
                provider="serpapi",
                program="cash",
                kind=FareKind.CASH,
                origin=origin,
                destination=destination,
                date=day,
                price_brl=price,
                airline=" + ".join(airlines),
                stops=max(0, len(segments) - 1),
                duration_min=option.get("total_duration"),
                flight_numbers=", ".join(s.get("flight_number", "") for s in segments if s.get("flight_number")),
                cabin=cabin,
                departure_time=hhmm((segments[0].get("departure_airport") or {}).get("time")),
                arrival_time=hhmm((segments[-1].get("arrival_airport") or {}).get("time")),
                booking_url=url,
            )
        )
    return quotes


class SerpApiGoogleFlights(Provider):
    key = "serpapi"
    label = "Google Flights (SerpApi)"
    delay_factor = 0.25

    def __init__(self, settings, client: httpx.AsyncClient | None = None):
        super().__init__(settings)
        if not settings.serpapi_key:
            raise ProviderError("Defina SERPAPI_KEY para usar a fonte 'serpapi'", transient=False)
        self.client = client or httpx.AsyncClient(timeout=60)

    async def search(self, origin, destination, day, adults, cabin):
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": day.isoformat(),
            "type": 2,  # só ida: idas e voltas são combinadas pelo analisador
            "adults": adults,
            "travel_class": TRAVEL_CLASS.get(cabin, 1),
            "currency": "BRL",
            "hl": "pt-BR",
            "gl": "br",
            "api_key": self.settings.serpapi_key,
        }
        try:
            resp = await self.client.get(ENDPOINT, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"SerpApi: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ProviderBlocked(f"SerpApi recusou a chave (HTTP {resp.status_code})")
        if resp.status_code == 429:
            raise ProviderBlocked("SerpApi: limite de buscas do plano atingido")
        payload = resp.json()
        self.dump(f"{origin}{destination}{day}", payload)
        error = payload.get("error")
        if error:
            if "no results" in error.lower() or "hasn't returned any results" in error.lower():
                return []
            raise ProviderError(f"SerpApi: {error}")
        quotes = parse_google_flights(payload, origin, destination, day, cabin)
        # O preço do Google Flights é o total para todos os passageiros.
        for q in quotes:
            q.price_brl = round(q.price_brl / adults, 2)
        return quotes

    async def close(self):
        await self.client.aclose()
