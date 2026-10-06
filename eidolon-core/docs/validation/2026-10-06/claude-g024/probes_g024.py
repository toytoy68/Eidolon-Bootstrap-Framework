# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g024.py
# Description : Contre-revue de cd80be2 : budget, capacité des pauses, mission_id (C-TASK-G024)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run on base e2d01ff and target cd80be2 (frozen copies, git archive):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree>/eidolon-core/src:<tree>/eidolon-core \
        python docs/validation/2026-10-06/claude-g024/probes_g024.py

No network: real WebReader/fetch with a simulated resolver and HTTP peer that
counts exchanges. Pause storage in temporary SQLite files. Clocks injected.
"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile
from pathlib import Path

from eidolon_core.commands import CANCEL_PROTOCOL, PROTOCOL, parse_cancel_command, parse_command
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import ResearchPauses, origin_scope, provider_scope
from eidolon_core.store import Store
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_research import Provider


def section(t): print(f"\n== {t}")


def outcome(fn):
    try:
        r = fn()
        if isinstance(r, dict) and "sources" in r:
            return "report " + ",".join(s["state"] for s in r["sources"]) + f" status={r['status']}"
        return repr(r)[:90]
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:80]}"


class Connector:
    def __init__(self, script, during=None):
        self.script, self.calls, self.during = script, [], during
    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append(host)
        if self.during: self.during(host)
        status, hdrs, body = self.script[host]
        return RawResponse(status, hdrs, body, True)


def public(host, port): return ["9.9.9.9"]
def hit(host="docs.example", path="a"): return Hit(f"https://{host}/{path}", "Synthetic reference")
TEXT = (200, (("Content-Type", "text/plain"),), b"public text")


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


class SlowPauses(ResearchPauses):
    """Every durable lookup 'costs' 6 s on the coordinator's monotonic clock; optional cancel flag."""
    def __init__(self, path, mono, on_lookup=None, **kw):
        super().__init__(path, **kw); self.mono, self.on_lookup = mono, on_lookup
    def active(self, scope):
        self.mono.t += 6
        if self.on_lookup: self.on_lookup()
        return super().active(scope)


def co(connector, pauses, hits=None, **kw):
    return ResearchCoordinator([Provider("p", hits or [hit()])], WebReader(public, connector, clock=kw.get("clock", __import__("time").monotonic)),
                               resolver=public, pauses=pauses, **kw)


def p1_budget():
    section("1 D-G019-1: slow pause lookup before an HTTP hop; budget and cancellation")
    for label, budget, redirect in (("budget 13 s, direct", 13, False), ("budget 19 s, via redirect", 19, True), ("budget 60 s (normal read)", 60, False)):
        temp = Path(tempfile.mkdtemp(prefix="g024-")); mono = Clock(100.0)
        script = {"docs.example": (302, (("Location", "https://mirror.example/a"),), b"") if redirect else TEXT, "mirror.example": TEXT}
        c = Connector(script)
        r = co(c, SlowPauses(temp / "p.sqlite3", mono), limits=ResearchLimits(seconds=budget), clock=mono).run("q")
        print(f"  {label:26} exchanges={c.calls} source={r['sources'][0]['state']} status={r['status']} elapsed={mono.t - 100:.0f}s")
        shutil.rmtree(temp)
    temp = Path(tempfile.mkdtemp(prefix="g024-")); mono = Clock(100.0); flag = {"cancel": False, "n": 0}
    def lookup():
        flag["n"] += 1
        if flag["n"] == 3: flag["cancel"] = True  # cancellation observed during the hop's own lookup
    c = Connector({"docs.example": TEXT})
    r = co(c, SlowPauses(temp / "p.sqlite3", mono, lookup), clock=mono).run("q", cancelled=lambda: flag["cancel"])
    print(f"  cancel during the hop lookup: exchanges={c.calls} source={r['sources'][0]['state']} status={r['status']}")
    shutil.rmtree(temp)
    # A refusal already received is kept even if the budget is exceeded during the exchange.
    temp = Path(tempfile.mkdtemp(prefix="g024-")); mono = Clock(100.0); p = ResearchPauses(temp / "p.sqlite3")
    c = Connector({"docs.example": (429, (("Retry-After", "30"),), b"")}, during=lambda h: setattr(mono, "t", mono.t + 100))
    r = co(c, p, limits=ResearchLimits(seconds=30), clock=mono).run("q")
    print(f"  429 received while the budget expires: source={r['sources'][0]['state']} status={r['status']} paused={bool(p.active(origin_scope('docs.example', 443)))}")
    shutil.rmtree(temp)


def full_table(path, keep=256, release_first=True):
    p = ResearchPauses(path)
    for i in range(keep // 2):
        p.pause([origin_scope(f"h{i}.example", 443), origin_scope(f"g{i}.example", 443)], reason="ACCESS_DENIED")
    if keep % 2:
        p.pause([origin_scope("odd.example", 443)], reason="ACCESS_DENIED")
    if release_first:
        r = p.active(origin_scope("h0.example", 443)); p.release(r["id"], expected_revision=r["revision"], actor="op", reason="released")
    return p


def p2_capacity():
    section("2 L-G019-1: capacity exhausted (256 rows, one RELEASED)")
    temp = Path(tempfile.mkdtemp(prefix="g024-")); full_table(temp / "full.sqlite3")
    c = Connector({"new.example": (429, (("Retry-After", "30"),), b""), "h0.example": TEXT, "g1.example": TEXT})
    runs = [outcome(lambda: co(c, ResearchPauses(temp / "full.sqlite3"), hits=[hit("new.example")]).run("q")) for _ in range(2)]
    print(f"  new refusing origin, two rebuilt coordinators: {runs} | exchanges={c.calls}")
    print(f"  known RELEASED origin h0 (no new row needed) -> {outcome(lambda: co(c, ResearchPauses(temp / 'full.sqlite3'), hits=[hit('h0.example')]).run('q'))}")
    print(f"  known ACTIVE origin g1 -> {outcome(lambda: co(c, ResearchPauses(temp / 'full.sqlite3'), hits=[hit('g1.example')]).run('q'))} | exchanges={c.calls}")
    same = co(c, ResearchPauses(temp / "full.sqlite3"), hits=[hit("new.example")])
    first = outcome(lambda: same.run("q"))
    print(f"  same coordinator after a capacity refusal, then a known origin -> {first} | {outcome(lambda: same.run('q'))}")
    prov = Provider("fresh-provider", [hit("h0.example")])
    r = outcome(lambda: ResearchCoordinator([prov], WebReader(public, c), resolver=public, pauses=ResearchPauses(temp / "full.sqlite3")).run("q"))
    print(f"  new provider with a full table -> {r} | provider searched={prov.calls}")
    shutil.rmtree(temp)

    temp = Path(tempfile.mkdtemp(prefix="g024-")); full_table(temp / "f.sqlite3", keep=255, release_first=False)
    c = Connector({"fresh.example": (302, (("Location", "https://mirror.example/a"),), b""), "mirror.example": (429, (("Retry-After", "30"),), b"")})
    r = outcome(lambda: co(c, ResearchPauses(temp / "f.sqlite3"), hits=[hit("fresh.example")]).run("q"))
    print(f"  255 rows, redirect fresh -> mirror (needs 2 rows): {r} | exchanges={c.calls}")
    c2 = Connector({"solo.example": (302, (("Location", "https://solo.example/b"),), b"")})
    c2.script["solo.example"] = (429, (("Retry-After", "30"),), b"")
    r2 = outcome(lambda: co(c2, ResearchPauses(temp / "f.sqlite3"), hits=[hit("solo.example")]).run("q"))
    print(f"  255 rows, single new origin refusing (needs 1 row) -> {r2} | exchanges={c2.calls} | rows now={len(ResearchPauses(temp / 'f.sqlite3').inspect()['pauses'])}")
    shutil.rmtree(temp)

    # Check then pause is not a reservation: another writer takes the last row during the exchange.
    temp = Path(tempfile.mkdtemp(prefix="g024-")); p = full_table(temp / "r.sqlite3", keep=255, release_first=False)
    c = Connector({"race.example": (429, (("Retry-After", "30"),), b"")},
                  during=lambda h: ResearchPauses(temp / "r.sqlite3").pause([origin_scope("other.example", 443)], reason="ACCESS_DENIED"))
    r = outcome(lambda: co(c, ResearchPauses(temp / "r.sqlite3"), hits=[hit("race.example")]).run("q"))
    again = outcome(lambda: co(c, ResearchPauses(temp / "r.sqlite3"), hits=[hit("race.example")]).run("q"))
    print(f"  last row taken by another writer during the exchange: {r} | rebuilt -> {again} | exchanges={c.calls}")
    shutil.rmtree(temp)

    temp = Path(tempfile.mkdtemp(prefix="g024-")); ResearchPauses(temp / "s.sqlite3")
    c = Connector({"docs.example": TEXT}); coord = co(c, ResearchPauses(temp / "s.sqlite3"))
    (temp / "s.sqlite3").unlink()
    print(f"  storage gone before the capacity check -> {outcome(lambda: coord.run('q'))} | exchanges={c.calls}")
    for bad in ([], [origin_scope("a.example", 443)] * 3, "x"):
        print(f"  check_capacity({str(bad)[:30]}) -> {outcome(lambda: ResearchPauses(temp / 't.sqlite3').check_capacity(bad))}")
    shutil.rmtree(temp)


def p2b_known_scopes():
    section("2b full table: known origin with and without a row for the provider")
    temp = Path(tempfile.mkdtemp(prefix="g024-")); p = ResearchPauses(temp / "f.sqlite3")
    p.pause([provider_scope("p")], reason="RATE_LIMITED", retry_after=0)
    r = p.active(provider_scope("p")); p.release(r["id"], expected_revision=r["revision"], actor="op", reason="x")
    for i in range(127):
        p.pause([origin_scope(f"h{i}.example", 443), origin_scope(f"g{i}.example", 443)], reason="ACCESS_DENIED")
    p.pause([origin_scope("odd.example", 443)], reason="ACCESS_DENIED")
    r = p.active(origin_scope("h0.example", 443)); p.release(r["id"], expected_revision=r["revision"], actor="op", reason="x")
    c = Connector({"h0.example": TEXT, "new.example": TEXT})
    def run(provider, host):
        return outcome(lambda: ResearchCoordinator([Provider(provider, [hit(host)])], WebReader(public, c), resolver=public,
                                                   pauses=ResearchPauses(temp / "f.sqlite3")).run("q"))
    print(f"  rows={len(p.inspect()['pauses'])} (2 RELEASED: provider p, origin h0)")
    print(f"  provider p (row exists), known origin h0 -> {run('p', 'h0.example')}")
    print(f"  provider p (row exists), new origin that would not refuse -> {run('p', 'new.example')}")
    print(f"  provider q (no row), known origin h0 -> {run('q', 'h0.example')} | exchanges={c.calls}")
    shutil.rmtree(temp)


def p3_mission_id():
    section("3 R-G020-1: invalid mission_id, text and bytes, decision and cancel")
    base = dict(store_id="s-" + "a" * 32, client_id="c", command_key="k", actor="a", reason="r")
    cancel = dict(base, protocol=CANCEL_PROTOCOL, mission_id="M-1")
    decision = dict(base, protocol=PROTOCOL, mission_id="M-1", expected_revision=0, proposal_sha256="c" * 64, decision="approve")
    for label, parser, value in (("cancel text", parse_cancel_command, json.dumps(cancel)), ("cancel bytes", parse_cancel_command, json.dumps(cancel).encode()),
                                 ("decision text", parse_command, json.dumps(decision)), ("decision bytes", parse_command, json.dumps(decision).encode()),
                                 ("cancel mission_id=42", parse_cancel_command, json.dumps(dict(cancel, mission_id=42))),
                                 ("duplicate key", parse_cancel_command, '{"protocol":1,"protocol":2}'),
                                 ("wrong protocol", parse_cancel_command, json.dumps(dict(cancel, protocol=PROTOCOL))),
                                 ("bad client_id", parse_cancel_command, json.dumps(dict(cancel, mission_id="m-" + "b" * 32, client_id="-x")))):
        print(f"  {label:22} -> {outcome(lambda: parser(value))}")
    temp = Path(tempfile.mkdtemp(prefix="g024-")); store = Store(temp)
    before = (temp / "missions.sqlite3").read_bytes()
    req = temp / "req.json"; req.write_text(json.dumps(dict(cancel, store_id="s-" + "a" * 32)))
    p = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(temp), "command-cancel", "--request", str(req)],
                       capture_output=True, text=True, timeout=60, env=os.environ)
    print(f"  CLI command-cancel bad mission_id: exit={p.returncode} traceback={'Traceback' in p.stderr} | {p.stderr.strip()[:90]} "
          f"| database unchanged={(temp / 'missions.sqlite3').read_bytes() == before}")
    shutil.rmtree(temp)


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | tree {Path(__import__('eidolon_core').__file__).parents[3].name}")
    for probe in (p1_budget, p2_capacity, p2b_known_scopes, p3_mission_id):
        probe()
