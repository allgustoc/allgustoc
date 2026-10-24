"""Valida a captura de JSON pelo navegador contra um site local que imita a LATAM.

Precisa do Playwright e de um Chromium: `pip install -e '.[browser]' && playwright install chromium`
(ou RADAR_BROWSER_EXECUTABLE apontando para um Chromium já instalado)."""

import asyncio
import json
import os
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from radar.providers.base import ProviderBlocked
from radar.providers.browser import BrowserSession
from radar.providers.latam import parse_latam

pytest.importorskip("playwright")

PAGE = b"""<html><body><div id=app>carregando</div><script>
fetch('/bff/air-offers/v2/offers/search?redemption=true').then(r => r.json())
  .then(d => document.getElementById('app').textContent = d.content.length + ' voos');
</script></body></html>"""
OFFERS = {"content": [{"summary": {"origin": {"iataCode": "GRU", "departure": "2027-03-02T23:35:00"},
                                   "destination": {"iataCode": "LIS"}, "stopOvers": 0,
                                   "lowestPrice": {"amount": 61000, "taxes": 380.0}}}]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/bff/"):
            body, ctype = json.dumps(OFFERS).encode(), "application/json"
        elif self.path.startswith("/blocked"):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access Denied")
            return
        else:
            body, ctype = PAGE, "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _session(settings, tmp_path):
    settings.browser_profile_dir = str(tmp_path / "profile")
    settings.browser_timeout = 15
    settings.browser_headless = True
    settings.debug_dump_dir = str(tmp_path / "debug")
    settings.browser_executable = os.environ.get("RADAR_BROWSER_EXECUTABLE", "")
    return BrowserSession(settings, "teste")


def test_capture_and_parse(server, settings, tmp_path):
    async def go():
        session = _session(settings, tmp_path)
        try:
            return await session.capture(f"{server}/oferta-voos", lambda u: "/bff/air-offers" in u)
        finally:
            await session.close()

    try:
        captured = asyncio.run(go())
    except Exception as exc:  # Chromium ausente na máquina
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("Chromium do Playwright não instalado")
        raise
    (q,) = parse_latam(captured[-1].body, date(2027, 3, 2), "economy", True, 400)
    assert (q.origin, q.destination, q.miles, q.taxes_brl) == ("GRU", "LIS", 61000, 380.0)


def test_block_page_raises(server, settings, tmp_path):
    async def go():
        session = _session(settings, tmp_path)
        try:
            await session.capture(f"{server}/blocked", lambda u: "/blocked" in u)
        finally:
            await session.close()

    with pytest.raises(ProviderBlocked):
        try:
            asyncio.run(go())
        except ProviderBlocked:
            raise
        except Exception as exc:
            if "não está instalado" in str(exc) or "Executable doesn't exist" in str(exc):
                pytest.skip("Chromium do Playwright não instalado")
            raise
    saved = list((tmp_path / "debug").glob("teste-falha-*"))
    assert {p.suffix for p in saved} == {".png", ".json"}


def test_missing_chromium_gives_install_hint(settings, tmp_path):
    from radar.providers.base import ProviderError

    session = _session(settings, tmp_path)
    settings.browser_executable = str(tmp_path / "nao-existe" / "chrome")

    async def go():
        try:
            await session._ensure()
        finally:
            await session.close()

    with pytest.raises(ProviderError, match="playwright install chromium"):
        asyncio.run(go())
