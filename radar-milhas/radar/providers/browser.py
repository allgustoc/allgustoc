"""Navegador automatizado (Playwright) para os sites dos programas de fidelidade.

Smiles, LATAM Pass e Azul não têm API pública. Em vez de imitar as chamadas internas
(que exigem tokens e passam por antirrobô), abrimos a página de resultados como um
usuário faria e capturamos o JSON que o próprio site recebe. O perfil do navegador é
persistente (RADAR_BROWSER_PROFILE_DIR), então cookies e eventual login são mantidos.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..config import Settings
from .base import ProviderBlocked, ProviderError

log = logging.getLogger(__name__)

BLOCK_MARKERS = ("captcha", "access denied", "acesso negado", "unusual traffic", "request unsuccessful")


@dataclass
class Captured:
    url: str
    status: int
    body: Any
    request_headers: dict[str, str] = field(default_factory=dict)


class BrowserSession:
    def __init__(self, settings: Settings, profile: str):
        self.settings = settings
        self.profile = profile
        self._pw = None
        self._ctx = None
        self._lock = asyncio.Lock()

    async def _ensure(self):
        if self._ctx is not None:
            return self._ctx
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ProviderError(
                "Playwright não instalado: pip install 'radar-milhas[browser]' && playwright install chromium",
                transient=False,
            ) from exc
        self._pw = await async_playwright().start()
        kwargs: dict[str, Any] = {
            "headless": self.settings.browser_headless,
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo",
            "viewport": {"width": 1366, "height": 900},
        }
        if self.settings.browser_executable:
            kwargs["executable_path"] = self.settings.browser_executable
        profile_dir = Path(self.settings.browser_profile_dir) / self.profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = await self._pw.chromium.launch_persistent_context(str(profile_dir), **kwargs)
        return self._ctx

    async def capture(self, url: str, matcher: Callable[[str], bool], timeout: float | None = None) -> list[Captured]:
        """Abre `url` e devolve as respostas JSON cujas URLs satisfazem `matcher`."""
        timeout = timeout or self.settings.browser_timeout
        async with self._lock:
            ctx = await self._ensure()
            page = await ctx.new_page()
            captured: list[Captured] = []
            pending: list[asyncio.Task] = []

            async def handle(response):
                if response.request.method == "OPTIONS" or not matcher(response.url):
                    return
                try:
                    body = await response.json()
                except Exception:  # resposta não-JSON (HTML de bloqueio, por exemplo)
                    body = None
                try:
                    headers = await response.request.all_headers()
                except Exception:
                    headers = {}
                captured.append(Captured(response.url, response.status, body, headers))

            page.on("response", lambda r: pending.append(asyncio.ensure_future(handle(r))))
            loop = asyncio.get_running_loop()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                deadline = loop.time() + timeout
                while loop.time() < deadline:
                    if any(c.body is not None and c.status < 400 for c in captured):
                        await asyncio.sleep(1.5)  # deixa chegar respostas complementares
                        break
                    if any(c.status in (403, 429) for c in captured):
                        break
                    await asyncio.sleep(0.5)
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                if not any(c.body is not None and c.status < 400 for c in captured):
                    text = ""
                    try:
                        text = ((await page.title()) + " " + (await page.inner_text("body"))[:2000]).lower()
                    except Exception:
                        pass
                    if any(c.status in (403, 429) for c in captured) or any(m in text for m in BLOCK_MARKERS):
                        raise ProviderBlocked(f"{self.profile}: o site bloqueou a automação (antirrobô/captcha)")
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"{self.profile}: falha no navegador: {exc}") from exc
            finally:
                await page.close()
            ok = [c for c in captured if c.body is not None and c.status < 400]
            if not ok:
                raise ProviderError(f"{self.profile}: o site não retornou resultados em {timeout:.0f}s")
            return ok

    async def get_json(self, url: str, headers: dict[str, str]) -> Any:
        """GET reaproveitando cookies do navegador (ex.: taxas de embarque da Smiles)."""
        ctx = await self._ensure()
        safe = {k: v for k, v in headers.items() if not k.startswith(":") and k.lower() not in {"host", "content-length"}}
        resp = await ctx.request.get(url, headers=safe, timeout=self.settings.browser_timeout * 1000)
        if resp.status in (403, 429):
            raise ProviderBlocked(f"{self.profile}: bloqueado ao consultar {url.split('?')[0]}")
        if not resp.ok:
            raise ProviderError(f"{self.profile}: HTTP {resp.status} em {url.split('?')[0]}")
        return await resp.json()

    async def close(self) -> None:
        if self._ctx is not None:
            await self._ctx.close()
            self._ctx = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None


def walk(node: Any):
    """Percorre recursivamente dicts/listas de um JSON."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def find_number(node: Any, keys: tuple[str, ...]) -> float | None:
    """Primeiro valor numérico encontrado sob alguma das chaves (busca em profundidade)."""
    for d in walk(node):
        for key in keys:
            value = d.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            if isinstance(value, dict):
                inner = value.get("amount", value.get("value"))
                if isinstance(inner, (int, float)) and not isinstance(inner, bool):
                    return float(inner)
    return None
