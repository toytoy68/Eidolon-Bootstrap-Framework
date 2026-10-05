# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_http_demo.py
# Description : Recherche et lecteur HTTP raccordés, serveur local synthétique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Only 127.0.0.1 is contacted. No real provider, Internet, model or mission."""
import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from eidolon_core.contracts import encode
from eidolon_core.egress import WebPolicy
from eidolon_core.presentation import header, message
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import StdlibConnector, TransportLimits


class LocalFixtureConnector(StdlibConnector):
    """DEMO ONLY: map a policy-checked fictitious public address to loopback.

    Reported addresses remain policy fixture values, not real remote hosts.
    Never use this connector in production.
    """
    def exchange(self, **kwargs):
        return super().exchange(**{**kwargs, "address": "127.0.0.1"})


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append((self.headers.get("Host"), self.path))
        body, status, kind = b"Document synthetique : verifier avant d'agir.", 200, "text/plain"
        extra = []
        if self.path == "/denied":
            status, body = 403, b"SECRET-ERROR-BODY"
        elif self.path == "/quota":
            status, body, extra = 429, b"", [("Retry-After", "120")]
        elif self.path == "/challenge":
            body, kind = b"<title>Verify you are human</title>", "text/html"
        elif self.path == "/start":
            status, body, extra = 302, b"", [("Location", "/plain")]
        self.send_response(status)
        for k, v in [("Content-Type", kind), ("Content-Length", str(len(body))), *extra]:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def fixture_dns(host, port):
    return ["9.9.9.9"]  # selected by policy, never contacted by the demo connector


class FixtureProvider:
    provider_id = "http-demo-fixtures/1"
    def __init__(self, port):
        self.port = port

    def search(self, query, limit):
        return [Hit(f"http://{host}.example:{self.port}/{path}", f"Fixture {path}")
                for host, path in [("blocked", "denied"), ("quota", "quota"),
                                   ("challenge", "challenge"), ("docs", "start")]][:limit]


def run_demo():
    with fixture_server() as server:
        policy = WebPolicy(schemes=("http",), ports=(server.server_port,))
        reader = WebReader(fixture_dns, LocalFixtureConnector(),
                           TransportLimits(max_body_bytes=128_000, total_seconds=5, read_seconds=2),
                           transport_id="loopback-demo-only/1")
        coordinator = ResearchCoordinator([FixtureProvider(server.server_port)], reader,
                                          resolver=fixture_dns, policy=policy)
        report = coordinator.run("Reference fictive", required_pages=2)
        assert report["status"] == "PARTIAL" and report["readable_pages"] == 1
        assert [s["state"] for s in report["sources"]] == [
            "ACCESS_DENIED", "RATE_LIMITED", "CHALLENGE_SUSPECTED", "READ"]
        assert len(report["sources"][-1]["retrieval"]["hops"]) == 2
        assert len(server.requests) == 5  # four reads, including one redirect
        assert "SECRET-ERROR-BODY" not in encode(report)
        return {"synthetic": True, "network": "loopback only; reported public IPs are fixture values",
                "http_requests": len(server.requests), "report": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    result = run_demo()
    if args.format == "json":
        print(encode(result))
    else:
        print(header(title="Recherche HTTP locale"))
        print(message("INFO", "Serveur synthétique sur 127.0.0.1 ; fournisseur et DNS simulés."))
        for source in result["report"]["sources"]:
            print(message("INFO", f"{source['state']} | HTTP {source.get('http_status')}"))
        print(message("OK", "Parcours vérifié : 5 requêtes locales, 1 texte lu, résultat PARTIAL."))
        print(message("ATTENTION", "Aucune recherche Internet ni mission réelle validée."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
