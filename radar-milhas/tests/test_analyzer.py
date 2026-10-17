from datetime import date

from radar.alerts import evaluate
from radar.analyzer import analyze
from radar.models import FareKind, FareQuote


def cash(o, d, day, price):
    return FareQuote(provider="t", program="cash", kind=FareKind.CASH, origin=o, destination=d, date=day, price_brl=price)


def award(o, d, day, miles, taxes=300.0, program="smiles"):
    return FareQuote(provider="t", program=program, kind=FareKind.MILES, origin=o, destination=d, date=day,
                     miles=miles, taxes_brl=taxes)


def test_round_trip_combines_programs_and_respects_nights(watch, settings):
    settings.milheiro = {"smiles": 20.0, "latampass": 25.0}
    quotes = [
        cash("GRU", "LIS", date(2027, 3, 2), 2500),
        cash("LIS", "GRU", date(2027, 3, 11), 2600),
        award("GRU", "LIS", date(2027, 3, 2), 50000),  # 50*20+300 = 1300
        award("LIS", "GRU", date(2027, 3, 11), 60000, program="latampass", taxes=200),  # 60*25+200 = 1700
        cash("LIS", "GRU", date(2027, 3, 4), 100),  # só 2 noites: não pode combinar
    ]
    a = analyze(watch, quotes, settings)
    assert a.best_cash[0].cost_brl == 5100
    assert a.best_cash[0].nights == 9
    best = a.best_overall[0]
    assert best.cost_brl == 3000
    assert {l.quote.program for l in best.legs} == {"smiles", "latampass"}
    assert best.total_miles == 110000 and best.cash_out_of_pocket == 500
    assert a.best_miles[0].cost_brl == 3000


def test_suggestions_outside_window(watch, settings):
    quotes = [
        cash("GRU", "LIS", date(2027, 3, 2), 3000),
        cash("LIS", "GRU", date(2027, 3, 10), 3000),
        cash("GRU", "LIS", date(2027, 2, 22), 1500),  # antes da janela
        cash("LIS", "GRU", date(2027, 3, 2), 1500),
        cash("GRU", "LIS", date(2027, 3, 15), 2950),  # fora, mas economia pequena
        cash("LIS", "GRU", date(2027, 3, 23), 2950),
    ]
    a = analyze(watch, quotes, settings)
    assert a.best_overall[0].cost_brl == 6000
    assert len(a.suggestions) == 1
    s = a.suggestions[0]
    assert s.outbound.date == date(2027, 2, 22) and s.cost_brl == 3000
    assert abs(s.saving_vs_window - 0.5) < 1e-9
    assert "sugestao" in {al.rule for al in evaluate(a, settings)}


def test_one_way_and_max_stops(watch, settings):
    watch.round_trip = False
    watch.max_stops = 0
    q1 = cash("GRU", "LIS", date(2027, 3, 5), 1000)
    q1.stops = 2
    q2 = cash("GRU", "LIS", date(2027, 3, 6), 1800)
    a = analyze(watch, [q1, q2], settings)
    assert [t.cost_brl for t in a.best_cash] == [1800]
    assert a.best_cash[0].inbound is None


def test_miles_value_and_trend(watch, settings):
    settings.milheiro = {"smiles": 16.0}
    quotes = [
        cash("GRU", "LIS", date(2027, 3, 2), 3300),
        award("GRU", "LIS", date(2027, 3, 2), 100000, taxes=300),
        cash("LIS", "GRU", date(2027, 3, 12), 2000),
    ]
    history = [{"best_cash_brl": 8000, "best_miles_brl": None, "best_overall_brl": 7000}] * 3
    a = analyze(watch, quotes, settings, history=history)
    mv = a.miles_value[0]
    assert mv["program"] == "smiles" and mv["median_value"] == 30.0
    assert mv["verdict"] == "Vale muito a pena usar milhas"
    assert a.trend["cash"]["is_record"] and a.trend["cash"]["pct"] < 0
    assert "recorde" in {al.rule for al in evaluate(a, settings)}


