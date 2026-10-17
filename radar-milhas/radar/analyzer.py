"""Transforma as tarifas coletadas em recomendações: melhores viagens em dinheiro, em
milhas, combinadas (ida por um programa e volta por outro), sugestões de datas fora da
janela e um termômetro de preço contra o histórico do próprio radar."""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from .config import Settings
from .models import Analysis, Direction, FareKind, FareQuote, Leg, Trip, Watch, program_label
from .planner import leg_windows
from .valuation import effective_cost_brl, milheiro, value_per_thousand

CATEGORIES = ("cash", "miles", "any")


def _direction(quote: FareQuote, watch: Watch) -> Direction | None:
    if quote.origin in watch.origins and quote.destination in watch.destinations:
        return Direction.OUTBOUND
    if watch.round_trip and quote.origin in watch.destinations and quote.destination in watch.origins:
        return Direction.INBOUND
    return None


def _matches(quote: FareQuote, category: str) -> bool:
    return category == "any" or quote.kind == FareKind(category)


class _Legs:
    """Melhor trecho por (sentido, data, categoria)."""

    def __init__(self, watch: Watch, quotes: list[FareQuote], settings: Settings):
        self.best: dict[tuple[Direction, str], dict[date, Leg]] = {}
        self.all: list[tuple[Direction, Leg]] = []
        for q in quotes:
            direction = _direction(q, watch)
            if direction is None:
                continue
            if watch.max_stops is not None and q.stops > watch.max_stops:
                continue
            leg = Leg(q, effective_cost_brl(q, settings))
            self.all.append((direction, leg))
            for category in CATEGORIES:
                if not _matches(q, category):
                    continue
                by_date = self.best.setdefault((direction, category), {})
                current = by_date.get(q.date)
                if current is None or leg.cost_brl < current.cost_brl:
                    by_date[q.date] = leg

    def get(self, direction: Direction, category: str) -> dict[date, Leg]:
        return self.best.get((direction, category), {})


def _in_window(watch: Watch, out_date: date, in_date: date | None) -> bool:
    last = in_date or out_date
    return out_date >= watch.start_date and last <= watch.end_date


def build_trips(watch: Watch, legs: _Legs, category: str) -> list[Trip]:
    outs = legs.get(Direction.OUTBOUND, category)
    if not watch.round_trip:
        trips = [Trip(leg, None, _in_window(watch, d, None)) for d, leg in outs.items()]
    else:
        ins = legs.get(Direction.INBOUND, category)
        trips = []
        for d1, out_leg in outs.items():
            for nights in range(watch.min_nights, watch.max_nights + 1):
                d2 = d1 + timedelta(days=nights)
                in_leg = ins.get(d2)
                if in_leg is not None:
                    trips.append(Trip(out_leg, in_leg, _in_window(watch, d1, d2)))
    trips.sort(key=lambda t: (t.cost_brl, t.outbound.date))
    return trips


def _diverse(trips: list[Trip], limit: int, spacing_days: int = 1) -> list[Trip]:
    """Evita listar 5 variações quase idênticas (datas vizinhas) da mesma oportunidade."""
    chosen: list[Trip] = []
    for t in trips:
        too_close = False
        for c in chosen:
            same_out = abs((t.outbound.date - c.outbound.date).days) <= spacing_days
            same_in = (t.inbound is None and c.inbound is None) or (
                t.inbound is not None
                and c.inbound is not None
                and abs((t.inbound.date - c.inbound.date).days) <= spacing_days
            )
            if same_out and same_in:
                too_close = True
                break
        if not too_close:
            chosen.append(t)
        if len(chosen) >= limit:
            break
    return chosen


def _calendar(watch: Watch, legs: _Legs) -> list[dict]:
    windows = leg_windows(watch)
    rows: list[dict] = []
    for direction, (lo, hi) in windows.items():
        cash = legs.get(direction, "cash")
        miles = legs.get(direction, "miles")
        for d in sorted(set(cash) | set(miles)):
            c, m = cash.get(d), miles.get(d)
            rows.append(
                {
                    "direction": direction,
                    "date": d,
                    "in_window": lo <= d <= hi,
                    "cash": c,
                    "miles": m,
                    "best_cost": min(x.cost_brl for x in (c, m) if x is not None),
                }
            )
    return rows


def _miles_value(legs: _Legs, settings: Settings) -> list[dict]:
    """Compara, na mesma rota e data, a tarifa em dinheiro com a emissão em milhas."""
    cheapest_cash: dict[tuple[str, str, date], float] = {}
    for _, leg in legs.all:
        q = leg.quote
        if q.kind == FareKind.CASH and q.price_brl:
            key = (q.origin, q.destination, q.date)
            cheapest_cash[key] = min(cheapest_cash.get(key, q.price_brl), q.price_brl)

    best_miles: dict[tuple[str, str, str, date], FareQuote] = {}
    for _, leg in legs.all:
        q = leg.quote
        if q.kind != FareKind.MILES or not q.miles:
            continue
        key = (q.program, q.origin, q.destination, q.date)
        if key not in best_miles or q.miles < best_miles[key].miles:
            best_miles[key] = q

    samples: dict[str, list[float]] = {}
    for (program, origin, destination, d), q in best_miles.items():
        cash = cheapest_cash.get((origin, destination, d))
        if cash is None:
            continue
        value = value_per_thousand(q.miles, q.taxes_brl, cash)
        if value is not None:
            samples.setdefault(program, []).append(value)

    out = []
    for program, values in sorted(samples.items()):
        median = statistics.median(values)
        cost = milheiro(settings, program)
        if median >= cost * 1.3:
            verdict = "Vale muito a pena usar milhas"
        elif median >= cost:
            verdict = "Milhas compensam"
        else:
            verdict = "Melhor pagar em dinheiro"
        out.append(
            {
                "program": program,
                "label": program_label(program),
                "median_value": median,
                "best_value": max(values),
                "your_cost": cost,
                "samples": len(values),
                "verdict": verdict,
            }
        )
    return out


def _trend(current: float | None, previous: list[float]) -> dict | None:
    if current is None:
        return None
    previous = [p for p in previous if p]
    if not previous:
        return {"current": current, "median": None, "pct": None, "is_record": False}
    median = statistics.median(previous[:30])
    return {
        "current": current,
        "median": median,
        "pct": (current - median) / median,
        "is_record": current < min(previous),
    }


def analyze(
    watch: Watch,
    quotes: list[FareQuote],
    settings: Settings,
    history: list[dict] | None = None,
    top_n: int = 5,
) -> Analysis:
    legs = _Legs(watch, quotes, settings)
    analysis = Analysis(watch=watch, n_quotes=len(quotes))

    trips = {c: build_trips(watch, legs, c) for c in CATEGORIES}
    in_window = {c: [t for t in trips[c] if t.in_window] for c in CATEGORIES}
    analysis.best_cash = _diverse(in_window["cash"], top_n)
    analysis.best_miles = _diverse(in_window["miles"], top_n)
    analysis.best_overall = _diverse(in_window["any"], top_n)
    if in_window["miles"]:
        analysis.fewest_miles = min(in_window["miles"], key=lambda t: (t.total_miles, t.cost_brl))

    reference = in_window["any"][0].cost_brl if in_window["any"] else None
    candidates = []
    for t in trips["any"]:
        if t.in_window:
            continue
        if reference is not None:
            saving = (reference - t.cost_brl) / reference
            if saving < settings.suggestion_min_saving:
                continue
            t.saving_vs_window = saving
        candidates.append(t)
    analysis.suggestions = _diverse(candidates, top_n, spacing_days=2)

    analysis.calendar = _calendar(watch, legs)
    analysis.miles_value = _miles_value(legs, settings)

    history = history or []
    analysis.trend = {
        "cash": _trend(_first_cost(analysis.best_cash), [h["best_cash_brl"] for h in history]),
        "miles": _trend(_first_cost(analysis.best_miles), [h["best_miles_brl"] for h in history]),
        "overall": _trend(_first_cost(analysis.best_overall), [h["best_overall_brl"] for h in history]),
    }
    return analysis


def _first_cost(trips: list[Trip]) -> float | None:
    return trips[0].cost_brl if trips else None
