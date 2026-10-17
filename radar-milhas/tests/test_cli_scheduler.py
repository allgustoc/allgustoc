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
    monkeypatch.setenv("RADAR_REQUEST_DELAY", "0")
    assert main(["add", "--origem", "GRU", "--destino", "PT", "--inicio", "01/03/2027", "--fim", "2027-03-20",
                 "--noites", "7-10"]) == 0
    assert "LIS (Lisboa)" in capsys.readouterr().out
    assert main(["run", "--sem-notificar"]) == 0
    out = capsys.readouterr().out
    assert "Melhor em dinheiro" in out and "[demo] radar #1" in out
    assert main(["report", "1"]) == 0
    assert main(["add", "--origem", "GRU", "--destino", "XYZ1", "--inicio", "2027-03-01", "--fim", "2027-03-20"]) == 2
