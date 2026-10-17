"""Smiles (GOL): emissões em milhas na GOL e parceiras (Air France/KLM, TAP, Iberia...)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode

from ..models import FareKind, FareQuote
from .base import Provider, ProviderError, hhmm, to_int
from .browser import BrowserSession, find_number

SEARCH_PAGE = "https://www.smiles.com.br/mfe/emissao-passagem/"
TAX_ENDPOINT = "https://api-airlines-boarding-tax-prd.smiles.com.br/v1/airlines/flight/boardingtax"
CABIN = {"economy": "ECONOMIC", "premium": "ECONOMIC", "business": "BUSINESS", "first": "BUSINESS"}
BRT = timezone(timedelta(hours=-3))
# Quantos voos mais baratos por data têm a taxa de embarque consultada de verdade.
TAX_LOOKUPS_PER_SEARCH = 2


def search_url(origin: str, destination: str, day: date, adults: int, cabin: str) -> str:
    epoch_ms = int(datetime.combine(day, time(12, 0), BRT).timestamp() * 1000)
    params = {
        "adults": adults, "cabin": CABIN.get(cabin, "ALL"), "children": 0, "departureDate": epoch_ms,
        "destination": destination, "infants": 0, "isElegible": "false", "isFlexibleDateChecked": "false",
        "returnDate": "", "searchType": "g3", "segments": 1, "tripType": 2, "originAirport": origin,
        "originCity": "", "originCountry": "", "originAirportIsAny": "false", "destinCity": "",
        "destinCountry": "", "destinAirportIsAny": "false", "novo-resultado-voos": "true",
    }
    return f"{SEARCH_PAGE}?{urlencode(params)}"


def _duration(flight: dict) -> int | None:
    d = flight.get("duration")
    if isinstance(d, dict):
        return (to_int(d.get("hours")) or 0) * 60 + (to_int(d.get("minutes")) or 0) or None
    return to_int(flight.get("durationNumber"))


def parse_smiles(payload: dict, day: date, cabin: str, club: bool, url: str = "") -> list[tuple[FareQuote, dict]]:
    """Devolve (tarifa, ids) — os ids permitem consultar a taxa de embarque depois."""
    out: list[tuple[FareQuote, dict]] = []
    for segment in payload.get("requestedFlightSegmentList") or []:
        for flight in segment.get("flightList") or []:
            fares = [
                f for f in flight.get("fareList") or []
                if to_int(f.get("miles")) and not (f.get("money") or 0) and "MONEY" not in str(f.get("type", "")).upper()
            ]
            # Tarifa "Clube Smiles" só vale para assinantes (RADAR_SMILES_CLUB=true).
            eligible = [f for f in fares if club or "CLUB" not in str(f.get("type", "")).upper()]
            if not eligible:
                continue
            fare = min(eligible, key=lambda f: to_int(f["miles"]))
            dep, arr = flight.get("departure") or {}, flight.get("arrival") or {}
            legs = flight.get("legList") or []
            numbers = [
                f"{(leg.get('marketingAirline') or {}).get('code', '')}{leg.get('flightNumber', '')}"
                for leg in legs if leg.get("flightNumber")
            ]
            quote = FareQuote(
                provider="smiles",
                program="smiles",
                kind=FareKind.MILES,
                origin=(dep.get("airport") or {}).get("code", ""),
                destination=(arr.get("airport") or {}).get("code", ""),
                date=day,
                miles=to_int(fare["miles"]),
                airline=(flight.get("airline") or {}).get("name", ""),
                stops=to_int(flight.get("stops")) or 0,
                duration_min=_duration(flight),
                flight_numbers=", ".join(numbers),
                cabin=cabin,
                departure_time=hhmm(dep.get("date")),
                arrival_time=hhmm(arr.get("date")),
                seats=to_int(flight.get("availableSeats")),
                booking_url=url,
            )
            ids = {"uid": flight.get("uid"), "fare_uid": fare.get("uid"), "fare_type": fare.get("type"),
                   "segment": segment.get("type", "SEGMENT_1")}
            out.append((quote, ids))
    return out


class SmilesProvider(Provider):
    key = "smiles"
    label = "Smiles"
    delay_factor = 1.5

    def __init__(self, settings, session: BrowserSession | None = None):
        super().__init__(settings)
        self.session = session or BrowserSession(settings, "smiles")

    async def search(self, origin, destination, day, adults, cabin):
        url = search_url(origin, destination, day, adults, cabin)
        captured = await self.session.capture(url, lambda u: "/airlines/search" in u and "smiles" in u)
        payload = captured[-1].body
        self.dump(f"{origin}{destination}{day}", payload)
        if not isinstance(payload, dict) or "requestedFlightSegmentList" not in payload:
            raise ProviderError("Smiles: formato de resposta inesperado (veja RADAR_DEBUG_DUMP_DIR)", transient=False)
        parsed = parse_smiles(payload, day, cabin, self.settings.smiles_club, url)
        for q, _ in parsed:
            q.origin, q.destination = q.origin or origin, q.destination or destination
        parsed = [(q, ids) for q, ids in parsed if q.origin == origin and q.destination == destination]
        parsed.sort(key=lambda p: p[0].miles)
        headers = captured[-1].request_headers
        for i, (quote, ids) in enumerate(parsed):
            taxes = None
            if i < TAX_LOOKUPS_PER_SEARCH and ids.get("uid") and ids.get("fare_uid"):
                taxes = await self._taxes(ids, adults, headers)
            if taxes is None:
                quote.taxes_brl, quote.taxes_estimated = self.settings.tax_estimate_brl, True
            else:
                quote.taxes_brl = taxes
        return [q for q, _ in parsed]

    async def _taxes(self, ids: dict, adults: int, headers: dict) -> float | None:
        params = urlencode({
            "adults": adults, "children": 0, "infants": 0, "fareuid": ids["fare_uid"], "uid": ids["uid"],
            "type": ids.get("segment") or "SEGMENT_1", "highlightText": ids.get("fare_type") or "SMILES",
        })
        try:
            payload = await self.session.get_json(f"{TAX_ENDPOINT}?{params}", headers)
        except ProviderError:
            return None
        self.dump("boardingtax", payload)
        totals = payload.get("totals") if isinstance(payload, dict) else None
        value = find_number(totals or payload, ("money", "totalBoardingTax", "boardingTax"))
        return round(value / adults, 2) if value else None

    async def close(self):
        await self.session.close()
