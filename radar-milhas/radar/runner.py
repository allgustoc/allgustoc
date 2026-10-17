"""Executa as buscas de um radar em todas as fontes, salva as tarifas e gera a análise."""

from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .analyzer import analyze
from .config import Settings
from .db import Database
from .models import Analysis, FareQuote, SearchTask, Watch
from .planner import build_tasks, prioritize
from .providers import Provider, ProviderBlocked, ProviderError, create_providers

log = logging.getLogger(__name__)

MAX_CONSECUTIVE_ERRORS = 5
RETRIES = 2


@dataclass
class ProviderStats:
    provider: str
    planned: int = 0
    searches: int = 0
    quotes: int = 0
    errors: int = 0
    stopped: str = ""
    messages: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    watch: Watch
    analysis: Analysis
    stats: list[ProviderStats]

    @property
    def n_searches(self) -> int:
        return sum(s.searches for s in self.stats)

    @property
    def n_quotes(self) -> int:
        return sum(s.quotes for s in self.stats)

    @property
    def n_errors(self) -> int:
        return sum(s.errors for s in self.stats)


async def _pause(settings: Settings, provider: Provider) -> None:
    delay = settings.request_delay * provider.delay_factor
    if delay > 0:
        await asyncio.sleep(delay * random.uniform(0.7, 1.3))


async def _with_retries(coro_factory, settings: Settings):
    for attempt in range(RETRIES + 1):
        try:
            return await coro_factory()
        except ProviderError as exc:
            if not exc.transient or attempt == RETRIES:
                raise
            await asyncio.sleep(min(30.0, settings.request_delay * 2 ** (attempt + 1)))


def _chunks(dates: list[date], max_days: int) -> list[tuple[date, date]]:
    """Agrupa datas ordenadas em intervalos de no máximo `max_days` dias."""
    out: list[tuple[date, date]] = []
    for d in sorted(dates):
        if out and (d - out[-1][0]).days < max_days:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


async def _run_provider(
    provider: Provider, tasks: list[SearchTask], watch: Watch, db: Database, settings: Settings, now: datetime
) -> ProviderStats:
    stats = ProviderStats(provider.key)
    last = db.last_searched(provider.key, watch.adults, watch.cabin)
    budget = settings.max_searches_per_provider
    consecutive_errors = 0

    def record(origin, destination, day, status, quotes=None, error=None):
        db.record_search(provider.key, origin, destination, day, watch.adults, watch.cabin, status, quotes, error)

    if provider.supports_range:
        due = prioritize(tasks, last, now, None, settings.refresh_hours)
        by_route: dict[tuple[str, str], list[date]] = defaultdict(list)
        for t in due:
            by_route[(t.origin, t.destination)].append(t.date)
        calls = [(o, d, s, e) for (o, d), dates in by_route.items() for s, e in _chunks(dates, provider.max_range_days)]
        stats.planned = len(calls)
        for origin, destination, start, end in calls[:budget]:
            try:
                quotes = await _with_retries(
                    lambda: provider.search_range(origin, destination, start, end, watch.adults, watch.cabin), settings
                )
            except ProviderError as exc:
                stats.errors += 1
                stats.messages.append(f"{origin}→{destination} {start}..{end}: {exc}")
                if isinstance(exc, ProviderBlocked) or not exc.transient:
                    stats.stopped = str(exc)
                    break
                continue
            per_day: dict[date, list[FareQuote]] = defaultdict(list)
            for q in quotes:
                if q.origin == origin and q.destination == destination:
                    per_day[q.date].append(q)
            day = start
            while day <= end:
                found = per_day.get(day, [])
                record(origin, destination, day, "ok" if found else "empty", found)
                stats.searches += 1
                stats.quotes += len(found)
                day += timedelta(days=1)
            await _pause(settings, provider)
        return stats

    due = prioritize(tasks, last, now, budget, settings.refresh_hours)
    stats.planned = len(due)
    for t in due:
        try:
            quotes = await _with_retries(
                lambda: provider.search(t.origin, t.destination, t.date, watch.adults, watch.cabin), settings
            )
        except ProviderBlocked as exc:
            stats.errors += 1
            stats.stopped = str(exc)
            record(t.origin, t.destination, t.date, "blocked", error=str(exc))
            break
        except ProviderError as exc:
            stats.errors += 1
            consecutive_errors += 1
            stats.messages.append(f"{t.origin}→{t.destination} {t.date}: {exc}")
            record(t.origin, t.destination, t.date, "error", error=str(exc))
            if not exc.transient or consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                stats.stopped = str(exc)
                break
            await _pause(settings, provider)
            continue
        consecutive_errors = 0
        record(t.origin, t.destination, t.date, "ok" if quotes else "empty", quotes)
        stats.searches += 1
        stats.quotes += len(quotes)
        await _pause(settings, provider)
    return stats


def analyze_watch(watch: Watch, db: Database, settings: Settings, now: datetime | None = None) -> Analysis:
    airports = watch.origins + watch.destinations
    explore = timedelta(days=watch.explore_days)
    quotes = db.current_quotes(
        airports, airports, watch.start_date - explore, watch.end_date + explore,
        watch.adults, watch.cabin, settings.stale_days, now=now,
    )
    return analyze(watch, quotes, settings, history=db.run_history(watch.id))


async def run_watch(
    watch: Watch,
    db: Database,
    settings: Settings,
    providers: list[Provider],
    today: date | None = None,
    now: datetime | None = None,
) -> RunResult:
    now = now or datetime.now()
    today = today or now.date()
    run_id = db.start_run(watch.id)
    tasks = build_tasks(watch, today, settings.explore_step_days)
    results = await asyncio.gather(
        *(_run_provider(p, tasks, watch, db, settings, now) for p in providers), return_exceptions=True
    )
    stats: list[ProviderStats] = []
    for provider, res in zip(providers, results):
        if isinstance(res, BaseException):
            log.exception("Falha inesperada na fonte %s", provider.key, exc_info=res)
            res = ProviderStats(provider.key, errors=1, stopped=f"erro inesperado: {res}")
        stats.append(res)
        if res.stopped:
            log.warning("[%s] fonte interrompida: %s", provider.key, res.stopped)

    analysis = analyze_watch(watch, db, settings)

    def best(trips):
        return round(trips[0].cost_brl, 2) if trips else None

    db.finish_run(
        run_id,
        n_searches=sum(s.searches for s in stats),
        n_quotes=sum(s.quotes for s in stats),
        n_errors=sum(s.errors for s in stats),
        best_cash_brl=best(analysis.best_cash),
        best_miles_brl=best(analysis.best_miles),
        best_overall_brl=best(analysis.best_overall),
        log=[s.__dict__ for s in stats],
    )
    return RunResult(watch, analysis, stats)


async def run_all(
    db: Database, settings: Settings, watch_ids: list[int] | None = None, notify: bool = True
) -> list[RunResult]:
    from .notifier import notify_results

    watches = [w for w in db.list_watches(only_active=watch_ids is None) if watch_ids is None or w.id in watch_ids]
    if not watches:
        log.info("Nenhum radar ativo")
        return []
    providers = create_providers(settings)
    if not providers:
        log.error("Nenhuma fonte disponível. Confira RADAR_PROVIDERS e as chaves de API.")
        return []
    results = []
    try:
        for watch in watches:
            log.info("Rodando radar #%s (%s)", watch.id, watch.name)
            result = await run_watch(watch, db, settings, providers)
            log.info(
                "Radar #%s: %d buscas, %d tarifas, %d erros", watch.id, result.n_searches, result.n_quotes, result.n_errors
            )
            results.append(result)
    finally:
        for p in providers:
            try:
                await p.close()
            except Exception:  # pragma: no cover - limpeza
                log.debug("Erro ao fechar %s", p.key, exc_info=True)
    if notify:
        await notify_results(results, settings)
    return results
