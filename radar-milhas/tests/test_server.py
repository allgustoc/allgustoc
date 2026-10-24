import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from radar.web.server import MARKER_HEADER, bind_sockets, check_panel


def _serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/radar-milhas/"


class OtherServer(BaseHTTPRequestHandler):
    # Imita o servidor embutido do Windows (http.sys/IIS), que costuma ocupar a porta 80.
    server_version = "Microsoft-HTTPAPI/2.0"
    sys_version = ""

    def do_GET(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, *args):
        pass


class Panel(OtherServer):
    def do_GET(self):
        self.send_response(200)
        self.send_header(MARKER_HEADER, "1")
        self.end_headers()


def test_check_panel_detects_another_program():
    httpd, url = _serve(OtherServer)
    try:
        problem = check_panel(url)
        assert problem and "outro programa" in problem and "Microsoft-HTTPAPI" in problem
    finally:
        httpd.shutdown()
    httpd, url = _serve(Panel)
    try:
        assert check_panel(url) is None
    finally:
        httpd.shutdown()


def test_bind_sockets_refuses_busy_port():
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        assert bind_sockets("127.0.0.1", port) is None
    finally:
        busy.close()
    socks = bind_sockets("127.0.0.1", 0)
    assert socks and socks[0].getsockname()[0] == "127.0.0.1"
    for s in socks:
        s.close()
