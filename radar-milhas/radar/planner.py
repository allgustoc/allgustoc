"""Decide quais (rota, data) consultar em cada execução diária.

- Datas dentro da janela cadastrada são consultadas todo dia (prioridade máxima).
- Datas fora da janela (até `explore_days` antes/depois) são amostradas em rodízio a
  cada `explore_step_days` dias; é daí que saem as sugestões de datas "fora do radar".
- Um orçamento por fonte limita quantas consultas são feitas por execução, e consultas
  feitas há menos de `refresh_hours` (por qualquer radar) são reaproveitadas.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import Direction, SearchTask, Watch

EXPLORATION_SHARE = 0.25


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def leg_windows(watch: Watch) -> dict[Direction, tuple[date, date]]:
    """Faixa de datas de cada trecho que respeita a janela cadastrada."""
    if not watch.round_trip:
        return {Direction.OUTBOUND: (watch.start_date, watch.end_date)}
    return {
        Direction.OUTBOUND: (watch.start_date, watch.end_date - timedelta(days=watch.min_nights)),
        Direction.INBOUND: (watch.start_date + timedelta(days=watch.min_nights), watch.end_date),
    }


def build_tasks(watch: Watch, today: date, explore_step_days: int = 3) -> list[SearchTask]:
    earliest = today + timedelta(days=1)
    step = max(1, explore_step_days)
    offset = today.toordinal() % step
    explore = timedelta(days=watch.explore_days)
    tasks: list[SearchTask] = []
    for direction, (lo, hi) in leg_windows(watch).items():
        if direction == Direction.OUTBOUND:
            routes = [(o, d) for o in watch.origins for d in watch.destinations]
        else:
            routes = [(d, o) for o in watch.origins for d in watch.destinations]
        for day in _daterange(max(earliest, lo - explore), hi + explore):
            in_window = lo <= day <= hi
            if not in_window and (day.toordinal() - offset) % step != 0:
                continue
            for origin, destination in routes:
                tasks.append(SearchTask(origin, destination, day, direction, in_window))
    return tasks


def task_key(task: SearchTask) -> tuple[str, str, date]:
    return (task.origin, task.destination, task.date)


def prioritize(
    tasks: list[SearchTask],
    last_searched: dict[tuple[str, str, date], datetime],
    now: datetime,
    budget: int | None,
    refresh_hours: float,
) -> list[SearchTask]:
    """Filtra o que já está fresco e ordena: nunca consultado > mais antigo > data mais próxima."""
    fresh_cutoff = now - timedelta(hours=refresh_hours)
    seen: set[tuple[str, str, date]] = set()
    due: list[SearchTask] = []
    for t in tasks:
        key = task_key(t)
        if key in seen:
            continue
        seen.add(key)
        last = last_searched.get(key)
        if last is None or last < fresh_cutoff:
            due.append(t)

    def rank(t: SearchTask):
        last = last_searched.get(task_key(t))
        return (last is not None, last or datetime.min, t.date, t.origin, t.destination)

    window = sorted((t for t in due if t.in_window), key=rank)
    outside = sorted((t for t in due if not t.in_window), key=rank)
    if budget is None or len(window) + len(outside) <= budget:
        return window + outside

    reserved = min(len(outside), int(budget * EXPLORATION_SHARE))
    take_window = min(len(window), budget - reserved)
    take_outside = min(len(outside), budget - take_window)
    return window[:take_window] + outside[:take_outside]
