"""LATAM: a mesma busca do site retorna tarifas em dinheiro (redemption=false) e em
pontos LATAM Pass (redemption=true)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from ..models import FareKind, FareQuote
from .base import Provider, ProviderBlocked, ProviderError, hhmm, to_float, to_int
from .browser import BrowserSession, find_number

SEARCH_PAGE = "https://www.latamairlines.com/br/pt/oferta-voos"
CABIN = {"economy": "Economy", "premium": "Premium Economy", "business": "Business", "first": "Business"}
TAX_KEYS = ("taxes", "taxAmount", "totalTaxes", "amountTaxes", "tax")


def search_url(origin: str, destination: str, day: date, adults: int, cabin: str, redemption: bool) -> str:
    params = {
        "origin": origin, "outbound": f"{day.isoformat()}T12:00:00.000Z", "destination": destination,
        "inbound": "null", "adt": adults, "chd": 0, "inf": 0, "trip": "OW", "cabin": CABIN.get(cabin, "Economy"),
        "redemption": "true" if redemption else "false", "sort": "RECOMMENDED",
    }
    return f"{SEARCH_PAGE}?{urlencode(params)}"


def _flight_numbers(item: dict, summary: dict) -> str:
    numbers = []
    for seg in item.get("itinerary") or []:
        flight = seg.get("flight") or {}
        if flight.get("flightNumber"):
            numbers.append(f"{flight.get('airlineCode', '')}{flight['flightNumber']}")
    return ", ".join(numbers) or str(summary.get("flightCode") or "")


def parse_latam(
    payload: dict, day: date, cabin: str, redemption: bool, tax_estimate: float, url: str = ""
) -> list[FareQuote]:
    quotes: list[FareQuote] = []
    for item in payload.get("content") or []:
        summary = item.get("summary") or {}
        origin, destination = summary.get("origin") or {}, summary.get("destination") or {}
        price = summary.get("lowestPrice") or {}
        if not price and summary.get("brands"):
            price = (summary["brands"][0] or {}).get("price") or {}
        amount = to_float(price.get("amount"))
        if not amount:
            continue
        quote = FareQuote(
            provider="latam",
            program="latampass" if redemption else "cash",
            kind=FareKind.MILES if redemption else FareKind.CASH,
            origin=origin.get("iataCode", ""),
            destination=destination.get("iataCode", ""),
            date=day,
            airline="LATAM",
            stops=to_int(summary.get("stopOvers")) or 0,
            duration_min=to_int(summary.get("duration")),
            flight_numbers=_flight_numbers(item, summary),
            cabin=cabin,
            departure_time=hhmm(origin.get("departure") or origin.get("departureTime")),
            arrival_time=hhmm(destination.get("arrival") or destination.get("arrivalTime")),
            booking_url=url,
        )
        if redemption:
            quote.miles = int(amount)
            taxes = find_number(price, TAX_KEYS) or find_number(summary.get("brands") or [], TAX_KEYS)
            if taxes is None:
                quote.taxes_brl, quote.taxes_estimated = tax_estimate, True
            else:
                quote.taxes_brl = taxes
        else:
            currency = str(price.get("currency") or "BRL").upper()
            if currency not in ("BRL", "R$"):
                continue
            quote.price_brl = amount
        quotes.append(quote)
    return quotes


class LatamProvider(Provider):
    key = "latam"
    label = "LATAM / LATAM Pass"
    delay_factor = 1.5

    def __init__(self, settings, session: BrowserSession | None = None, modes: tuple[bool, ...] = (True, False)):
        super().__init__(settings)
        self.session = session or BrowserSession(settings, "latam")
        self.modes = modes  # True = pontos LATAM Pass, False = dinheiro

    async def search(self, origin, destination, day, adults, cabin):
        quotes: list[FareQuote] = []
        errors: list[ProviderError] = []
        for redemption in self.modes:
            url = search_url(origin, destination, day, adults, cabin, redemption)
            try:
                captured = await self.session.capture(url, lambda u: "/bff/air-offers" in u and "search" in u)
            except ProviderBlocked:
                raise
            except ProviderError as exc:
                errors.append(exc)
                continue
            payload = captured[-1].body
            self.dump(f"{origin}{destination}{day}-{'pts' if redemption else 'brl'}", payload)
            if not isinstance(payload, dict) or "content" not in payload:
                errors.append(ProviderError("formato de resposta inesperado do site (rode radar diagnostico)", transient=False))
                continue
            parsed = parse_latam(payload, day, cabin, redemption, self.settings.tax_estimate_brl, url)
            for q in parsed:
                q.origin, q.destination = q.origin or origin, q.destination or destination
            quotes.extend(q for q in parsed if q.origin == origin and q.destination == destination)
        if errors and len(errors) == len(self.modes):
            # Só vale tentar de novo se todas as falhas forem passageiras.
            transient = all(e.transient for e in errors)
            raise ProviderError("; ".join(dict.fromkeys(str(e) for e in errors)), transient=transient)
        return quotes

    async def close(self):
        await self.session.close()
