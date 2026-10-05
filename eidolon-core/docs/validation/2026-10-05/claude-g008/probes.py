# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes.py
# Description : Sondes indépendantes de contre-revue du lecteur HTTP (C-TASK-G008)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G008. Production code is imported, never modified.

From eidolon-core/:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-g008/probes.py

Only 127.0.0.1 is contacted (local server); every other probe uses a fake
connector. Each probe prints OBSERVED facts; the classification lives in the
README (DEFECT / ANNOUNCED_LIMIT / CONSISTENCY / OK).
"""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import ssl
import sys
import threading
import time

from eidolon_core.egress import WebPolicy
from eidolon_core.research import Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse, StdlibConnector, TransportLimits, fetch

PUBLIC = "93.184.215.10"   # documentation-style public address; never contacted
TEXT = b"Reference text for the probe.\n"


def resolver(host, port):
    return [PUBLIC]


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


class FakeConnector:
    """Scripted responses per host+path; records every exchange (= connection)."""

    def __init__(self, routes, on_exchange=None):
        self.routes, self.calls, self.on_exchange = routes, [], on_exchange

    def exchange(self, *, scheme, host, port, address, target, headers, limits, deadline):
        self.calls.append(f"{host}{target}")
        if self.on_exchange:
            self.on_exchange()
        status, hdrs, body = self.routes[f"{host}{target}"]
        return RawResponse(status, tuple(hdrs), body, True)


class Provider:
    provider_id = "probe-provider/1"

    def __init__(self, urls):
        self.urls = urls

    def search(self, query, limit):
        return [Hit(u, "t") for u in self.urls]


def coordinator(urls, connector, *, clock=None, reader_clock=None, limits=None):
    clock = clock or Clock()
    reader = WebReader(resolver=resolver, connector=connector, clock=reader_clock or clock,
                       limits=TransportLimits(max_body_bytes=128_000))
    return ResearchCoordinator([Provider(urls)], reader, resolver=resolver,
                               limits=limits or ResearchLimits(reads=5), clock=clock)


def ok_text():
    return (200, [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(TEXT)))], TEXT)


def section(title):
    print(f"\n== {title}")


# --- P1: a 429 whose headers are anomalous loses its back-off -----------------------------
def p1_rate_limit_lost():
    section("P1 429 with anomalous headers: is the domain still suspended?")
    variants = {
        "control: normal 429": [("Retry-After", "600")],
        "duplicate Retry-After": [("Retry-After", "600"), ("Retry-After", "600")],
        "duplicate Content-Type": [("Retry-After", "600"), ("Content-Type", "text/html"),
                                   ("Content-Type", "text/html")],
        "Content-Length + Transfer-Encoding": [("Retry-After", "600"), ("Content-Length", "0"),
                                               ("Transfer-Encoding", "chunked")],
        "invalid Content-Length": [("Retry-After", "600"), ("Content-Length", "abc")],
    }
    for name, headers in variants.items():
        conn = FakeConnector({"a.example/one": (429, headers, b""), "a.example/two": ok_text()})
        c = coordinator(["https://a.example/one", "https://a.example/two"], conn)
        first = c.run("q", required_pages=2)
        after_run1 = len(conn.calls)
        c.providers = (Provider(["https://a.example/two"]),)
        c.run("q")
        print(f"  {name:36} run1 states={[s['state'] for s in first['sources']]} "
              f"run1 contacted={conn.calls[:after_run1]} | run2 contacted={conn.calls[after_run1:]}")


# --- P2: Retry-After values, through the public reader ------------------------------------
def p2_retry_after_values():
    section("P2 Retry-After on 429 (value -> retry_after, review)")
    now = datetime.now(timezone.utc)
    values = ["0", "120", "86400", "86401", "0000000120", "99999999999", "-5", "1.5", "  60  ",
              "120, 60", "١٢٠", "", format_datetime(now - timedelta(hours=1), usegmt=True),
              format_datetime(now + timedelta(hours=1), usegmt=True), "Fri, 31 Dec 9999 23:59:59 GMT",
              "2026-10-05T18:00:00Z", "Fri, 07 Aug 2026 11:07:16 +0200"]
    policy = WebPolicy()
    for value in values:
        conn = FakeConnector({"a.example/": (429, [("Retry-After", value)], b"")})
        try:
            page = WebReader(resolver=resolver, connector=conn).read("https://a.example/", policy)
            print(f"  {value!r:40} retry_after={page.retry_after} review={page.retry_review_required}")
        except Exception as exc:  # noqa: BLE001 - probe reports any failure by name
            print(f"  {value!r:40} raised {type(exc).__name__}: {exc}")


# --- P3: 3xx and 503 with Retry-After ----------------------------------------------------
def p3_redirect_and_503():
    section("P3 redirect / 503 carrying Retry-After")
    policy = WebPolicy()
    for status, ra in ((302, "30"), (302, "0"), (302, "never"), (503, "30"), (503, None)):
        headers = [("Location", "https://b.example/target")] if status == 302 else []
        if ra is not None:
            headers.append(("Retry-After", ra))
        conn = FakeConnector({"a.example/": (status, headers, b""), "b.example/target": ok_text()})
        page = WebReader(resolver=resolver, connector=conn).read("https://a.example/", policy)
        conn2 = FakeConnector(conn.routes)
        state = coordinator(["https://a.example/"], conn2).run("q")["sources"][0]["state"]
        print(f"  {status} Retry-After={ra!r:8} status={page.status} retry={page.retry_after} "
              f"review={page.retry_review_required} contacted={conn.calls} coordinator_state={state}")


# --- P4: alternative URL redirecting to a suspended domain --------------------------------
def p4_redirect_to_suspended():
    section("P4 alternative URL redirecting to a suspended domain")
    routes = {"b.example/x": (429, [("Retry-After", "600")], b""),
              "a.example/y": (302, [("Location", "https://b.example/z")], b""),
              "b.example/z": ok_text()}
    conn = FakeConnector(routes)
    c = coordinator(["https://b.example/x", "https://a.example/y"], conn)
    r = c.run("q", required_pages=2)
    print(f"  same run:        states={[s['state'] for s in r['sources']]} contacted={conn.calls}")
    conn.calls.clear()
    c.providers = (Provider(["https://a.example/y"]),)
    r = c.run("q")
    print(f"  next run, same coordinator: states={[s['state'] for s in r['sources']]} contacted={conn.calls}")
    conn.calls.clear()
    r = coordinator(["https://a.example/y"], conn).run("q")
    print(f"  new coordinator:            states={[s['state'] for s in r['sources']]} contacted={conn.calls} "
          f"(suspension is RAM-only)")


# --- P5: complete receipt after deadline / cancellation ----------------------------------
def p5_late_receipts():
    section("P5 complete receipt after transport deadline, research deadline, cancellation")
    # (a) transport deadline: the reader's clock passes total_seconds during the exchange.
    clock = Clock()
    conn = FakeConnector({"a.example/": ok_text()}, on_exchange=lambda: setattr(clock, "value", clock.value + 40))
    c = coordinator(["https://a.example/"], conn, clock=clock)
    r1 = c.run("q"); r2 = c.run("q")
    s = r1["sources"][0]
    print(f"  (a) transport late: run1 status={r1['status']} state={s['state']} readable={r1['readable_pages']} "
          f"deadline_exceeded={s.get('deadline_exceeded')} | run2 cache_hit={r2['sources'][0]['cache_hit']} "
          f"reads={len(conn.calls)}")
    # (b) research deadline only: coordinator clock moves, reader clock does not.
    cclock, rclock = Clock(), Clock()
    conn = FakeConnector({"a.example/": ok_text()}, on_exchange=lambda: setattr(cclock, "value", cclock.value + 40))
    c = coordinator(["https://a.example/"], conn, clock=cclock, reader_clock=rclock)
    r1 = c.run("q"); r2 = c.run("q")
    s1, s2 = r1["sources"][0], r2["sources"][0]
    print(f"  (b) research late:  run1 status={r1['status']} state={s1['state']} readable={r1['readable_pages']} "
          f"| run2 status={r2['status']} cache_hit={s2['cache_hit']} same observed_at="
          f"{s1.get('observed_at') == s2.get('observed_at')} reads={len(conn.calls)}")
    # (c) cancellation during the exchange.
    flag = {"v": False}
    conn = FakeConnector({"a.example/": ok_text()}, on_exchange=lambda: flag.update(v=True))
    c = coordinator(["https://a.example/"], conn)
    r1 = c.run("q", cancelled=lambda: flag["v"])
    flag["v"] = False
    r2 = c.run("q")
    print(f"  (c) cancelled:      run1 status={r1['status']} state={r1['sources'][0]['state']} "
          f"| run2 status={r2['status']} cache_hit={r2['sources'][0]['cache_hit']} reads={len(conn.calls)}")


# --- P6: cache keeps the original observation; error body never reaches the report --------
def p6_cache_and_error_body():
    section("P6 cache provenance and error body")
    clock = Clock()
    routes = {"a.example/r": (301, [("Location", "https://a.example/final")], b""), "a.example/final": ok_text()}
    conn = FakeConnector(routes)
    c = coordinator(["https://a.example/r"], conn, clock=clock)
    r1 = c.run("q"); clock.value += 10; r2 = c.run("q")
    a, b = r1["sources"][0], r2["sources"][0]
    keys = ("observed_at", "body_sha256", "body_bytes")
    print(f"  cache_hit={b['cache_hit']} identical {keys}={all(a[k] == b[k] for k in keys)} "
          f"hops_kept={a['retrieval']['hops'] == b['retrieval']['hops']} hops={len(b['retrieval']['hops'])}")
    secret = b"SECRET-ERROR-BODY-7f3a"
    for status in (429, 403, 500):
        conn = FakeConnector({"a.example/": (status, [("Content-Type", "text/plain")], secret)})
        r = coordinator(["https://a.example/"], conn).run("q")
        print(f"  {status}: body in report={secret.decode() in json.dumps(r)} state={r['sources'][0]['state']} "
              f"retrieval.kind={r['sources'][0].get('retrieval', {}).get('kind')}")


# --- P7: query string kept in final_url while hops are redacted ----------------------------
def p7_query_redaction():
    section("P7 query string in evidence")
    conn = FakeConnector({"a.example/p?token=abc123": ok_text()})
    result = fetch("https://a.example/p?token=abc123", policy=WebPolicy(), resolver=resolver, connector=conn)
    ev = result.evidence()
    print(f"  hops[0]={ev['hops'][0]['url']} (query hashed) | final_url={ev['final_url']}")


# --- P8: TLS context weakened after construction -----------------------------------------
def p8_tls_mutation():
    section("P8 TLS context mutated after StdlibConnector construction")
    free = socket.socket(); free.bind(("127.0.0.1", 0)); port = free.getsockname()[1]; free.close()
    limits = TransportLimits(connect_seconds=1, read_seconds=1, total_seconds=2)
    for name, weaken in (("verify_mode=CERT_NONE (control)", lambda c: (setattr(c, "check_hostname", False),
                                                                         setattr(c, "verify_mode", ssl.CERT_NONE))),
                         ("minimum_version=TLSv1_1", lambda c: setattr(c, "minimum_version", ssl.TLSVersion.TLSv1_1)),
                         ("set_ciphers SECLEVEL=0", lambda c: c.set_ciphers("ALL:@SECLEVEL=0")),
                         ("verify_flags cleared", lambda c: setattr(c, "verify_flags", ssl.VerifyFlags(0)))):
        ctx = ssl.create_default_context()
        connector = StdlibConnector(ssl_context=ctx)
        try:
            weaken(ctx)
        except ssl.SSLError as exc:
            print(f"  {name:34} could not apply here: {exc}")
            continue
        try:
            connector.exchange(scheme="https", host="a.example", port=port, address="127.0.0.1", target="/",
                               headers=(("Host", "a.example"),), limits=limits, deadline=time.monotonic() + 2)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:34} -> {type(exc).__name__} {getattr(exc, 'code', '')}".rstrip())


# --- local server for P9/P10 ------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/drip-body":
            body = b"x" * 40
            self.send_response(200)
            self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close"); self.end_headers(); self.wfile.flush()
            for byte in body:
                self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(0.2)
        elif self.path == "/drip-headers":
            raw = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nX-Pad: " + b"p" * 30 + b"\r\nContent-Length: 2\r\n\r\nok"
            for byte in raw:
                self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(0.15)
            self.close_connection = True
        else:
            body = TEXT
            self.send_response(200)
            self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # the drip handler loses its peer when the client gives up: expected


class LoopbackConnector(StdlibConnector):
    """Like the demo connector: the pinned public address is replaced by 127.0.0.1."""

    def exchange(self, **kwargs):
        return super().exchange(**{**kwargs, "address": "127.0.0.1"})


def p9_p10_local():
    server = QuietServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_port
    policy = WebPolicy(schemes=("http",), ports=(port,))
    try:
        section("P9 drip server vs total_seconds=1 (cooperative budget)")
        limits = TransportLimits(total_seconds=1, connect_seconds=2, read_seconds=2, max_body_bytes=128_000)
        for path in ("/drip-body", "/drip-headers"):
            start = time.monotonic()
            try:
                r = fetch(f"http://a.example:{port}{path}", policy=policy, resolver=resolver,
                          connector=LoopbackConnector(), limits=limits)
                outcome = f"returned size={r.size} deadline_exceeded={r.deadline_exceeded}"
            except Exception as exc:  # noqa: BLE001
                outcome = f"{type(exc).__name__} {getattr(exc, 'code', '')}"
            print(f"  {path:14} elapsed={time.monotonic() - start:5.1f}s for total_seconds=1 -> {outcome}")

        section("P10 injected reader clock vs StdlibConnector (fast healthy page)")
        print(f"  time.monotonic() here = {time.monotonic():.0f}")
        for label, clock in (("real monotonic", time.monotonic), ("fake clock fixed at 0", lambda: 0.0),
                             ("fake clock fixed at 1e9", lambda: 1e9)):
            reader = WebReader(resolver=resolver, connector=LoopbackConnector(), clock=clock)
            try:
                page = reader.read(f"http://a.example:{port}/ok", policy)
                outcome = f"status={page.status} bytes={len(page.body)} deadline_exceeded={page.deadline_exceeded}"
            except Exception as exc:  # noqa: BLE001
                outcome = f"{type(exc).__name__} {getattr(exc, 'code', '')}"
            print(f"  {label:26} -> {outcome}")
    finally:
        server.shutdown()


def main():
    print(f"Python {sys.version.split()[0]}; only 127.0.0.1 contacted; fake connectors elsewhere.")
    p1_rate_limit_lost(); p2_retry_after_values(); p3_redirect_and_503(); p4_redirect_to_suspended()
    p5_late_receipts(); p6_cache_and_error_body(); p7_query_redaction(); p8_tls_mutation(); p9_p10_local()
    return 0


if __name__ == "__main__":
    sys.exit(main())
