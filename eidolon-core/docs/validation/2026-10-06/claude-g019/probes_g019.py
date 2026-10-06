# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g019.py
# Description : Sondes indépendantes des suspensions Web persistantes C-002c (C-TASK-G019)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G019 against the frozen target dc16ce1.

From eidolon-core/, with a frozen copy of dc16ce1 (git archive):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen>/eidolon-core/src:<frozen>/eidolon-core \
        python docs/validation/2026-10-06/claude-g019/probes_g019.py

No Internet: the real WebReader/fetch gets a simulated resolver and connector
that count every exchange. Pause storage is a temporary SQLite file; faults are
a deleted file, a raw-SQL corrupted record, a write lock held by another
process, a full table, and injected clocks. Provider/hit come from the frozen
tests. research-release is only called on these synthetic copies.
"""
import json
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import PauseStorageError, ResearchPauses, origin_scope, provider_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_research import Provider

SECRET_QUERY = "secret query G019 do-not-store"
PRIVATE_BODY = b"PRIVATE-BODY-G019"


def section(title):
    print(f"\n== {title}")


def outcome(fn):
    try:
        r = fn()
        if isinstance(r, dict) and "sources" in r:
            return "report " + ",".join(s["state"] for s in r["sources"]) + f" status={r['status']}"
        return repr(r)[:110]
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:80]}"


class Connector:
    def __init__(self, script):
        self.script, self.calls = script, []

    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append(host)
        status, hdrs, body = self.script[host] if not callable(self.script) else self.script(host)
        return RawResponse(status, hdrs, body, True)


def public(host, port):
    return ["9.9.9.9"]


def hit(host="docs.example", path="a"):
    return Hit(f"https://{host}/{path}", "Synthetic reference")


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def coordinator(connector, pauses, hits=None, **kw):
    return ResearchCoordinator([Provider("p", hits or [hit()])], WebReader(kw.pop("resolver", public), connector),
                               resolver=kw.pop("dns", public), pauses=pauses, **kw)


# --- 1. persistence, minimum delays, stale revision, new refusal, audit ---------------------------
def p1_persistence():
    section("1 pause survives reconstruction; delays, stale revision, new refusal after release, audit")
    temp = Path(tempfile.mkdtemp(prefix="g019-")); clock = Clock()
    pauses = ResearchPauses(temp / "research-pauses.sqlite3", clock=clock)
    c = Connector({"docs.example": (429, (("Retry-After", "30"),), PRIVATE_BODY)})
    r1 = coordinator(c, pauses).run(SECRET_QUERY)
    rebuilt = ResearchPauses(temp / "research-pauses.sqlite3", clock=clock)
    r2 = coordinator(c, rebuilt).run(SECRET_QUERY)
    rec = rebuilt.active(origin_scope("docs.example", 443))
    print(f"  429 RA=30: run1 {r1['sources'][0]['state']} | rebuilt run2 {r2['sources'][0]['state']} | exchanges={len(c.calls)} "
          f"| not_before-observed={(rec['not_before_ms'] - rec['observed_at_ms']) // 1000}s rev={rec['revision']}")
    print(f"  release at +10 s -> {outcome(lambda: rebuilt.release(rec['id'], expected_revision=rec['revision'], actor='op', reason='probe'))}")
    clock.t += 10
    rebuilt.pause([origin_scope("docs.example", 443)], reason="RATE_LIMITED", retry_after=5)  # shorter delay observed later
    rec2 = rebuilt.active(origin_scope("docs.example", 443))
    print(f"  later 429 RA=5 keeps the longest known minimum: not_before still +{(rec2['not_before_ms'] - rec['observed_at_ms']) // 1000}s from first, rev={rec2['revision']}")
    clock.t += 25
    print(f"  release with the OLD revision -> {outcome(lambda: rebuilt.release(rec['id'], expected_revision=rec['revision'], actor='op', reason='probe'))}")
    released = rebuilt.release(rec2["id"], expected_revision=rec2["revision"], actor="op-G019", reason="reviewed G019")
    print(f"  release with current revision -> {json.dumps(released)} | exchanges during release: {len(c.calls) - 1}")
    c.script["docs.example"] = (403, (), PRIVATE_BODY)
    r3 = coordinator(c, rebuilt).run(SECRET_QUERY)
    rec3 = rebuilt.active(origin_scope("docs.example", 443))
    r4 = coordinator(c, ResearchPauses(temp / "research-pauses.sqlite3", clock=clock)).run(SECRET_QUERY)
    print(f"  after release: run3 {r3['sources'][0]['state']} (1 new exchange) -> new pause {rec3['reason']} rev={rec3['revision']} "
          f"| run4 {r4['sources'][0]['state']} | exchanges total={len(c.calls)}")
    inspect = rebuilt.inspect()
    raw = (temp / "research-pauses.sqlite3").read_bytes()
    with sqlite3.connect(temp / "research-pauses.sqlite3") as db:
        kinds = [k for (k,) in db.execute("SELECT kind FROM pause_events ORDER BY sequence")]
    print(f"  audit events={inspect['audit_events']} kinds={kinds} | query text in pause DB={SECRET_QUERY.encode() in raw} "
          f"body in pause DB={PRIVATE_BODY in raw} | body or query in reports={PRIVATE_BODY.decode() in json.dumps([r1, r2, r3, r4]) or SECRET_QUERY in json.dumps([r1, r2, r3, r4])}")

    for label, header in (("429 ambiguous Retry-After", (("Retry-After", "soon-ish"),)), ("503 ambiguous Retry-After", (("Retry-After", "soon-ish"),))):
        status = 429 if label.startswith("429") else 503
        p = ResearchPauses(temp / f"amb-{status}.sqlite3", clock=clock)
        cc = Connector({"docs.example": (status, header, b"")})
        coordinator(cc, p).run("q")
        r = p.active(origin_scope("docs.example", 443))
        print(f"  {label}: reason={r['reason']} review_required={r['review_required']} not_before={'+%ds' % ((r['not_before_ms'] - r['observed_at_ms']) // 1000) if r['not_before_ms'] else None} "
              f"| immediate release -> {outcome(lambda: p.release(r['id'], expected_revision=r['revision'], actor='op', reason='x'))}")

    p = ResearchPauses(temp / "provider.sqlite3", clock=clock)
    prov = Provider("p", AccessFailure("RATE_LIMITED", 120))
    for _ in range(2):
        ResearchCoordinator([prov], WebReader(public, Connector({})), resolver=public, pauses=ResearchPauses(temp / "provider.sqlite3", clock=clock)).run("q")
    print(f"  provider 429 RA=120: provider searched {prov.calls} time(s) over two rebuilt coordinators | paused={bool(p.active(provider_scope('p')))}")
    shutil.rmtree(temp)


# --- 2. redirect: atomic initial/final, blocked hop, capacity ------------------------------------
def p2_redirect_capacity():
    section("2 redirect origins, blocked hop before connection, capacity without eviction")
    temp = Path(tempfile.mkdtemp(prefix="g019-")); clock = Clock()
    pauses = ResearchPauses(temp / "p.sqlite3", clock=clock)
    c = Connector({"docs.example": (302, (("Location", "https://mirror.example/a"),), b""),
                   "mirror.example": (429, (("Retry-After", "30"),), b"")})
    coordinator(c, pauses).run("q")
    with sqlite3.connect(temp / "p.sqlite3") as db:
        observed = db.execute("SELECT count(*), count(DISTINCT at_ms) FROM pause_events WHERE kind='OBSERVED'").fetchone()
    print(f"  302 -> mirror 429: exchanges={c.calls} paused docs={bool(pauses.active(origin_scope('docs.example', 443)))} "
          f"mirror={bool(pauses.active(origin_scope('mirror.example', 443)))} | OBSERVED events={observed[0]} same timestamp={observed[1] == 1}")
    # Redirect INTO a paused origin from a fresh one: the hop must stop before connecting.
    c2 = Connector({"fresh.example": (302, (("Location", "https://mirror.example/b"),), b""),
                    "mirror.example": (200, (("Content-Type", "text/plain"),), b"should not be read")})
    r = coordinator(c2, pauses, hits=[hit("fresh.example")]).run("q")
    print(f"  fresh -> 302 -> paused mirror: exchanges={c2.calls} source={r['sources'][0]['state']}")

    # Capacity: 256 records exist (released ones included).
    full = ResearchPauses(temp / "full.sqlite3", clock=clock)
    for i in range(128):
        full.pause([origin_scope(f"h{i}.example", 443), origin_scope(f"g{i}.example", 443)], reason="ACCESS_DENIED")
    rec = full.active(origin_scope("h0.example", 443))
    full.release(rec["id"], expected_revision=rec["revision"], actor="op", reason="released, still counted")
    c3 = Connector({"new.example": (429, (("Retry-After", "30"),), b"")})
    runs = [outcome(lambda: coordinator(c3, ResearchPauses(temp / "full.sqlite3", clock=clock), hits=[hit("new.example")]).run("q")) for _ in range(2)]
    print(f"  table full (256, one released): run1 -> {runs[0]} | rebuilt run2 -> {runs[1]} | exchanges with the refusing origin={len(c3.calls)}")
    c4 = Connector({"ok.example": (200, (("Content-Type", "text/plain"),), b"public text")})
    print(f"  table full, an origin that does not refuse -> {outcome(lambda: coordinator(c4, ResearchPauses(temp / 'full.sqlite3', clock=clock), hits=[hit('ok.example')]).run('q'))}")
    shutil.rmtree(temp)


# --- 3. storage absent / corrupt / locked ---------------------------------------------------------
def _hold(path, seconds, ready):
    db = sqlite3.connect(path, timeout=5)
    db.execute("BEGIN IMMEDIATE")
    ready.set()
    time.sleep(seconds)
    db.rollback()


class FlakyPauses(ResearchPauses):
    """Second 'active' lookup (the before_hop check inside the reader) fails like storage."""
    calls = 0

    def active(self, scope):
        FlakyPauses.calls += 1
        if FlakyPauses.calls == 2:
            raise PauseStorageError("PAUSE_STORAGE_UNAVAILABLE")
        return super().active(scope)


def p3_storage():
    section("3 storage absent, corrupt, failing inside the reader hop check, locked after the response")
    temp = Path(tempfile.mkdtemp(prefix="g019-"))
    prov = Provider("p", [hit()])
    c = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text")})
    pauses = ResearchPauses(temp / "p.sqlite3")
    co = ResearchCoordinator([prov], WebReader(public, c), resolver=public, pauses=pauses)
    (temp / "p.sqlite3").unlink()
    print(f"  file deleted -> {outcome(lambda: co.run('q'))} | again same coordinator -> {outcome(lambda: co.run('q'))} "
          f"| provider searches={prov.calls} exchanges={len(c.calls)} recreated={(temp / 'p.sqlite3').exists()}")
    p = ResearchPauses(temp / "c.sqlite3")
    p.pause([origin_scope("docs.example", 443)], reason="ACCESS_DENIED")
    with sqlite3.connect(temp / "c.sqlite3") as db:
        db.execute("UPDATE pauses SET body='{not json'")
    print(f"  corrupt record -> {outcome(lambda: coordinator(c, ResearchPauses(temp / 'c.sqlite3')).run('q'))} | exchanges={len(c.calls)}")
    (temp / "g.sqlite3").write_bytes(b"garbage" * 50)
    print(f"  garbage file -> {outcome(lambda: ResearchPauses(temp / 'g.sqlite3'))}")

    FlakyPauses.calls = 0
    c5 = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text")})
    co = coordinator(c5, FlakyPauses(temp / "f.sqlite3"), hits=[hit(), hit(path="b")])
    print(f"  storage fails in the reader's hop check -> {outcome(lambda: co.run('q'))} | exchanges={len(c5.calls)} | next run -> {outcome(lambda: co.run('q'))}")

    ctx = mp.get_context("spawn")
    path = temp / "l.sqlite3"
    ResearchPauses(path)
    c6 = Connector({"docs.example": (429, (("Retry-After", "30"),), b"")})
    ready = ctx.Event()
    holder = None

    def script(host):
        nonlocal holder
        holder = ctx.Process(target=_hold, args=(str(path), 7, ready)); holder.start(); ready.wait(20)
        return (429, (("Retry-After", "30"),), b"")
    c6.script = script
    first = outcome(lambda: coordinator(c6, ResearchPauses(path)).run("q"))
    holder.join(15)
    c6.script = {"docs.example": (429, (("Retry-After", "30"),), b"")}
    second = outcome(lambda: coordinator(c6, ResearchPauses(path)).run("q"))
    print(f"  pause DB locked >5 s right after a 429 -> {first} | rebuilt coordinator -> {second} | exchanges={len(c6.calls)}")
    shutil.rmtree(temp)


# --- 4. release sends nothing; policy still applies; slow lookup vs budget; clocks -----------------
class SlowPauses(ResearchPauses):
    """Each lookup 'takes' 6 s of the coordinator's monotonic clock (slow storage)."""
    def __init__(self, path, budget_clock, **kw):
        super().__init__(path, **kw)
        self.budget_clock = budget_clock

    def active(self, scope):
        self.budget_clock.t += 6
        return super().active(scope)


def p4_release_budget_clocks():
    section("4 release, policy after release, slow lookups vs the research budget, wall clock")
    temp = Path(tempfile.mkdtemp(prefix="g019-")); clock = Clock()
    pauses = ResearchPauses(temp / "p.sqlite3", clock=clock)
    pauses.pause([origin_scope("docs.example", 443)], reason="ACCESS_DENIED")
    rec = pauses.active(origin_scope("docs.example", 443))
    c = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text")})
    pauses.release(rec["id"], expected_revision=rec["revision"], actor="op", reason="probe")
    private = lambda host, port: ["10.1.2.3"]
    r = coordinator(c, pauses, resolver=private, dns=private).run("q")
    print(f"  released, but the origin now resolves private -> {r['sources'][0]['state']} reason={r['sources'][0].get('reason')} exchanges={len(c.calls)}")

    for label, budget in (("budget 10 s", 10), ("budget 13 s", 13)):
        mono = Clock(100.0)
        c2 = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text")})
        sp = SlowPauses(temp / f"slow-{budget}.sqlite3", mono)
        r = ResearchCoordinator([Provider("p", [hit()])], WebReader(public, c2, clock=mono), resolver=public, pauses=sp,
                                limits=ResearchLimits(seconds=budget), clock=mono).run("q")
        print(f"  each lookup costs 6 s, {label}: exchanges={len(c2.calls)} source={r['sources'][0]['state']} status={r['status']} "
              f"elapsed={mono.t - 100:.0f}s")

    wall = Clock()
    p = ResearchPauses(temp / "w.sqlite3", clock=wall)
    p.pause([origin_scope("docs.example", 443)], reason="RATE_LIMITED", retry_after=3600)
    rec = p.active(origin_scope("docs.example", 443))
    wall.t -= 120
    back = outcome(lambda: p.pause([origin_scope("docs.example", 443)], reason="RATE_LIMITED"))
    rel_back = outcome(lambda: p.release(rec["id"], expected_revision=rec["revision"], actor="op", reason="x"))
    wall.t += 120 + 3600 + 1
    print(f"  wall clock back 120 s: new observation -> {back} | release -> {rel_back}")
    print(f"  wall clock forward past the minimum: active still={bool(p.active(origin_scope('docs.example', 443)))} (no automatic release) "
          f"| explicit release -> {outcome(lambda: p.release(rec['id'], expected_revision=rec['revision'], actor='op', reason='x')['status'])}")
    shutil.rmtree(temp)


# --- 5. cache and cancellation ---------------------------------------------------------------------
def p5_cache_cancel():
    section("5 cache and cancellation")
    temp = Path(tempfile.mkdtemp(prefix="g019-"))
    pauses = ResearchPauses(temp / "p.sqlite3")
    c = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text")})
    co = coordinator(c, pauses)
    co.run("q")
    ResearchPauses(temp / "p.sqlite3").pause([origin_scope("docs.example", 443)], reason="ACCESS_DENIED")  # seen by another coordinator
    r = co.run("q")
    s = r["sources"][0]
    print(f"  origin paused after a cached read: same coordinator -> {s['state']} cache_hit={s['cache_hit']} exchanges={len(c.calls)} "
          f"| new coordinator -> {coordinator(c, pauses).run('q')['sources'][0]['state']} exchanges={len(c.calls)}")
    c2 = Connector({"docs.example": (302, (("Location", "https://mirror.example/a"),), b""),
                    "mirror.example": (200, (("Content-Type", "text/plain"),), b"x")})
    flag = {"n": 0}

    def cancelled():
        flag["n"] += 1
        return bool(c2.calls)  # becomes true right after the first hop
    r = coordinator(c2, ResearchPauses(temp / "q.sqlite3")).run("q", cancelled=cancelled)
    print(f"  cancelled after the first hop: exchanges={c2.calls} source={r['sources'][0]['state']} status={r['status']}")
    shutil.rmtree(temp)


def p6_cli():
    section("6 CLI on the synthetic copy")
    temp = Path(tempfile.mkdtemp(prefix="g019-"))
    p = ResearchPauses(temp / "research-pauses.sqlite3")
    p.pause([origin_scope("docs.example", 443)], reason="ACCESS_DENIED")
    rec = p.active(origin_scope("docs.example", 443))
    def cli(*args):
        r = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(temp), *args], capture_output=True, text=True, timeout=60, env=os.environ)
        return f"exit={r.returncode} traceback={'Traceback' in r.stderr} | {(r.stdout or r.stderr).strip()[:120]}"
    print(f"  research-pauses           {cli('research-pauses')[:60]}")
    print(f"  release, stale revision   {cli('research-release', rec['id'], '--revision', str(rec['revision'] + 5), '--actor', 'op', '--reason', 'x')}")
    print(f"  release, current revision {cli('research-release', rec['id'], '--revision', str(rec['revision']), '--actor', 'op', '--reason', 'x')}")
    empty = Path(tempfile.mkdtemp(prefix="g019-"))
    r = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(empty), "research-pauses"], capture_output=True, text=True, timeout=60, env=os.environ)
    print(f"  research-pauses, no DB    exit={r.returncode} created={(empty / 'research-pauses.sqlite3').exists()} | {r.stderr.strip()[:90]}")
    shutil.rmtree(temp); shutil.rmtree(empty)


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version}")
    for probe in (p1_persistence, p2_redirect_capacity, p3_storage, p4_release_budget_clocks, p5_cache_cancel, p6_cli):
        probe()
