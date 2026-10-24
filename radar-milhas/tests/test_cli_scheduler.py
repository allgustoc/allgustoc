from datetime import datetime, time

from radar.cli import main
from radar.scheduler import next_run, parse_run_times


def test_next_run_same_day_and_next_day():
    times = parse_run_times("19:00, 07:00")
    assert times == [time(7), time(19)]
    assert next_run(datetime(2026, 10, 17, 6, 0), times) == datetime(2026, 10, 17, 7, 0)
    assert next_run(datetime(2026, 10, 17, 7, 0), times) == datetime(2026, 10, 17, 19, 0)
    assert next_run(datetime(2026, 10, 17, 20, 0), times) == datetime(2026, 10, 18, 7, 0)


def test_cli_add_run_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RADAR_DB_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("RADAR_PROVIDERS", "demo")
    monkeypatch.setenv("RADAR_ALLOW_DEMO", "1")
    monkeypatch.setenv("RADAR_REQUEST_DELAY", "0")
    assert main(["add", "--origem", "GRU", "--destino", "PT", "--inicio", "01/03/2027", "--fim", "2027-03-20",
                 "--noites", "7-10"]) == 0
    assert "LIS (Lisboa)" in capsys.readouterr().out
    assert main(["run", "--sem-notificar"]) == 0
    out = capsys.readouterr().out
    assert "Melhor em dinheiro" in out and "[demo] radar #1" in out
    assert main(["report", "1"]) == 0
    assert main(["add", "--origem", "GRU", "--destino", "XYZ1", "--inicio", "2027-03-01", "--fim", "2027-03-20"]) == 2


def test_default_sources_are_real(monkeypatch, tmp_path):
    from radar.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RADAR_PROVIDERS", raising=False)
    assert Settings.from_env().providers == ["latam", "smiles", "azul"]


def test_old_env_with_demo_uses_real_sources_and_purges(tmp_path, monkeypatch, capsys):
    from datetime import date as d

    from radar.config import Settings
    from radar.db import Database
    from radar.models import FareKind, FareQuote

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RADAR_PROVIDERS", "demo")
    monkeypatch.delenv("RADAR_ALLOW_DEMO", raising=False)
    monkeypatch.setenv("RADAR_DB_PATH", str(tmp_path / "old.db"))
    assert Settings.from_env().providers == ["latam", "smiles", "azul"]
    db = Database(tmp_path / "old.db")
    q = FareQuote(provider="demo", program="cash", kind=FareKind.CASH, origin="GRU", destination="LIS",
                  date=d(2027, 3, 2), price_brl=1)
    db.record_search("demo", "GRU", "LIS", d(2027, 3, 2), 1, "economy", "ok", [q])
    db.close()
    assert main(["list"]) == 0
    assert "Dados de teste antigos removidos" in capsys.readouterr().err
    db = Database(tmp_path / "old.db")
    assert db.conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0] == 0
