# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g028.py
# Description : Contre-revue disponibilité des pauses, contenus en double et découverte (C-TASK-G028)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run on base c3d7bf7 and target 8983d35 (frozen copies):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree>/eidolon-core/src:<tree>/eidolon-core \
        python docs/validation/2026-10-06/claude-g028/probes_g028.py
No network: real WebReader/fetch with simulated DNS and HTTP peer, or injected reader."""
import json, sqlite3, sys, tempfile, time
from pathlib import Path

from eidolon_core.research import AccessFailure, Hit, Page, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import ResearchPauses, origin_scope, provider_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse


def section(t): print(f"\n== {t}")


def outcome(fn):
    try:
        r = fn()
        if isinstance(r, dict) and "sources" in r:
            return f"report {[s['state'] for s in r['sources']]} status={r['status']} readable={r['readable_pages']} discovery={r.get('discovery_status')}"
        return repr(r)[:90]
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:70]}"


class Provider:
    def __init__(self, pid, hits): self.provider_id, self.hits, self.calls = pid, hits, 0
    def search(self, query, limit):
        self.calls += 1
        if isinstance(self.hits, Exception): raise self.hits
        return self.hits


class Connector:
    def __init__(self, script): self.script, self.calls = script, []
    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append(host + target)
        return RawResponse(*self.script[host + target.split("?")[0]], True)


def body(t): return (200, (("Content-Type", "text/plain"),), t)
dns = lambda h, p: ["93.184.215.10"]
def hit(url, title="t"): return Hit(url, title)


def co(hits, connector, pauses=None, providers=None, **kw):
    return ResearchCoordinator(providers or [Provider("p", hits)], WebReader(dns, connector), resolver=dns, pauses=pauses, **kw)


def fill(p, n, prefix="h"):
    for i in range(0, n - 1, 2):
        p.pause([origin_scope(f"{prefix}{i}.example", 443), origin_scope(f"{prefix}{i+1}.example", 443)], reason="ACCESS_DENIED")
    if n % 2:
        p.pause([origin_scope(f"{prefix}odd.example", 443)], reason="ACCESS_DENIED")


def release(p, host):
    r = p.active(origin_scope(host, 443)); return p.release(r["id"], expected_revision=r["revision"], actor="op", reason="probe")


def p1_capacity():
    section("1 capacity counted on ACTIVE pauses")
    temp = Path(tempfile.mkdtemp()); path = temp / "p.sqlite3"; p = ResearchPauses(path)
    p.pause([provider_scope("p")], reason="RATE_LIMITED", retry_after=0); r = p.active(provider_scope("p"))
    p.release(r["id"], expected_revision=r["revision"], actor="op", reason="x")
    fill(p, 256)
    c = Connector({"new.example/a": body(b"texte"), "h0.example/a": body(b"texte h0")})
    print(f"  256 ACTIVE + provider RELEASED: new origin -> {outcome(lambda: co([hit('https://new.example/a')], c, ResearchPauses(path)).run('q'))} exchanges={len(c.calls)}")
    rec = release(p, "h0.example")
    print(f"  release h0 (request_sent={rec['request_sent']}), no automatic call: exchanges={len(c.calls)}")
    print(f"  then new origin -> {outcome(lambda: co([hit('https://new.example/a')], c, ResearchPauses(path)).run('q'))} exchanges={len(c.calls)}")
    rows = {r['scope'].get('host') or r['scope'].get('provider_id'): (r['status'], r['revision']) for r in p.inspect()['pauses']}
    print(f"  rows kept: h0={rows.get('h0.example')} provider p={rows.get('p')} total rows={len(rows)} audit events={p.inspect()['audit_events']}")
    # Re-observing a RELEASED scope consumes a slot again and invalidates the release revision.
    release(p, "h1.example"); old = [r for r in p.inspect()['pauses'] if r['scope'].get('host') == 'h1.example'][0]
    p.pause([origin_scope("h1.example", 443)], reason="ACCESS_DENIED")
    now = p.active(origin_scope("h1.example", 443))
    print(f"  re-observed RELEASED h1: ACTIVE rev {old['revision']}->{now['revision']} | release with old revision -> "
          f"{outcome(lambda: p.release(now['id'], expected_revision=old['revision'], actor='op', reason='x'))}")
    full = outcome(lambda: p.pause([origin_scope("one-more.example", 443)], reason="ACCESS_DENIED"))
    print(f"  255 ACTIVE (h0 released, h1 re-observed), one more new pause -> {full[:60]}")
    # Redirect needing two new scopes with exactly one free slot.
    release(p, "h2.example")
    c2 = Connector({"fresh.example/a": (302, (("Location", "https://mirror2.example/b"),), b""), "mirror2.example/b": (429, (("Retry-After", "30"),), b"")})
    print(f"  one free slot, redirect needing 2 -> {outcome(lambda: co([hit('https://fresh.example/a')], c2, ResearchPauses(path)).run('q'))} exchanges={c2.calls}")
    # Preflight refusal twice in the same coordinator: same diagnosis, no false 'prior write uncertain'.
    fill_path = temp / "f.sqlite3"; f = ResearchPauses(fill_path); fill(f, 256)
    c3 = Connector({"x.example/a": body(b"x")}); same = co([hit("https://x.example/a")], c3, ResearchPauses(fill_path))
    print(f"  same coordinator, two preflight refusals: {outcome(lambda: same.run('q'))} | {outcome(lambda: same.run('q'))}")
    # Write refusal after an exchange (another writer took the last slot): conservative latch kept.
    w_path = temp / "w.sqlite3"; w = ResearchPauses(w_path); fill(w, 255)
    class Racing(Connector):
        def exchange(self, **kw):
            ResearchPauses(w_path).pause([origin_scope("other.example", 443)], reason="ACCESS_DENIED")
            return super().exchange(**kw)
    c4 = Racing({"race.example/a": (429, (("Retry-After", "30"),), b"")}); racing = co([hit("https://race.example/a")], c4, ResearchPauses(w_path))
    print(f"  last slot taken during the exchange: {outcome(lambda: racing.run('q'))} | next run same coordinator: {outcome(lambda: racing.run('q'))}")
    # Real storage failure keeps the latch.
    s_path = temp / "s.sqlite3"; ResearchPauses(s_path); c5 = Connector({"y.example/a": body(b"y")}); broken = co([hit("https://y.example/a")], c5, ResearchPauses(s_path))
    s_path.unlink()
    print(f"  storage gone: {outcome(lambda: broken.run('q'))} | next: {outcome(lambda: broken.run('q'))}")
    # History growth: every check scans all rows (no retention).
    h_path = temp / "h.sqlite3"; h = ResearchPauses(h_path)
    for i in range(0, 4000, 2):
        h.pause([origin_scope(f"k{i}.example", 443), origin_scope(f"k{i+1}.example", 443)], reason="ACCESS_DENIED")
        for host in (f"k{i}.example", f"k{i+1}.example"):
            release(h, host)
    t0 = time.perf_counter(); h.check_capacity([origin_scope("new.example", 443)]); dt = time.perf_counter() - t0
    print(f"  4000 RELEASED rows kept: one check_capacity takes {dt*1000:.0f} ms (scans and decodes every row)")


def p2_content():
    section("2 counting identical content once, keeping every receipt")
    same = b"Contenu identique G028."
    for label, urls, script in (
        ("tracking parameter", ["https://news.example/a", "https://news.example/a?utm_source=x"], {"news.example/a": body(same)}),
        ("functional parameter", ["https://news.example/item?id=1", "https://news.example/item?id=2"], {"news.example/item": body(same)}),
        ("two domains (mirror)", ["https://news.example/a", "https://mirror.example/a"], {"news.example/a": body(same), "mirror.example/a": body(same)}),
        ("redirect to an already read final", ["https://news.example/a", "https://short.example/x"],
         {"news.example/a": body(same), "short.example/x": (302, (("Location", "https://news.example/a"),), b"")}),
        ("nearly identical (one space)", ["https://news.example/a", "https://mirror.example/a"], {"news.example/a": body(same), "mirror.example/a": body(same + b" ")})):
        c = Connector(script)
        r = co([hit(u) for u in urls], c).run("q", required_pages=2)
        print(f"  {label:34} exchanges={len(c.calls)} sent={[x.split('/',1)[1] for x in c.calls]} states={[s['state'] for s in r['sources']]} "
              f"readable={r['readable_pages']} status={r['status']} dup_of={'set' if any(s.get('duplicate_of') for s in r['sources']) else None}")
    # Same URL, different bodies across runs: cache, then a changed body.
    c = Connector({"news.example/a": body(b"version 1")}); coord = co([hit("https://news.example/a")], c)
    a = coord.run("q"); c.script["news.example/a"] = body(b"version 2"); b = coord.run("q")
    print(f"  same URL, body changed between runs (cache) -> run2 cache_hit={b['sources'][0]['cache_hit']} text={b['sources'][0].get('text')!r}")
    # Same body served by a cached first source and a fresh second one.
    c = Connector({"news.example/a": body(same), "mirror.example/a": body(same)}); coord = co([hit("https://news.example/a")], c)
    coord.run("q"); coord.providers[0].hits = [hit("https://news.example/a"), hit("https://mirror.example/a")]
    r = coord.run("q", required_pages=2)
    print(f"  cached source + fresh mirror: states={[s['state'] for s in r['sources']]} cache_hit={[s['cache_hit'] for s in r['sources']]} readable={r['readable_pages']}")


def p3_discovery():
    section("3 discovery_status")
    ok = Connector({"news.example/a": body(b"x")})
    for label, providers, kw in (
        ("all EMPTY", [Provider("a", []), Provider("b", [])], {}),
        ("all down", [Provider("a", AccessFailure("UNAVAILABLE")), Provider("b", AccessFailure("TIMEOUT"))], {}),
        ("one EMPTY, one down", [Provider("a", []), Provider("b", AccessFailure("UNAVAILABLE"))], {}),
        ("invalid result", [Provider("a", ["not a hit"])], {}),
        ("hits found, read fails", [Provider("a", [hit("https://dead.example/a")])], {}),
        ("provider budget (3 configured, limit 2), all EMPTY", [Provider("a", []), Provider("b", []), Provider("c", [])], {"limits": ResearchLimits(providers=2)}),
        ("cancelled before search", [Provider("a", [])], {"cancel": True}),
        ("provider paused", [Provider("p", [])], {"paused": True})):
        temp = Path(tempfile.mkdtemp()); pauses = ResearchPauses(temp / "p.sqlite3")
        if kw.get("paused"): pauses.pause([provider_scope("p")], reason="RATE_LIMITED", retry_after=60)
        coord = ResearchCoordinator(providers, WebReader(dns, Connector({})), resolver=dns, pauses=pauses, limits=kw.get("limits"))
        r = outcome(lambda: coord.run("q", cancelled=(lambda: True) if kw.get("cancel") else (lambda: False)))
        print(f"  {label:50} {r}")


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | tree {Path(__import__('eidolon_core').__file__).parents[3].name}")
    for probe in (p1_capacity, p2_content, p3_discovery):
        try:
            probe()
        except Exception as exc:  # the base tree may refuse a setup step the target accepts
            print(f"  probe stopped: {type(exc).__name__}: {str(exc)[:90]}")
