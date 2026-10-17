"""Azul: a página de seleção de voo aceita moeda em pontos (cc=PTS, Azul Fidelidade)
ou em reais (cc=BRL). Conector experimental: o formato da resposta da Azul muda com
frequência; rode `radar probe azul ...` com RADAR_DEBUG_DUMP_DIR para validar."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from ..models import FareKind, FareQuote
from .base import Provider, ProviderBlocked, ProviderError, hhmm, to_int
from .browser import BrowserSession, find_number, walk

SEARCH_PAGE = "https://www.voeazul.com.br/br/pt/home/selecao-voo"
POINT_KEYS = ("points", "pointsAmount", "totalPoints", "miles")
CASH_KEYS = ("totalAmount", "fareAmount", "price", "amount")
TAX_KEYS = ("taxes", "totalTaxes", "boardingTax", "taxAmount")


def search_url(origin: str, destination: str, day: date, adults: int, points: bool) -> str:
    params = {
        "c[0].ds": origin, "c[0].std": day.strftime("%m/%d/%Y"), "c[0].as": destination,
        "p[0].t": "ADT", "p[0].c": adults, "p[0].cp": "false", "f.dl": 0, "f.dr": 0,
        "cc": "PTS" if points else "BRL",
    }
    return f"{SEARCH_PAGE}?{urlencode(params)}"


def _journeys(payload) -> list[tuple[dict, dict]]:
    """Encontra blocos de voo no estilo Navitaire: {'identifier': {...}, 'fares': [...]}."""
    found = []
    for node in walk(payload):
        ident = node.get("identifier")
        if isinstance(ident, dict) and ident.get("departureStation") and ident.get("arrivalStation"):
            found.append((node, ident))
    return found


def parse_azul(payload, day: date, cabin: str, points: bool, tax_estimate: float, url: str = "") -> list[FareQuote]:
    quotes: list[FareQuote] = []
    for journey, ident in _journeys(payload):
        values = []
        for fare in journey.get("fares") or []:
            amount = find_number(fare, POINT_KEYS if points else CASH_KEYS)
            if amount:
                values.append((amount, fare))
        if not values:
            continue
        amount, fare = min(values, key=lambda v: v[0])
        segments = journey.get("segments") or []
        stops = to_int(journey.get("stops"))
        if stops is None:
            stops = max(0, len(segments) - 1) if segments else to_int((ident.get("connections") or {}).get("count")) or 0
        quote = FareQuote(
            provider="azul",
            program="azul" if points else "cash",
            kind=FareKind.MILES if points else FareKind.CASH,
            origin=ident["departureStation"],
            destination=ident["arrivalStation"],
            date=day,
            airline="Azul",
            stops=stops,
            flight_numbers=f"{ident.get('carrierCode', 'AD')}{ident.get('flightNumber', '')}".strip(),
            cabin=cabin,
            departure_time=hhmm(ident.get("std")),
            arrival_time=hhmm(ident.get("sta")),
            booking_url=url,
        )
        if points:
            quote.miles = int(amount)
            taxes = find_number(fare, TAX_KEYS)
            if taxes is None:
                quote.taxes_brl, quote.taxes_estimated = tax_estimate, True
            else:
                quote.taxes_brl = taxes
        else:
            quote.price_brl = amount
        quotes.append(quote)
    return quotes


class AzulProvider(Provider):
    key = "azul"
    label = "Azul / Azul Fidelidade"
    delay_factor = 1.5

    def __init__(self, settings, session: BrowserSession | None = None, modes: tuple[bool, ...] = (True, False)):
        super().__init__(settings)
        self.session = session or BrowserSession(settings, "azul")
        self.modes = modes  # True = pontos, False = reais

    async def search(self, origin, destination, day, adults, cabin):
        if cabin not in ("economy", "business"):
            cabin = "economy"
        quotes: list[FareQuote] = []
        errors: list[str] = []
        for points in self.modes:
            url = search_url(origin, destination, day, adults, points)
            try:
                captured = await self.session.capture(url, lambda u: "voeazul" in u and "availability" in u.lower())
            except ProviderBlocked:
                raise
            except ProviderError as exc:
                errors.append(str(exc))
                continue
            payload = captured[-1].body
            self.dump(f"{origin}{destination}{day}-{'pts' if points else 'brl'}", payload)
            parsed = parse_azul(payload, day, cabin, points, self.settings.tax_estimate_brl, url)
            quotes.extend(q for q in parsed if q.origin == origin and q.destination == destination)
        if errors and len(errors) == len(self.modes):
            raise ProviderError("; ".join(errors))
        return quotes

    async def close(self):
        await self.session.close()
