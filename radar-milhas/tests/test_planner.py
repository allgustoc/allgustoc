from datetime import date, datetime, timedelta

from radar.models import Direction
from radar.planner import build_tasks, leg_windows, prioritize


def test_leg_windows_respect_min_nights(watch):
    windows = leg_windows(watch)
    assert windows[Direction.OUTBOUND] == (date(2027, 3, 1), date(2027, 3, 13))
    assert windows[Direction.INBOUND] == (date(2027, 3, 8), date(2027, 3, 20))


def test_build_tasks_window_and_rotating_exploration(watch):
    today = date(2026, 10, 17)
    tasks = build_tasks(watch, today, explore_step_days=3)
    out_window = [t for t in tasks if t.direction == Direction.OUTBOUND and t.in_window]
    assert len(out_window) == 13
    assert all((t.origin, t.destination) == ("GRU", "LIS") for t in out_window)
    assert all((t.origin, t.destination) == ("LIS", "GRU") for t in tasks if t.direction == Direction.INBOUND)
    windows = leg_windows(watch)
    outside = [t for t in tasks if not t.in_window]
    assert outside
    for t in outside:
        lo, hi = windows[t.direction]
        assert t.date < lo or t.date > hi
    # Em 3 dias seguidos o rodízio cobre todas as datas de exploração.
    covered = set()
    for i in range(3):
        covered |= {(t.direction, t.date) for t in build_tasks(watch, today + timedelta(days=i), 3) if not t.in_window}
    lo = date(2027, 3, 1) - timedelta(days=10)
    assert (Direction.OUTBOUND, lo) in covered and (Direction.OUTBOUND, lo + timedelta(days=1)) in covered


def test_build_tasks_skips_past_dates(watch):
    tasks = build_tasks(watch, date(2027, 3, 5), 1)
    assert min(t.date for t in tasks) == date(2027, 3, 6)


def test_prioritize_skips_fresh_and_reserves_exploration(watch):
    now = datetime(2026, 10, 17, 7, 0)
    tasks = build_tasks(watch, now.date(), 1)
    fresh = {(t.origin, t.destination, t.date): now - timedelta(hours=2) for t in tasks[:5]}
    picked = prioritize(tasks, fresh, now, budget=20, refresh_hours=20)
    assert len(picked) == 20
    assert not any((t.origin, t.destination, t.date) in fresh for t in picked)
    assert sum(not t.in_window for t in picked) == 5  # 25% do orçamento para explorar
    assert picked[0].in_window


def test_prioritize_prefers_never_searched_then_oldest(watch):
    now = datetime(2026, 10, 17, 7, 0)
    tasks = [t for t in build_tasks(watch, now.date(), 1) if t.in_window][:3]
    last = {
        (tasks[0].origin, tasks[0].destination, tasks[0].date): now - timedelta(days=1),
        (tasks[1].origin, tasks[1].destination, tasks[1].date): now - timedelta(days=3),
    }
    picked = prioritize(tasks, last, now, budget=None, refresh_hours=20)
    assert picked == [tasks[2], tasks[1], tasks[0]]
