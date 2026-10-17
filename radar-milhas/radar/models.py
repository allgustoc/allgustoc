from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class FareKind(StrEnum):
    CASH = "cash"
    MILES = "miles"


class Direction(StrEnum):
    OUTBOUND = "out"
    INBOUND = "in"


PROGRAM_LABELS = {
    "cash": "Dinheiro",
    "smiles": "Smiles (GOL)",
    "latampass": "LATAM Pass",
    "azul": "Azul Fidelidade",
}

CABINS = ("economy", "premium", "business", "first")


def program_label(program: str) -> str:
    return PROGRAM_LABELS.get(program, program.replace("_", " ").title())


@dataclass
class Watch:
    """Um radar cadastrado: rotas + janela de datas que o bot vigia diariamente."""

    name: str
    origins: list[str]
    destinations: list[str]
    start_date: date
    end_date: date
    round_trip: bool = True
    min_nights: int = 7
    max_nights: int = 21
    adults: int = 1
    cabin: str = "economy"
    max_stops: int | None = None
    target_cash_brl: float | None = None
    target_miles: int | None = None
    explore_days: int = 30
    active: bool = True
    id: int | None = None
    created_at: datetime | None = None

    def validate(self) -> None:
        if not self.origins or not self.destinations:
            raise ValueError("Informe ao menos uma origem e um destino")
        if self.end_date < self.start_date:
            raise ValueError("A data de fim deve ser posterior à data de início")
        if self.round_trip:
            if self.min_nights < 1 or self.max_nights < self.min_nights:
                raise ValueError("Faixa de noites inválida")
            if (self.end_date - self.start_date).days < self.min_nights:
                raise ValueError("A janela é menor que o mínimo de noites")
        if not 1 <= self.adults <= 9:
            raise ValueError("Número de adultos deve estar entre 1 e 9")
        if self.cabin not in CABINS:
            raise ValueError(f"Cabine inválida: {self.cabin}")
        if self.explore_days < 0:
            raise ValueError("Dias de exploração não pode ser negativo")


@dataclass(frozen=True)
class SearchTask:
    origin: str
    destination: str
    date: date
    direction: Direction
    in_window: bool


@dataclass
class FareQuote:
    """Uma tarifa só de ida, por passageiro adulto."""

    provider: str
    program: str  # "cash" ou chave do programa ("smiles", "latampass", "azul", ...)
    kind: FareKind
    origin: str
    destination: str
    date: date
    price_brl: float | None = None  # tarifa total em dinheiro (kind=cash)
    miles: int | None = None  # milhas/pontos (kind=miles)
    taxes_brl: float = 0.0  # taxas de embarque pagas em dinheiro (kind=miles)
    taxes_estimated: bool = False
    airline: str = ""
    stops: int = 0
    duration_min: int | None = None
    flight_numbers: str = ""
    cabin: str = "economy"
    departure_time: str = ""
    arrival_time: str = ""
    booking_url: str = ""
    seats: int | None = None
    observed_at: datetime | None = None
    id: int | None = None

    def route(self) -> str:
        return f"{self.origin}→{self.destination}"


@dataclass
class Leg:
    """Uma tarifa avaliada (custo efetivo em R$ calculado com o valor do milheiro)."""

    quote: FareQuote
    cost_brl: float

    @property
    def date(self) -> date:
        return self.quote.date


@dataclass
class Trip:
    outbound: Leg
    inbound: Leg | None = None
    in_window: bool = True
    saving_vs_window: float | None = None  # fração mais barata que o melhor da janela

    @property
    def cost_brl(self) -> float:
        return self.outbound.cost_brl + (self.inbound.cost_brl if self.inbound else 0.0)

    @property
    def nights(self) -> int | None:
        if not self.inbound:
            return None
        return (self.inbound.date - self.outbound.date).days

    @property
    def open_jaw(self) -> bool:
        """Chega numa cidade e volta de outra (ex.: chega em Lisboa, volta de Madri)."""
        return self.inbound is not None and self.outbound.quote.destination != self.inbound.quote.origin

    @property
    def legs(self) -> list[Leg]:
        return [self.outbound] + ([self.inbound] if self.inbound else [])

    @property
    def total_miles(self) -> int:
        return sum(l.quote.miles or 0 for l in self.legs if l.quote.kind == FareKind.MILES)

    @property
    def cash_out_of_pocket(self) -> float:
        """Quanto sai do bolso em R$ (tarifas em dinheiro + taxas das emissões em milhas)."""
        total = 0.0
        for leg in self.legs:
            q = leg.quote
            total += (q.price_brl or 0.0) if q.kind == FareKind.CASH else q.taxes_brl
        return total

    @property
    def taxes_estimated(self) -> bool:
        return any(l.quote.taxes_estimated for l in self.legs)

    def key(self) -> tuple:
        return (self.outbound.date, self.inbound.date if self.inbound else None)


@dataclass
class Analysis:
    watch: Watch
    best_cash: list[Trip] = field(default_factory=list)
    best_miles: list[Trip] = field(default_factory=list)
    best_overall: list[Trip] = field(default_factory=list)
    suggestions: list[Trip] = field(default_factory=list)
    fewest_miles: Trip | None = None  # viagem na janela com menos milhas
    calendar: list[dict] = field(default_factory=list)
    miles_value: list[dict] = field(default_factory=list)
    trend: dict = field(default_factory=dict)
    n_quotes: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.best_cash or self.best_miles or self.best_overall)
