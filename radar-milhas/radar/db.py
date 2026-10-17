"""Persistência em SQLite: radares, buscas realizadas, tarifas e histórico de execuções."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import FareKind, FareQuote, Watch

SCHEMA = """
CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    origins TEXT NOT NULL,
    destinations TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    round_trip INTEGER NOT NULL DEFAULT 1,
    min_nights INTEGER NOT NULL DEFAULT 7,
    max_nights INTEGER NOT NULL DEFAULT 21,
    adults INTEGER NOT NULL DEFAULT 1,
    cabin TEXT NOT NULL DEFAULT 'economy',
    max_stops INTEGER,
    target_cash_brl REAL,
    target_miles INTEGER,
    explore_days INTEGER NOT NULL DEFAULT 30,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Uma linha por (fonte, rota, data) consultada. As tarifas válidas de uma rota/data
-- são sempre as da busca mais recente: se a última busca voltou vazia, a rota esgotou.
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    date TEXT NOT NULL,
    adults INTEGER NOT NULL,
    cabin TEXT NOT NULL,
    searched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    n_results INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_searches_key
    ON searches (provider, origin, destination, date, adults, cabin, searched_at);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    program TEXT NOT NULL,
    kind TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    date TEXT NOT NULL,
    price_brl REAL,
    miles INTEGER,
    taxes_brl REAL NOT NULL DEFAULT 0,
    taxes_estimated INTEGER NOT NULL DEFAULT 0,
    airline TEXT,
    stops INTEGER NOT NULL DEFAULT 0,
    duration_min INTEGER,
    flight_numbers TEXT,
    cabin TEXT,
    departure_time TEXT,
    arrival_time TEXT,
    booking_url TEXT,
    seats INTEGER,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_quotes_search ON quotes (search_id);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_id INTEGER NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    n_searches INTEGER NOT NULL DEFAULT 0,
    n_quotes INTEGER NOT NULL DEFAULT 0,
    n_errors INTEGER NOT NULL DEFAULT 0,
    best_cash_brl REAL,
    best_miles_brl REAL,
    best_overall_brl REAL,
    log TEXT
);
CREATE INDEX IF NOT EXISTS ix_runs_watch ON runs (watch_id, started_at);
"""


def _iso(d: date | datetime) -> str:
    return d.isoformat()


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- radares
    def add_watch(self, w: Watch) -> Watch:
        w.validate()
        w.created_at = w.created_at or _now()
        cur = self.conn.execute(
            """INSERT INTO watches (name, origins, destinations, start_date, end_date, round_trip,
               min_nights, max_nights, adults, cabin, max_stops, target_cash_brl, target_miles,
               explore_days, active, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                w.name, ",".join(w.origins), ",".join(w.destinations), _iso(w.start_date), _iso(w.end_date),
                int(w.round_trip), w.min_nights, w.max_nights, w.adults, w.cabin, w.max_stops,
                w.target_cash_brl, w.target_miles, w.explore_days, int(w.active), _iso(w.created_at),
            ),
        )
        self.conn.commit()
        w.id = cur.lastrowid
        return w

    @staticmethod
    def _row_to_watch(r: sqlite3.Row) -> Watch:
        return Watch(
            id=r["id"],
            name=r["name"],
            origins=r["origins"].split(","),
            destinations=r["destinations"].split(","),
            start_date=date.fromisoformat(r["start_date"]),
            end_date=date.fromisoformat(r["end_date"]),
            round_trip=bool(r["round_trip"]),
            min_nights=r["min_nights"],
            max_nights=r["max_nights"],
            adults=r["adults"],
            cabin=r["cabin"],
            max_stops=r["max_stops"],
            target_cash_brl=r["target_cash_brl"],
            target_miles=r["target_miles"],
            explore_days=r["explore_days"],
            active=bool(r["active"]),
            created_at=datetime.fromisoformat(r["created_at"]),
        )

    def get_watch(self, watch_id: int) -> Watch | None:
        r = self.conn.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()
        return self._row_to_watch(r) if r else None

    def list_watches(self, only_active: bool = False) -> list[Watch]:
        sql = "SELECT * FROM watches" + (" WHERE active = 1" if only_active else "") + " ORDER BY id"
        return [self._row_to_watch(r) for r in self.conn.execute(sql)]

    def set_watch_active(self, watch_id: int, active: bool) -> bool:
        cur = self.conn.execute("UPDATE watches SET active = ? WHERE id = ?", (int(active), watch_id))
        self.conn.commit()
        return cur.rowcount > 0

    def delete_watch(self, watch_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------------- buscas
    def last_searched(self, provider: str, adults: int, cabin: str) -> dict[tuple[str, str, date], datetime]:
        """Última busca bem-sucedida (ok/empty) por (origem, destino, data) para uma fonte."""
        rows = self.conn.execute(
            """SELECT origin, destination, date, MAX(searched_at) AS last FROM searches
               WHERE provider = ? AND adults = ? AND cabin = ? AND status IN ('ok', 'empty')
               GROUP BY origin, destination, date""",
            (provider, adults, cabin),
        )
        return {
            (r["origin"], r["destination"], date.fromisoformat(r["date"])): datetime.fromisoformat(r["last"])
            for r in rows
        }

    def record_search(
        self,
        provider: str,
        origin: str,
        destination: str,
        day: date,
        adults: int,
        cabin: str,
        status: str,
        quotes: list[FareQuote] | None = None,
        error: str | None = None,
        searched_at: datetime | None = None,
    ) -> int:
        searched_at = searched_at or _now()
        quotes = quotes or []
        cur = self.conn.execute(
            """INSERT INTO searches (provider, origin, destination, date, adults, cabin, searched_at,
               status, n_results, error) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (provider, origin, destination, _iso(day), adults, cabin, _iso(searched_at), status, len(quotes), error),
        )
        search_id = cur.lastrowid
        for q in quotes:
            q.observed_at = q.observed_at or searched_at
            self.conn.execute(
                """INSERT INTO quotes (search_id, provider, program, kind, origin, destination, date,
                   price_brl, miles, taxes_brl, taxes_estimated, airline, stops, duration_min,
                   flight_numbers, cabin, departure_time, arrival_time, booking_url, seats, observed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    search_id, q.provider, q.program, str(q.kind), q.origin, q.destination, _iso(q.date),
                    q.price_brl, q.miles, q.taxes_brl, int(q.taxes_estimated), q.airline, q.stops,
                    q.duration_min, q.flight_numbers, q.cabin, q.departure_time, q.arrival_time,
                    q.booking_url, q.seats, _iso(q.observed_at),
                ),
            )
        self.conn.commit()
        return search_id

    def current_quotes(
        self,
        origins: list[str],
        destinations: list[str],
        start: date,
        end: date,
        adults: int,
        cabin: str,
        max_age_days: int,
        now: datetime | None = None,
    ) -> list[FareQuote]:
        """Tarifas da busca mais recente de cada (fonte, rota, data), dentro da validade."""
        now = now or _now()
        cutoff = _iso(now - timedelta(days=max_age_days))
        ph_o = ",".join("?" * len(origins))
        ph_d = ",".join("?" * len(destinations))
        sql = f"""
            SELECT q.* FROM quotes q
            WHERE q.search_id IN (
                SELECT MAX(id) FROM searches
                WHERE status IN ('ok', 'empty') AND adults = ? AND cabin = ? AND searched_at >= ?
                  AND origin IN ({ph_o}) AND destination IN ({ph_d}) AND date BETWEEN ? AND ?
                GROUP BY provider, origin, destination, date
            )
        """
        params = [adults, cabin, cutoff, *origins, *destinations, _iso(start), _iso(end)]
        return [self._row_to_quote(r) for r in self.conn.execute(sql, params)]

    @staticmethod
    def _row_to_quote(r: sqlite3.Row) -> FareQuote:
        return FareQuote(
            id=r["id"],
            provider=r["provider"],
            program=r["program"],
            kind=FareKind(r["kind"]),
            origin=r["origin"],
            destination=r["destination"],
            date=date.fromisoformat(r["date"]),
            price_brl=r["price_brl"],
            miles=r["miles"],
            taxes_brl=r["taxes_brl"] or 0.0,
            taxes_estimated=bool(r["taxes_estimated"]),
            airline=r["airline"] or "",
            stops=r["stops"] or 0,
            duration_min=r["duration_min"],
            flight_numbers=r["flight_numbers"] or "",
            cabin=r["cabin"] or "economy",
            departure_time=r["departure_time"] or "",
            arrival_time=r["arrival_time"] or "",
            booking_url=r["booking_url"] or "",
            seats=r["seats"],
            observed_at=datetime.fromisoformat(r["observed_at"]),
        )

    def provider_health(self, days: int = 7) -> list[dict]:
        cutoff = _iso(_now() - timedelta(days=days))
        rows = self.conn.execute(
            """SELECT provider, status, COUNT(*) AS n, MAX(searched_at) AS last FROM searches
               WHERE searched_at >= ? GROUP BY provider, status ORDER BY provider, status""",
            (cutoff,),
        )
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- execuções
    def start_run(self, watch_id: int) -> int:
        cur = self.conn.execute("INSERT INTO runs (watch_id, started_at) VALUES (?, ?)", (watch_id, _iso(_now())))
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, **fields) -> None:
        fields["finished_at"] = _iso(_now())
        if "log" in fields and not isinstance(fields["log"], str):
            fields["log"] = json.dumps(fields["log"], ensure_ascii=False)
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))
        self.conn.commit()

    def run_history(self, watch_id: int, limit: int = 60) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM runs WHERE watch_id = ? AND finished_at IS NOT NULL ORDER BY id DESC LIMIT ?",
            (watch_id, limit),
        )
        return [dict(r) for r in rows]
