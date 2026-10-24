from fastapi.testclient import TestClient

from radar.web.app import create_app


def test_create_and_view_watch(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        resp = client.post("/watches", data={
            "nome": "Lisboa", "origem": "GRU", "destino": "PT", "inicio": "2027-03-01", "fim": "2027-03-25",
            "noites_min": "7", "noites_max": "12", "adultos": "2", "cabine": "economy", "meta_dinheiro": "4.500,00",
            "explorar": "15",
        }, follow_redirects=False)
        assert resp.status_code == 303
        page = client.get(resp.headers["location"])
        assert page.status_code == 200 and "Lisboa" in page.text and "Buscar agora" in page.text
        bad = client.post("/watches", data={"origem": "GRU", "destino": "LISBOA", "inicio": "2027-03-01",
                                            "fim": "2027-03-25"})
        assert bad.status_code == 400 and "Aeroporto inválido" in bad.text
        assert client.get("/watches/999").status_code == 404


def test_update_targets(settings):
    with TestClient(create_app(settings)) as client:
        resp = client.post("/watches", data={"origem": "GRU", "destino": "LIS", "inicio": "2027-03-01",
                                             "fim": "2027-03-25"}, follow_redirects=False)
        url = resp.headers["location"]
        r = client.post(f"{url}/metas", data={"meta_dinheiro": "3.900,00", "meta_milhas": "120.000"},
                        follow_redirects=False)
        assert r.status_code == 303
        db = client.app.state.db
        w = db.get_watch(int(url.rsplit("/", 1)[1]))
        assert (w.target_cash_brl, w.target_miles) == (3900.0, 120000)
        assert "Alertas de preço" in client.get(url).text


def test_failed_source_is_explained_on_page(settings):
    import asyncio

    from radar.db import Database
    from radar.runner import run_all

    settings.providers = ["fonte_que_nao_existe"]
    with TestClient(create_app(settings)) as client:
        resp = client.post("/watches", data={"origem": "GRU", "destino": "LIS", "inicio": "2027-03-01",
                                             "fim": "2027-03-25"}, follow_redirects=False)
        url = resp.headers["location"]
        assert "ainda não buscou" in client.get(url).text
        db = Database(settings.db_path)
        asyncio.run(run_all(db, settings, notify=False))
        db.close()
        page = client.get(url).text
        assert "a busca falhou" in page and "Fonte desconhecida" in page
        status = client.get(f"{url}/status").json()
        assert status == {"running": False, "providers": {}}
