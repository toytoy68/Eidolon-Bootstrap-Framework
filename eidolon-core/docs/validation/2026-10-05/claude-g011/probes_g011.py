# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g011.py
# Description : Sondes indépendantes des correctifs D1/D2/C5 (C-TASK-G011)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""New probes for C-TASK-G011, against the frozen target e25cd2a.

From eidolon-core/, with a frozen copy of e25cd2a:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen e25cd2a>/eidolon-core/src \
        python docs/validation/2026-10-05/claude-g011/probes_g011.py

Production code is imported read-only. Only 127.0.0.1 is contacted: a raw
socket server sends exact bytes so malformed responses reach http.client as
written. Elsewhere a fake connector records every exchange (= connection).
Each line prints observed facts; the classification is in README.md.
"""
import json
import socket
import socketserver
import sys
import threading
import time

from eidolon_core.contracts import ContractError
from eidolon_core.egress import WebPolicy
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse, StdlibConnector, TransportLimits, WebTransportError, fetch

PUBLIC = "93.184.215.10"            # never contacted
BLOCKED = "93.184.216.0/24"
MARKER = "SECRET-ERROR-BODY-g011"
TEXT = b"Reference text for the probe.\n"


def resolver(host, port):
    return ["93.184.216.34"] if host == "blocked.example" else [PUBLIC]


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


class FakeConnector:
    def __init__(self, routes, clock=None, advance=0.0):
        self.routes, self.calls, self.remaining = routes, [], []
        self.clock, self.advance = clock, advance

    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append(f"{host}{target}")
        self.remaining.append(remaining_seconds)
        if self.clock is not None:
            self.clock.value += self.advance
        status, hdrs, body = self.routes[f"{host}{target}"]
        return RawResponse(status, tuple(hdrs), body, True)


class Provider:
    provider_id = "probe-provider/1"

    def __init__(self, urls):
        self.urls = urls

    def search(self, query, limit):
        return [Hit(u, "t") for u in self.urls]


def coordinator(urls, connector, clock, policy=None):
    reader = WebReader(resolver=resolver, connector=connector, clock=clock,
                       limits=TransportLimits(max_body_bytes=128_000))
    return ResearchCoordinator([Provider(urls)], reader, resolver=resolver, policy=policy or WebPolicy(),
                               limits=ResearchLimits(reads=5), clock=clock)


def section(title):
    print(f"\n== {title}")


ANOMALIES = {
    "duplicate Retry-After": [("Retry-After", "60"), ("Retry-After", "60")],
    "duplicate Content-Type": [("Retry-After", "60"), ("Content-Type", "text/plain"), ("Content-Type", "text/html")],
    "Content-Length + Transfer-Encoding": [("Retry-After", "60"), ("Content-Length", "0"), ("Transfer-Encoding", "chunked")],
    "invalid Content-Length": [("Retry-After", "60"), ("Content-Length", "12abc")],
    "control char in value": [("Retry-After", "60\x01")],
    "malformed header name": [("Retry After", "60")],
    "101 header pairs": [("Retry-After", "60")] + [(f"X-H{i}", "v") for i in range(100)],
    "headers over max_header_bytes": [("Retry-After", "60"), ("X-Pad", "p" * 33_000)],
}


# --- Q1: D1 on doubles, 429 and 503 -------------------------------------------------------
def q1_doubles():
    section("Q1 D1 on doubles: anomalous 429/503 -> suspension, no second contact, even much later")
    for status in (429, 503):
        for name, headers in ANOMALIES.items():
            clock = Clock()
            conn = FakeConnector({"a.example/one": (status, headers, MARKER.encode()), "a.example/two": (200, [
                ("Content-Type", "text/plain"), ("Content-Length", str(len(TEXT)))], TEXT)})
            c = coordinator(["https://a.example/one", "https://a.example/two"], conn, clock)
            r1 = c.run("q", required_pages=2)
            src = r1["sources"][0]
            ret = src.get("retrieval") or {}
            clock.value += 10**7          # "very late": about 115 days of synthetic time
            c.providers = (Provider(["https://a.example/two"]),)
            r2 = c.run("q")
            leaked = MARKER in json.dumps([r1, r2]) or "60\x01" in json.dumps(r1) or "text/html" in json.dumps(r1)
            print(f"  {status} {name:36} states={[s['state'] for s in r1['sources']]} contacts={len(conn.calls)} "
                  f"late_run={r2['sources'][0]['state']} validated={ret.get('headers_validated')} "
                  f"error={ret.get('header_error')} review={src.get('retry_review_required')} raw_leak={leaked}")


# --- Q2: D1 on a real loopback server, plus parser failures --------------------------------
class RawHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = self.request.recv(4096)
            if not chunk:
                return
            data += chunk
        path = data.split(b" ", 2)[1].decode("ascii")
        self.server.hits[path] = self.server.hits.get(path, 0) + 1
        try:
            self.request.sendall(self.server.routes[path])
        except OSError:
            pass


class RawServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass


def response(status_line, headers, body=b""):
    head = status_line + b"\r\n" + b"".join(k + b": " + v + b"\r\n" for k, v in headers) + b"\r\n"
    return head + body


class LoopbackConnector(StdlibConnector):
    def exchange(self, **kwargs):
        return super().exchange(**{**kwargs, "address": "127.0.0.1"})


def q2_loopback():
    section("Q2 D1 on a loopback server (raw bytes) and parser failures before any status")
    ok = response(b"HTTP/1.1 200 OK", [(b"Content-Type", b"text/plain"), (b"Content-Length", str(len(TEXT)).encode()),
                                       (b"Connection", b"close")], TEXT)
    cases = {
        "429 duplicate Retry-After": response(b"HTTP/1.1 429 Too Many", [(b"Retry-After", b"60"), (b"Retry-After", b"60")], MARKER.encode()),
        "503 invalid Content-Length": response(b"HTTP/1.1 503 Busy", [(b"Retry-After", b"60"), (b"Content-Length", b"12abc")], MARKER.encode()),
        "429 control char in value": response(b"HTTP/1.1 429 Too Many", [(b"Retry-After", b"60\x01")]),
        "503 headers over max_header_bytes": response(b"HTTP/1.1 503 Busy", [(b"Retry-After", b"60"), (b"X-Pad", b"p" * 33_000)]),
        "429 CL + TE": response(b"HTTP/1.1 429 Too Many", [(b"Content-Length", b"0"), (b"Transfer-Encoding", b"chunked")]),
        "PARSER: 429 line over 65536": response(b"HTTP/1.1 429 Too Many", [(b"X-Long", b"l" * 70_000)]),
        "PARSER: 429 with 101 headers": response(b"HTTP/1.1 429 Too Many", [(f"X-H{i}".encode(), b"v") for i in range(101)]),
        "PARSER: garbage status line": b"HTP/1.1 429 nope\r\n\r\n",
    }
    for name, raw in cases.items():
        server = RawServer(("127.0.0.1", 0), RawHandler)
        server.routes, server.hits = {"/one": raw, "/two": ok}, {}
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        policy = WebPolicy(schemes=("http",), ports=(port,))
        try:
            clock = Clock(time.monotonic())
            reader = WebReader(resolver=resolver, connector=LoopbackConnector(), clock=time.monotonic)
            c = ResearchCoordinator([Provider([f"http://a.example:{port}/one", f"http://a.example:{port}/two"])], reader,
                                    resolver=resolver, policy=policy, limits=ResearchLimits(reads=5), clock=clock)
            r = c.run("q", required_pages=2)
            src = r["sources"][0]
            ret = src.get("retrieval") or {}
            print(f"  {name:36} states={[s['state'] for s in r['sources']]} hits={server.hits} "
                  f"error={ret.get('header_error')} status_seen={ret.get('status')} raw_leak={MARKER in json.dumps(r)}")
        finally:
            server.shutdown()
            server.server_close()


# --- Q3: controls -------------------------------------------------------------------------
def q3_controls():
    section("Q3 controls: ambiguous 200 refused, bad status types never promoted, date/provenance kept")
    policy = WebPolicy()
    conn = FakeConnector({"a.example/": (200, [("Content-Length", "5"), ("Content-Length", "5")], b"hello")})
    try:
        WebReader(resolver=resolver, connector=conn).read("https://a.example/", policy)
        print("  200 duplicate Content-Length -> READ (unexpected)")
    except AccessFailure as exc:
        print(f"  200 duplicate Content-Length -> {exc.code}")
    for bad in ("429", 429.0, True, 600, 99):
        clock = Clock()
        conn = FakeConnector({"a.example/one": (bad, [("Retry-After", "60")], b""), "a.example/two": (
            200, [("Content-Type", "text/plain"), ("Content-Length", str(len(TEXT)))], TEXT)})
        r = coordinator(["https://a.example/one", "https://a.example/two"], conn, clock).run("q", required_pages=2)
        print(f"  status {bad!r:6} -> states={[s['state'] for s in r['sources']]} contacts={len(conn.calls)}")
    clock = Clock()
    conn = FakeConnector({"a.example/r": (301, [("Location", "https://a.example/q")], b""),
                          "a.example/q": (429, [("Retry-After", "60"), ("Retry-After", "60")], b"")})
    r = coordinator(["https://a.example/r"], conn, clock).run("q")
    ret = r["sources"][0]["retrieval"]
    print(f"  429 after redirect: status={ret['status']} final_url={ret['final_url']} hops={[h['status'] for h in ret['hops']]} "
          f"observed_at_present={bool(ret.get('observed_at'))} policy_id_present={bool(ret.get('policy_id'))} "
          f"keys={sorted(ret)}")


# --- Q4: D2 budgets -----------------------------------------------------------------------
def q4_budgets():
    section("Q4 D2: decreasing budget across hops, guard time counted, connector's own time, float edge")
    clock = Clock(500.0)
    routes = {"a.example/1": (302, [("Location", "https://a.example/2")], b""),
              "a.example/2": (302, [("Location", "https://a.example/3")], b""),
              "a.example/3": (200, [("Content-Type", "text/plain"), ("Content-Length", str(len(TEXT)))], TEXT)}
    conn = FakeConnector(routes, clock=clock, advance=5.0)
    guard = lambda decision: setattr(clock, "value", clock.value + 2.0)
    fetch("https://a.example/1", policy=WebPolicy(), resolver=resolver, connector=conn,
          limits=TransportLimits(total_seconds=30), clock=clock, before_hop=guard)
    print(f"  remaining per hop (5 s exchange + 2 s guard): {conn.remaining}")
    clock = Clock(500.0)
    conn = FakeConnector(routes, clock=clock, advance=14.0)
    try:
        fetch("https://a.example/1", policy=WebPolicy(), resolver=resolver, connector=conn,
              limits=TransportLimits(total_seconds=30), clock=clock, before_hop=guard)
        print("  exhausted budget -> fetched (unexpected)")
    except WebTransportError as exc:
        print(f"  exhausted budget -> {exc.code}; contacted={conn.calls}")

    # Connector's own time and the float edge, on loopback.
    slow = response(b"HTTP/1.1 200 OK", [(b"Content-Type", b"text/plain"), (b"Content-Length", str(len(TEXT)).encode())], TEXT)

    class SlowHandler(RawHandler):
        def handle(self):
            if self.server.delay:
                self.request.recv(4096)
                time.sleep(self.server.delay)
                self.request.sendall(slow)
                return
            super().handle()

    for label, delay, clock_value, total in (("server waits 1.5 s, remaining 0.5 s", 1.5, None, 0.5),
                                             ("frozen reader clock 237.965, default 30 s", 0, 237.965, 30.0),
                                             ("frozen reader clock 238.0, default 30 s (control)", 0, 238.0, 30.0)):
        server = RawServer(("127.0.0.1", 0), SlowHandler)
        server.routes, server.hits, server.delay = {"/p": slow}, {}, delay
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        clk = (lambda v=clock_value: v) if clock_value is not None else time.monotonic
        start = time.monotonic()
        try:
            r = fetch(f"http://a.example:{port}/p", policy=WebPolicy(schemes=("http",), ports=(port,)), resolver=resolver,
                      connector=LoopbackConnector(), limits=TransportLimits(total_seconds=total), clock=clk)
            outcome = f"returned status={r.status} deadline_exceeded={r.deadline_exceeded}"
        except (WebTransportError, ContractError) as exc:
            outcome = f"{type(exc).__name__} {getattr(exc, 'code', '')} {exc}".strip()
        print(f"  {label:48} elapsed={time.monotonic() - start:4.1f}s -> {outcome} | (c+t)-c={(237.965 + 30.0) - 237.965!r}"
              if clock_value == 237.965 else f"  {label:48} elapsed={time.monotonic() - start:4.1f}s -> {outcome}")
        server.shutdown()
        server.server_close()

    # Same float edge through the whole reader/coordinator chain.
    server = RawServer(("127.0.0.1", 0), RawHandler)
    server.routes, server.hits = {"/p": slow}, {}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    reader = WebReader(resolver=resolver, connector=LoopbackConnector(), clock=lambda: 237.965)
    c = ResearchCoordinator([Provider([f"http://a.example:{port}/p"])], reader, resolver=resolver,
                            policy=WebPolicy(schemes=("http",), ports=(port,)), clock=Clock())
    r = c.run("q")
    print(f"  coordinator, reader clock frozen at 237.965 -> state={r['sources'][0]['state']} server_hits={server.hits}")
    server.shutdown()
    server.server_close()


# --- Q5: C5 and redirect control ----------------------------------------------------------
def q5_redirects():
    section("Q5 C5: redirect without Location; valid redirects still policy-checked")
    policy = WebPolicy(blocked_networks=(BLOCKED,))
    for name, headers in (("301 without Location", []),
                          ("302 to blocked network", [("Location", "https://blocked.example/x")]),
                          ("302 to http (scheme not allowed)", [("Location", "http://b.example/x")]),
                          ("302 to non-allowed port", [("Location", "https://b.example:8443/x")])):
        conn = FakeConnector({"a.example/": (301 if "301" in name else 302, headers, b""),
                              "blocked.example/x": (200, [], b""), "b.example/x": (200, [], b"")})
        try:
            WebReader(resolver=resolver, connector=conn).read("https://a.example/", policy)
            outcome = "READ (unexpected)"
        except AccessFailure as exc:
            outcome = exc.code
        print(f"  {name:34} -> {outcome}; contacted={conn.calls}")


def main():
    print(f"Python {sys.version.split()[0]}; only 127.0.0.1 contacted; fake connectors elsewhere.")
    q1_doubles(); q2_loopback(); q3_controls(); q4_budgets(); q5_redirects()
    return 0


if __name__ == "__main__":
    sys.exit(main())
