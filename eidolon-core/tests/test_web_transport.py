# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_transport.py
# Description : Tests du transport HTTP de lecture candidat, sans Internet
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Simulated connector and loopback servers only; no real site is contacted.

The loopback tests keep the public web policy unchanged: a test-only connector
maps the pinned PUBLIC test address to 127.0.0.1 after the policy decided.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.egress import WebPolicy, decide
from eidolon_core.web_transport import (RawResponse, StdlibConnector, TransportLimits, WebTransportError,
                                        fetch)

PUBLIC = "93.184.215.14"
OTHER_PUBLIC = "93.184.215.15"


def resolver(table, calls=None):
    def resolve(host, port):
        if calls is not None:
            calls.append(host)
        return table[host]
    return resolve


DNS = resolver({"docs.example.com": [PUBLIC], "cdn.example.com": [OTHER_PUBLIC],
                "nas.attacker.example": ["192.168.1.10"], "home.attacker.example": ["203.0.113.7"]})
POLICY = WebPolicy()


class FakeConnector:
    """Scripted responses keyed by (address, target); records every exchange."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def exchange(self, *, scheme, host, port, address, target, headers, limits, deadline):
        self.calls.append({"scheme": scheme, "host": host, "port": port, "address": address,
                           "target": target, "headers": dict(headers)})
        response = self.script[(address, target)]
        if isinstance(response, Exception):
            raise response
        return response


def ok(body=b"hello", content_type="text/plain", extra=()):
    return RawResponse(200, (("Content-Type", content_type), ("Content-Length", str(len(body))), *extra),
                       body, True)


def redirect(location, status=302):
    return RawResponse(status, (("Location", location),), b"", True)


class FetchTests(unittest.TestCase):
    def test_success_records_evidence_without_second_resolution(self):
        calls = []
        answers = iter([[PUBLIC], ["127.0.0.1"]])  # a second lookup would rebind to loopback

        def rebinding(host, port):
            calls.append(host)
            return next(answers)
        connector = FakeConnector({(PUBLIC, "/guide?q=1"): ok(b"ZQXJ7")})
        result = fetch("https://docs.example.com/guide?q=1", policy=POLICY, resolver=rebinding,
                       connector=connector)
        self.assertEqual(calls, ["docs.example.com"])
        self.assertEqual((result.address, result.port, result.status, result.size),
                         (PUBLIC, 443, 200, 5))
        self.assertEqual(result.sha256, hashlib.sha256(b"ZQXJ7").hexdigest())
        self.assertEqual(result.final_url, "https://docs.example.com/guide?q=1")
        self.assertEqual(result.policy_id, POLICY.policy_id)
        hop = result.hops[0]
        self.assertEqual(hop["url"], "https://docs.example.com/guide")
        self.assertIn("query_sha256", hop)
        self.assertNotIn("ZQXJ7", str(result.evidence()))

    def test_request_is_fixed_get_with_name_host_and_no_extras(self):
        connector = FakeConnector({(PUBLIC, "/"): ok()})
        fetch("https://docs.example.com", policy=POLICY, resolver=DNS, connector=connector)
        call = connector.calls[0]
        self.assertEqual((call["host"], call["address"], call["target"]), ("docs.example.com", PUBLIC, "/"))
        self.assertEqual(set(call["headers"]), {"Host", "User-Agent", "Accept", "Accept-Encoding", "Connection"})
        self.assertEqual(call["headers"]["Host"], "docs.example.com")
        self.assertEqual(call["headers"]["Accept-Encoding"], "identity")

    def test_refused_destination_is_never_contacted(self):
        for url in ("https://nas.attacker.example/", "https://127.0.0.1/", "http://docs.example.com/",
                    "https://docs.example.com:8443/"):
            connector = FakeConnector({})
            with self.assertRaises(WebTransportError) as raised:
                fetch(url, policy=POLICY, resolver=DNS, connector=connector)
            self.assertEqual(raised.exception.code, "DESTINATION_REFUSED", url)
            self.assertEqual(connector.calls, [], url)

    def test_home_network_exclusion_applies_through_names_and_redirects(self):
        home = WebPolicy(blocked_networks=("203.0.113.0/24",))
        with self.assertRaises(WebTransportError) as raised:
            fetch("https://home.attacker.example/", policy=home, resolver=DNS, connector=FakeConnector({}))
        self.assertEqual(raised.exception.code, "DESTINATION_REFUSED")
        connector = FakeConnector({(PUBLIC, "/"): redirect("https://home.attacker.example/admin")})
        with self.assertRaises(WebTransportError):
            fetch("https://docs.example.com/", policy=home, resolver=DNS, connector=connector)
        self.assertEqual(len(connector.calls), 1)

    def test_redirects_are_rechecked_and_followed_by_code(self):
        connector = FakeConnector({(PUBLIC, "/a"): redirect("https://cdn.example.com/b?token=s3cret", 301),
                                   (OTHER_PUBLIC, "/b?token=s3cret"): ok(b"final")})
        result = fetch("https://docs.example.com/a", policy=POLICY, resolver=DNS, connector=connector)
        self.assertEqual((result.address, len(result.hops)), (OTHER_PUBLIC, 2))
        self.assertNotIn("s3cret", str(result.hops))
        for location in ("https://nas.attacker.example/", "http://docs.example.com/x", "//127.0.0.1/"):
            connector = FakeConnector({(PUBLIC, "/a"): redirect(location)})
            with self.assertRaises(WebTransportError, msg=location):
                fetch("https://docs.example.com/a", policy=POLICY, resolver=DNS, connector=connector)
            self.assertEqual(len(connector.calls), 1, location)

    def test_redirect_loop_and_budget(self):
        loop = FakeConnector({(PUBLIC, "/a"): redirect("/b"), (PUBLIC, "/b"): redirect("/a")})
        with self.assertRaises(WebTransportError) as raised:
            fetch("https://docs.example.com/a", policy=POLICY, resolver=DNS, connector=loop)
        self.assertEqual(raised.exception.code, "REDIRECT_LOOP")
        chain = FakeConnector({(PUBLIC, f"/{i}"): redirect(f"/{i + 1}") for i in range(10)})
        with self.assertRaises(WebTransportError) as raised:
            fetch("https://docs.example.com/0", policy=POLICY, resolver=DNS, connector=chain)
        self.assertEqual((raised.exception.code, len(chain.calls)), ("DESTINATION_REFUSED", 6))
        self.assertIn("TOO_MANY_REDIRECTS", str(raised.exception))

    def test_named_failures_never_echo_bodies(self):
        cases = {
            "HTTP_STATUS": RawResponse(500, (("Content-Type", "text/plain"),), b"SECRET-BODY", True),
            "HTTP_STATUS ": RawResponse(302, (), b"", True),
            "ENCODED_CONTENT": ok(gzip.compress(b"x" * 1000), extra=(("Content-Encoding", "gzip"),)),
            "ENCODED_CONTENT ": RawResponse(200, (("Transfer-Encoding", "gzip, chunked"),), b"hello", True),
            "TRUNCATED": RawResponse(200, (("Content-Length", "100"),), b"short", False),
            "AMBIGUOUS_HEADER": ok(extra=(("Content-Type", "text/html"),)),
            "HEADERS_TOO_LARGE": ok(extra=(("X-Big", "v" * 40_000),)),
            "BODY_TOO_LARGE": ok(b"y" * 2_000_001),
        }
        for code, response in cases.items():
            connector = FakeConnector({(PUBLIC, "/"): response})
            with self.assertRaises(WebTransportError, msg=code) as raised:
                fetch("https://docs.example.com/", policy=POLICY, resolver=DNS, connector=connector)
            self.assertEqual(raised.exception.code, code.strip(), code)
            self.assertNotIn("SECRET-BODY", str(raised.exception))

    def test_global_deadline_is_checked_between_hops(self):
        ticks = iter([0.0, 0.0, 31.0])
        connector = FakeConnector({(PUBLIC, "/a"): redirect("/b"), (PUBLIC, "/b"): ok()})
        with self.assertRaises(WebTransportError) as raised:
            fetch("https://docs.example.com/a", policy=POLICY, resolver=DNS, connector=connector,
                  clock=lambda: next(ticks))
        self.assertEqual((raised.exception.code, len(connector.calls)), ("DEADLINE_EXCEEDED", 1))

    def test_inputs_and_configuration(self):
        decision = decide("https://docs.example.com/", DNS, POLICY)
        with self.assertRaises(ContractError):
            fetch(decision, policy=POLICY, resolver=DNS, connector=FakeConnector({}))
        with self.assertRaises(ContractError):
            fetch("https://docs.example.com/", policy=None, resolver=DNS, connector=FakeConnector({}))
        for kwargs in ({"total_seconds": 0}, {"read_seconds": float("nan")}, {"max_body_bytes": 0},
                       {"max_header_bytes": True}):
            with self.assertRaises(ContractError, msg=kwargs):
                TransportLimits(**kwargs)
        insecure = ssl.create_default_context()
        insecure.check_hostname = False
        with self.assertRaises(ContractError):
            StdlibConnector(insecure)
        insecure.verify_mode = ssl.CERT_NONE
        with self.assertRaises(ContractError):
            StdlibConnector(insecure)


# --- loopback, real http.client --------------------------------------------------

class LoopbackConnector(StdlibConnector):
    """TEST ONLY: after the policy pinned a public test address, reach 127.0.0.1."""

    def exchange(self, **kwargs):
        self.seen = kwargs["address"]
        return super().exchange(**{**kwargs, "address": "127.0.0.1"})


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        server = self.server
        server.seen.append({"path": self.path, "host": self.headers.get("Host"),
                            "accept_encoding": self.headers.get("Accept-Encoding"),
                            "proxy_like": self.path.startswith("http"), "count": len(self.headers)})
        route = self.path.split("?")[0]
        try:
            if route == "/slow":
                time.sleep(1.5)
            if route == "/truncated":
                self.send_response(200)
                self.send_header("Content-Length", "1000")
                self.end_headers()
                self.wfile.write(b"x" * 10)
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            if route == "/many-headers":
                self.send_response(200)
                for i in range(120):
                    self.send_header(f"X-H{i}", "v")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if route == "/loop":
                self.send_response(302)
                self.send_header("Location", "/loop")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = {"/big": b"z" * 5000, "/gzip": gzip.compress(b"a" * 10_000)}.get(route, b"loopback ok")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            if route == "/gzip":
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def _server(context=None):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.seen, server.sni = [], []
    if context is not None:
        context.sni_callback = lambda sock, name, ctx: server.sni.append(name)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class LoopbackHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = _server()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.policy = WebPolicy(schemes=("http",), ports=(self.port,))  # address checks unchanged
        self.limits = TransportLimits(total_seconds=5, connect_seconds=1, read_seconds=0.5,
                                      max_body_bytes=4000, max_header_bytes=32_000)

    def get(self, path):
        return fetch(f"http://docs.example.com:{self.port}{path}", policy=self.policy, resolver=DNS,
                     connector=LoopbackConnector(), limits=self.limits)

    def code(self, path):
        with self.assertRaises(WebTransportError) as raised:
            self.get(path)
        return raised.exception.code

    def test_real_exchange_keeps_name_in_host_and_ignores_proxy_variables(self):
        trap = socket.socket()
        trap.bind(("127.0.0.1", 0))
        trap_port = trap.getsockname()[1]
        trap.close()
        proxies = {k: f"http://127.0.0.1:{trap_port}" for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY",
                                                                "https_proxy", "ALL_PROXY")}
        with patch.dict(os.environ, proxies):
            result = self.get("/page?x=1")
        seen = self.server.seen[-1]
        self.assertEqual((result.status, result.size, result.address), (200, 11, PUBLIC))
        self.assertEqual(seen["host"], f"docs.example.com:{self.port}")
        self.assertEqual((seen["path"], seen["accept_encoding"], seen["proxy_like"]), ("/page?x=1", "identity", False))
        self.assertEqual(seen["count"], 5)

    def test_real_failures(self):
        expected = {"/big": "BODY_TOO_LARGE", "/truncated": "TRUNCATED", "/slow": "TIMEOUT",
                    "/gzip": "ENCODED_CONTENT", "/many-headers": "HEADERS_TOO_LARGE", "/loop": "REDIRECT_LOOP"}
        for path, code in expected.items():
            self.assertEqual(self.code(path), code, path)

    def test_connection_refused(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        policy = WebPolicy(schemes=("http",), ports=(port,))
        with self.assertRaises(WebTransportError) as raised:
            fetch(f"http://docs.example.com:{port}/", policy=policy, resolver=DNS,
                  connector=LoopbackConnector(), limits=self.limits)
        self.assertEqual(raised.exception.code, "CONNECTION_FAILED")


@unittest.skipUnless(shutil.which("openssl"), "openssl CLI needed to build a test CA")
class LoopbackTLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="eidolon-tls-")
        run = lambda *args: subprocess.run(["openssl", *args], cwd=cls.dir, check=True, capture_output=True)  # noqa: E731
        run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=Eidolon Test CA",
            "-keyout", "ca.key", "-out", "ca.pem")
        for name in ("docs.example.com", "wrong.example.com"):
            Path(cls.dir, f"{name}.ext").write_text(f"subjectAltName=DNS:{name}\n")
            run("req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={name}", "-keyout", f"{name}.key",
                "-out", f"{name}.csr")
            run("x509", "-req", "-in", f"{name}.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
                "-days", "2", "-extfile", f"{name}.ext", "-out", f"{name}.pem")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def serve(self, name):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(Path(self.dir, f"{name}.pem"), Path(self.dir, f"{name}.key"))
        server = _server(context)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def fetch_tls(self, server, trust_test_ca=True):
        client = ssl.create_default_context(cafile=str(Path(self.dir, "ca.pem"))) if trust_test_ca else None
        policy = WebPolicy(ports=(server.server_port,))  # https only, address checks unchanged
        return fetch(f"https://docs.example.com:{server.server_port}/tls", policy=policy, resolver=DNS,
                     connector=LoopbackConnector(client),
                     limits=TransportLimits(total_seconds=5, connect_seconds=2, read_seconds=2))

    def test_sni_and_certificate_use_the_checked_name(self):
        server = self.serve("docs.example.com")
        result = self.fetch_tls(server)
        self.assertEqual((result.status, result.address), (200, PUBLIC))
        self.assertEqual(server.sni, ["docs.example.com"])
        self.assertEqual(server.seen[-1]["host"], f"docs.example.com:{server.server_port}")

    def test_wrong_name_and_untrusted_certificates_are_refused(self):
        with self.assertRaises(WebTransportError) as raised:
            self.fetch_tls(self.serve("wrong.example.com"))
        self.assertEqual(raised.exception.code, "TLS_CERTIFICATE")
        with self.assertRaises(WebTransportError) as raised:
            self.fetch_tls(self.serve("docs.example.com"), trust_test_ca=False)
        self.assertEqual(raised.exception.code, "TLS_CERTIFICATE")


class NoNetworkTests(unittest.TestCase):
    def test_simulated_fetch_opens_no_socket(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("network access attempted")
        with patch.object(socket, "create_connection", forbidden), patch.object(socket, "getaddrinfo", forbidden):
            fetch("https://docs.example.com/", policy=POLICY, resolver=DNS,
                  connector=FakeConnector({(PUBLIC, "/"): ok()}))


if __name__ == "__main__":
    unittest.main()
