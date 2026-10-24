"""Sobe o painel escutando em IPv4 e IPv6 e confere se é ele mesmo quem responde em localhost.

No Windows, "localhost" costuma ir primeiro para o IPv6 (::1). Se o painel escutasse só em 127.0.0.1
e outro programa (IIS, por exemplo) ocupasse a porta 80 no IPv6, o navegador mostraria o "Not Found"
desse outro programa.
"""

from __future__ import annotations

import errno
import socket
import sys
import threading
import urllib.error
import urllib.request

MARKER_HEADER = "X-Radar-Milhas"
LOOPBACK = (("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6))


def _close(socks: list[socket.socket]) -> None:
    for s in socks:
        s.close()


def bind_sockets(host: str, port: int) -> list[socket.socket] | None:
    """Reserva a porta em todos os endereços de `host`; None se algum já estiver em uso."""
    if host in ("127.0.0.1", "localhost"):
        targets = LOOPBACK
    elif host in ("0.0.0.0", "::"):
        targets = (("0.0.0.0", socket.AF_INET), ("::", socket.AF_INET6))
    else:
        targets = ((host, socket.AF_INET6 if ":" in host else socket.AF_INET),)
    socks: list[socket.socket] = []
    for address, family in targets:
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            continue  # computador sem IPv6
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        if sys.platform != "win32":
            # No Windows SO_REUSEADDR deixaria dividir a porta com outro programa; nos demais só evita
            # esperar o TIME_WAIT ao reiniciar.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((address, port))
        except OSError as exc:
            sock.close()
            if family == socket.AF_INET6 and exc.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT):
                continue  # IPv6 desativado: segue só com IPv4
            _close(socks)
            return None
        sock.listen(2048)
        socks.append(sock)
    return socks or None


def check_panel(url: str) -> str | None:
    """None se o painel respondeu em `url`; senão, a descrição do que respondeu no lugar."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=5) as resp:
            headers = resp.headers
            status = resp.status
    except urllib.error.HTTPError as exc:
        headers, status = exc.headers, exc.code
    except OSError as exc:
        return f"ninguém respondeu ({exc})"
    if headers.get(MARKER_HEADER):
        return None
    server = headers.get("Server") or "desconhecido"
    return f"outro programa respondeu (HTTP {status}, servidor: {server})"


def report_after_start(url: str, fallback_url: str, open_browser: bool, delay: float = 2.0) -> None:
    """Depois que o servidor sobe, confere o endereço e abre o navegador no que funciona."""

    def run() -> None:
        problem = check_panel(url)
        target = url
        if problem:
            print(f"\nAtenção: em {url} {problem}.")
            if check_panel(fallback_url) is None:
                print(f"O painel está funcionando em {fallback_url}")
                target = fallback_url
            else:
                print("O painel não respondeu nem pelo endereço numérico. Veja as mensagens acima.")
        if open_browser:
            import webbrowser

            webbrowser.open(target)

    threading.Timer(delay, run).start()
