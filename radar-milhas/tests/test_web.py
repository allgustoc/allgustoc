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
