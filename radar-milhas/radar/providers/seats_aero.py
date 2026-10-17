"""Disponibilidade de emissões em milhas via seats.aero (Partner API, plano Pro).

Uma única chamada traz várias datas, por isso é a forma mais barata de varrer janelas
grandes. Cada "source" do seats.aero é um programa de milhas (ex.: smiles, azul,
aeroplan, flyingblue). LATAM Pass não é coberto por ela; use a fonte 'latam'.
"""

from __future__ import annotations

from datetime import date

import httpx

from ..models import FareKind, FareQuote
from .base import CABIN_CODES, Provider, ProviderBlocked, ProviderError, to_float, to_int

ENDPOINT = "https://seats.aero/partnerapi/search"
SOURCE_TO_PROGRAM = {"smiles": "smiles", "azul": "azul", "latam": "latampass"}
BOOKING_URLS = {
    "smiles": "https://www.smiles.com.br/home",
    "azul": "https://www.voeazul.com.br/br/pt/programa-fidelidade",
}


def parse_seats_aero(payload: dict, cabin: str, fx: dict[str, float]) -> list[FareQuote]:
    prefix = CABIN_CODES.get(cabin, "Y")
    quotes: list[FareQuote] = []
    for item in payload.get("data") or []:
        if not item.get(f"{prefix}Available"):
            continue
        miles = to_int(item.get(f"{prefix}MileageCost"))
        if not miles:
            continue
        route = item.get("Route") or {}
        source = (route.get("Source") or item.get("Source") or "").lower()
        program = SOURCE_TO_PROGRAM.get(source, source)
        currency = (item.get("TaxesCurrency") or "BRL").upper()
        raw_taxes = to_float(item.get(f"{prefix}TotalTaxes"))
        taxes_brl, estimated = 0.0, True
        if raw_taxes is not None and currency in fx:
            # O seats.aero informa as taxas em centavos da moeda.
            taxes_brl, estimated = raw_taxes / 100.0 * fx[currency], False
        quotes.append(
            FareQuote(
                provider="seats_aero",
                program=program,
                kind=FareKind.MILES,
                origin=route.get("OriginAirport", ""),
                destination=route.get("DestinationAirport", ""),
                date=date.fromisoformat(item["Date"][:10]),
                miles=miles,
                taxes_brl=round(taxes_brl, 2),
                taxes_estimated=estimated,
                airline=item.get(f"{prefix}Airlines") or "",
                stops=0 if item.get(f"{prefix}Direct") else 1,
                cabin=cabin,
                seats=to_int(item.get(f"{prefix}RemainingSeats")) or None,
                booking_url=BOOKING_URLS.get(source, "https://seats.aero/search"),
            )
        )
    return quotes


class SeatsAeroProvider(Provider):
    key = "seats_aero"
    label = "seats.aero"
    supports_range = True
    max_range_days = 60
    delay_factor = 0.25

    def __init__(self, settings, client: httpx.AsyncClient | None = None):
        super().__init__(settings)
        if not settings.seats_aero_key:
            raise ProviderError("Defina SEATS_AERO_KEY para usar a fonte 'seats_aero'", transient=False)
        self.client = client or httpx.AsyncClient(
            timeout=60, headers={"Partner-Authorization": settings.seats_aero_key, "accept": "application/json"}
        )

    async def search(self, origin, destination, day, adults, cabin):
        return await self.search_range(origin, destination, day, day, adults, cabin)

    async def search_range(self, origin, destination, start, end, adults, cabin):
        params = {
            "origin_airport": origin,
            "destination_airport": destination,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "take": 500,
        }
        if self.settings.seats_aero_sources:
            params["sources"] = self.settings.seats_aero_sources
        quotes: list[FareQuote] = []
        fetched = 0
        for _ in range(10):  # paginação
            try:
                resp = await self.client.get(ENDPOINT, params=params)
            except httpx.HTTPError as exc:
                raise ProviderError(f"seats.aero: {exc}") from exc
            if resp.status_code in (401, 403):
                raise ProviderBlocked(f"seats.aero recusou a chave (HTTP {resp.status_code})")
            if resp.status_code == 429:
                raise ProviderBlocked("seats.aero: limite diário de chamadas atingido")
            if resp.status_code >= 400:
                raise ProviderError(f"seats.aero: HTTP {resp.status_code}")
            payload = resp.json()
            self.dump(f"{origin}{destination}{start}", payload)
            quotes.extend(parse_seats_aero(payload, cabin, self.settings.fx))
            fetched += len(payload.get("data") or [])
            if not payload.get("hasMore") or not payload.get("cursor"):
                break
            params["cursor"] = payload["cursor"]
            params["skip"] = fetched
        seats_needed = adults
        return [q for q in quotes if q.seats is None or q.seats >= seats_needed]

    async def close(self):
        await self.client.aclose()
