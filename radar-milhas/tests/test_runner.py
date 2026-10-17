import asyncio
from datetime import date, datetime

from radar.models import FareKind, FareQuote
from radar.notifier import format_digest
from radar.providers.base import Provider, ProviderBlocked
from radar.providers.demo import DemoProvider
from radar.runner import analyze_watch, run_watch


class FlakyProvider(Provider):
    key = "flaky"
    delay_factor = 0.0

    def __init__(self, settings, block_after=3):
        super().__init__(settings)
        self.calls = 0
        self.block_after = block_after

    async def search(self, origin, destination, day, adults, cabin):
        self.calls += 1
        if self.calls > self.block_after:
            raise ProviderBlocked("captcha")
        return [FareQuote(provider=self.key, program="cash", kind=FareKind.CASH, origin=origin,
                          destination=destination, date=day, price_brl=1000.0 + self.calls)]


def test_run_with_demo_provider_end_to_end(db, settings, watch):
    db.add_watch(watch)
    now = datetime(2026, 10, 17, 7, 0)
    result = asyncio.run(run_watch(watch, db, settings, [DemoProvider(settings)], now=now))
    assert result.n_searches > 0 and result.n_quotes > 0 and result.n_errors == 0
    a = result.analysis
    assert a.best_cash and a.best_miles and a.best_overall
    assert a.best_overall[0].cost_brl <= min(a.best_cash[0].cost_brl, a.best_miles[0].cost_brl)
    assert all(t.in_window for t in a.best_overall)
    text = format_digest(a, settings)
    assert "Melhor em dinheiro" in text and "Melhor em milhas" in text
    history = db.run_history(watch.id)
    assert history[0]["best_overall_brl"] == round(a.best_overall[0].cost_brl, 2)

    # Segunda execução no mesmo dia reaproveita o que está fresco: nenhuma busca nova.
    again = asyncio.run(run_watch(watch, db, settings, [DemoProvider(settings)], now=now))
    assert again.n_searches == 0
    assert again.analysis.best_overall[0].cost_brl == a.best_overall[0].cost_brl


def test_blocked_provider_stops_and_keeps_budget(db, settings, watch):
    settings.max_searches_per_provider = 10
    db.add_watch(watch)
    provider = FlakyProvider(settings, block_after=3)
    result = asyncio.run(run_watch(watch, db, settings, [provider], now=datetime(2026, 10, 17, 7)))
    (stats,) = result.stats
    assert provider.calls == 4 and stats.searches == 3 and stats.stopped == "captcha"


def test_empty_latest_search_invalidates_old_quotes(db, settings, watch):
    db.add_watch(watch)
    day = date(2027, 3, 2)
    q = FareQuote(provider="x", program="cash", kind=FareKind.CASH, origin="GRU", destination="LIS", date=day,
                  price_brl=999)
    db.record_search("x", "GRU", "LIS", day, 1, "economy", "ok", [q], searched_at=datetime(2026, 10, 16, 7))
    now = datetime(2026, 10, 17, 8)
    assert len(db.current_quotes(["GRU"], ["LIS"], day, day, 1, "economy", 4, now=now)) == 1
    db.record_search("x", "GRU", "LIS", day, 1, "economy", "error", error="timeout", searched_at=datetime(2026, 10, 17, 7))
    assert len(db.current_quotes(["GRU"], ["LIS"], day, day, 1, "economy", 4, now=now)) == 1
    db.record_search("x", "GRU", "LIS", day, 1, "economy", "empty", searched_at=datetime(2026, 10, 17, 7, 30))
    assert db.current_quotes(["GRU"], ["LIS"], day, day, 1, "economy", 4, now=now) == []
    assert analyze_watch(watch, db, settings, now=now).is_empty
