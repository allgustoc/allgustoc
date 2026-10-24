import asyncio
from datetime import date, datetime, timedelta

from radar.alerts import evaluate, only_new
from radar.analyzer import analyze
from radar.models import FareKind, FareQuote
from radar.notifier import notify_results
from radar.runner import RunResult


def q(o, d, day, price=None, miles=None, taxes=300.0, program="cash"):
    kind = FareKind.CASH if miles is None else FareKind.MILES
    return FareQuote(provider="t", program=program if miles else "cash", kind=kind, origin=o, destination=d,
                     date=day, price_brl=price, miles=miles, taxes_brl=taxes if miles else 0.0)


def quotes(cash_out=2000.0):
    return [
        q("GRU", "LIS", date(2027, 3, 2), price=cash_out),
        q("LIS", "GRU", date(2027, 3, 12), price=2000.0),
        q("GRU", "LIS", date(2027, 3, 3), miles=40000, program="smiles"),
        q("LIS", "GRU", date(2027, 3, 12), miles=45000, program="smiles"),
        q("GRU", "LIS", date(2027, 3, 4), miles=90000, program="smiles", taxes=10),
    ]


def test_targets_trigger(watch, settings):
    watch.target_cash_brl = 4500
    watch.target_miles = 90000
    a = analyze(watch, quotes(), settings)
    rules = {al.rule: al for al in evaluate(a, settings)}
    assert rules["meta_dinheiro"].value == 4000
    # A meta de milhas usa a viagem com MENOS milhas, mesmo que não seja a mais barata em R$.
    assert rules["meta_milhas"].value == 85000
    watch.target_cash_brl = 3000
    assert "meta_dinheiro" not in {al.rule for al in evaluate(analyze(watch, quotes(), settings), settings)}


def test_only_new_dedupes():
    now = datetime(2026, 10, 17, 7)

    class A:
        def __init__(self, rule, value):
            self.rule, self.value = rule, value

    alerts = [A("meta_dinheiro", 4000), A("recorde", 3900), A("queda", 3000)]
    last = {
        "meta_dinheiro": (4050, now - timedelta(days=1)),  # caiu só 1%: não repete
        "recorde": (4100, now - timedelta(days=1)),  # caiu ~5%: repete
        "queda": (2900, now - timedelta(days=8)),  # mais de 7 dias: repete
    }
    assert [a.rule for a in only_new(alerts, last, now)] == ["recorde", "queda"]


def test_notify_sends_alert_once(db, settings, watch, capsys):
    settings.notify_mode = "deals"
    watch.target_cash_brl = 4500
    db.add_watch(watch)

    def notify(cash_out):
        a = analyze(watch, quotes(cash_out), settings)
        asyncio.run(notify_results([RunResult(watch, a, [])], settings, db))
        return capsys.readouterr().out

    first = notify(2000.0)
    assert "Alerta de preço" in first and "Meta em dinheiro atingida" in first
    assert notify(2000.0) == ""  # mesmo preço: não repete
    assert "Meta em dinheiro atingida" in notify(1500.0)  # caiu mais 3%: avisa de novo
    sent = db.list_alerts(watch.id)
    assert len(sent) == 2 and sent[0]["value"] == 3500


def test_whatsapp_splits_and_strips_html(settings):
    import httpx

    from radar.notifier import send_whatsapp

    settings.whatsapp_phone, settings.whatsapp_apikey = "+5531999999999", "123"
    sent = []

    def handler(request):
        sent.append(dict(request.url.params))
        return httpx.Response(200, text="Message queued")

    text = "<b>Alerta</b>\n" + "\n".join(f"linha {i} com &amp; detalhes" for i in range(80))
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    asyncio.run(send_whatsapp(text, settings, client))
    assert len(sent) > 1 and all(len(p["text"]) <= 900 for p in sent)
    assert sent[0]["text"].startswith("Alerta") and "&" in sent[0]["text"] and "<b>" not in sent[0]["text"]
    assert sent[0]["phone"] == "+5531999999999" and sent[0]["apikey"] == "123"
