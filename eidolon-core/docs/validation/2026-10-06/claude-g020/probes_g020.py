# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g020.py
# Description : Sondes indépendantes des correctifs d'audit 97abdb2 (C-TASK-G020)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G020, run twice: base 32f1c8d, then fix 97abdb2.

From eidolon-core/, with frozen copies (git archive) of each tree:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree>/eidolon-core/src:<tree>/eidolon-core \
        python docs/validation/2026-10-06/claude-g020/probes_g020.py

Synthetic temporary states. No Internet: DNS and HTTP are simulated objects
handed to the real WebReader/fetch, or an injected Reader. Cancellation is
committed by another writer (CancelCommands, no lock) at named checkpoints or
while a slow verifier runs in its worker process. FaultAction, Provider, Reader,
dns and hit come from the frozen tests of the same tree.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from eidolon_core.action_view import action_view
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, PROTOCOL, CancelCommands, parse_cancel_command, parse_command
from eidolon_core.contracts import ContractError
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.research_pauses import ResearchPauses, origin_scope
from eidolon_core.store import Store
from eidolon_core.tools import Registry
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_actions import FaultAction
from tests.test_research import Provider, Reader, dns, hit

TREE = Path(__import__("eidolon_core").__file__).parents[2].name + "@" + Path(__import__("eidolon_core").__file__).parents[3].name


def section(title):
    print(f"\n== {title}")


def outcome(fn):
    try:
        r = fn()
        return repr(r)[:80] if not isinstance(r, dict) else f"status={r.get('status')}"
    except Exception as exc:  # the probe reports, it does not judge here
        return f"{type(exc).__name__}: {str(exc)[:80]}"


# --- 1. cancellation and verification ---------------------------------------------------------
@dataclass(frozen=True)
class SlowVerify:
    """Picklable verifier for the worker process: waits, then the real read-only check."""
    world: object
    seconds: float

    def verify(self, parameters, context, output):
        time.sleep(self.seconds)
        return self.world.verify(parameters, context, output)


@dataclass(frozen=True)
class BrokenVerify:
    def verify(self, parameters, context, output):
        raise OSError("synthetic verifier outage")


def runtime_with(store, *, execute=None, verify=None, **kw):
    base = ActionRuntime(store)
    tool = base.world.tool()
    if execute is not None:
        tool = replace(tool, execute=execute)
    if verify is not None:
        tool = replace(tool, verify=verify)
    return ActionRuntime(store, registry=Registry([tool]), **kw)


def approved(rt):
    m = rt.run(rt.create_restart("nas")["id"])
    rt.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve", actor="probe", reason="G020")
    return m["id"]


def cancel(store, mid):
    sid = ClientSync(store).snapshot(mid)["store_id"]
    return CancelCommands(Store(store.directory)).submit(dict(protocol=CANCEL_PROTOCOL, store_id=sid, client_id="probe",
        command_key="c-" + str(time.monotonic_ns()), mission_id=mid, actor="probe", reason="G020 stop"))["cancel_outcome"]


def brief(store, rt, m):
    m = store.get(m) if isinstance(m, str) else m
    view = action_view(m)
    kinds = [e["kind"] for e in store.events(m["id"])]
    return (f"{m['status']}/{m['phase']} err={(m.get('error') or {}).get('code')} outcome={m['outcome']['status']} "
            f"result={'set' if m['result'] else 'None'} calls={[c['status'] for c in m['calls']]} "
            f"effect={view['effect']['code'] if view else None} restarts={rt.world.observe('sim-nas')['restarts']} "
            f"CALL_STARTED={kinds.count('CALL_STARTED')}")


def p1_cancellation():
    section("1 cancellation vs verification")
    for point in ("TOOL_RETURNED", "RESULT_SAVED"):
        temp = tempfile.mkdtemp(prefix="g020-"); store = Store(temp)
        rt0 = ActionRuntime(store); mid = approved(rt0)
        fired = []
        rt = ActionRuntime(store, checkpoint=lambda k, p=point: fired.append(cancel(store, mid)) if k == p and not fired else None)
        r = outcome(lambda: rt.run(mid))
        print(f"  cancel at {point:14} -> {brief(store, rt0, mid)} | run again -> {rt0.run(mid)['status']}")
        shutil.rmtree(temp)

    # Cancel committed WHILE the verifier runs in its worker (slow verifier, 1.5 s).
    temp = tempfile.mkdtemp(prefix="g020-"); store = Store(temp)
    base = ActionRuntime(store)
    rt = runtime_with(store, verify=SlowVerify(base.world, 1.5).verify)
    mid = approved(rt)
    box = {}
    worker = threading.Thread(target=lambda: box.setdefault("m", outcome(lambda: rt.run(mid))))
    worker.start()
    deadline = time.time() + 15
    while time.time() < deadline and not any(e["kind"] == "RESULT_SAVED" for e in store.events(mid)):
        time.sleep(0.05)
    time.sleep(0.3)
    got = cancel(store, mid)
    worker.join(30)
    print(f"  cancel DURING verification ({got}) -> {brief(store, base, mid)}")
    shutil.rmtree(temp)

    # Verifier unavailable after cancellation: resumable? then can it be closed if it never returns?
    temp = tempfile.mkdtemp(prefix="g020-"); store = Store(temp)
    base = ActionRuntime(store)
    broken = runtime_with(store, verify=BrokenVerify().verify)
    mid = approved(broken)
    fired = []
    rt = runtime_with(store, verify=BrokenVerify().verify,
                      checkpoint=lambda k: fired.append(cancel(store, mid)) if k == "RESULT_SAVED" and not fired else None)
    rt.run(mid)
    print(f"  verifier down + cancel -> {brief(store, base, mid)}")
    print(f"      run again (still down) -> {brief(store, base, broken.run(mid))}")
    for label, fn in (("reconcile abandon", lambda: broken.reconcile(mid, decision="abandon", actor="probe", reason="close")),
                      ("second cancel command", lambda: cancel(store, mid)),
                      ("legacy runtime.cancel", lambda: broken.cancel(mid))):
        print(f"      {label:22} -> {outcome(fn)} | now {store.get(mid)['status']}")
    print(f"      verifier back -> {brief(store, base, base.run(mid))}")
    shutil.rmtree(temp)

    # Wrong output + cancellation: never ACHIEVED.
    temp = tempfile.mkdtemp(prefix="g020-"); store = Store(temp)
    base = ActionRuntime(store)
    wrong = runtime_with(store, execute=FaultAction(base.world, "wrong-output").execute)
    mid = approved(wrong)
    fired = []
    rt = runtime_with(store, execute=FaultAction(base.world, "wrong-output").execute,
                      checkpoint=lambda k: fired.append(cancel(store, mid)) if k == "TOOL_RETURNED" and not fired else None)
    rt.run(mid)
    print(f"  wrong output + cancel -> {brief(store, base, mid)}")
    shutil.rmtree(temp)

    # Child died after the effect (REVIEW), cancel, observed-result reconciliation (G015 R3 path).
    temp = tempfile.mkdtemp(prefix="g020-"); store = Store(temp)
    base = ActionRuntime(store)
    lost = runtime_with(store, execute=FaultAction(base.world, "lost").execute)
    mid = approved(lost)
    lost.run(mid)
    cancel(store, mid)
    lost.reconcile(mid, decision="observed-result", actor="probe", reason="adopt", output=base.world.receipt(mid)["result"])
    print(f"  REVIEW + cancel + observed-result, run -> {brief(store, base, lost.run(mid))}")
    shutil.rmtree(temp)


OLD_STATE = r'''
import sys
from eidolon_core.actions import ActionRuntime
from eidolon_core.store import Store
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands
store = Store(sys.argv[1]); rt = ActionRuntime(store)
m = rt.run(rt.create_restart("nas")["id"])
rt.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve", actor="p", reason="r")
def cp(kind, fired=[]):
    if kind == "TOOL_RETURNED" and not fired:
        sid = ClientSync(store).snapshot(m["id"])["store_id"]
        fired.append(CancelCommands(Store(sys.argv[1])).submit(dict(protocol=CANCEL_PROTOCOL, store_id=sid, client_id="p",
            command_key="old", mission_id=m["id"], actor="p", reason="r")))
ActionRuntime(store, checkpoint=cp).run(m["id"])
print(m["id"])
'''


def p1b_old_terminal(base_tree):
    section("1b mission closed by the OLD code (E1 state), then opened by this tree")
    if not base_tree:
        print("  skipped (no base tree given)")
        return
    temp = tempfile.mkdtemp(prefix="g020-")
    env = dict(os.environ, PYTHONPATH=f"{base_tree}/eidolon-core/src")
    p = subprocess.run([sys.executable, "-c", OLD_STATE, temp], capture_output=True, text=True, env=env, timeout=60)
    mid = p.stdout.strip().splitlines()[-1]
    store = Store(temp); rt = ActionRuntime(store)
    before = store.get(mid)
    print(f"  written by 32f1c8d: {brief(store, rt, before)}")
    after = rt.run(mid)
    print(f"  run with this tree: {brief(store, rt, after)} | reopened={after['status'] != before['status']} "
          f"revision {before['revision']}->{store.get(mid)['revision']}")
    shutil.rmtree(temp)


# --- 2. Web refusals ---------------------------------------------------------------------------
class Connector:
    """Simulated peer: scripted answers per host; counts every exchange."""
    def __init__(self, script):
        self.script, self.calls = script, []

    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append(host)
        status, hdrs, body, complete = self.script[host]
        return RawResponse(status, hdrs, body, complete)


def p2_web():
    section("2a refusal after a redirect to ANOTHER origin, then final DNS fails / turns private (real WebReader/fetch)")
    for status in (403, 429, 503):
        for final_dns in ("fails", "private"):
            temp = tempfile.mkdtemp(prefix="g020-")
            pauses = ResearchPauses(Path(temp) / "pauses.sqlite3")
            connector = Connector({"docs.example": (302, (("Location", "https://mirror.example/a"),), b"", True),
                                   "mirror.example": (status, (("Retry-After", "30"),), b"", True)})

            outage = {"on": True}

            def resolver(host, port):
                if outage["on"] and host == "mirror.example" and len(connector.calls) >= 2:
                    if final_dns == "fails":
                        raise OSError("synthetic DNS outage after the response")
                    return ["10.0.0.7"]
                return ["9.9.9.9"]
            reports = [ResearchCoordinator([Provider("p", [hit()])], WebReader(resolver, connector),
                                           resolver=resolver, pauses=pauses).run("fixture") for _ in range(2)]
            outage["on"] = False  # DNS healthy again: only the durable pause can stop a direct hit
            direct = ResearchCoordinator([Provider("p", [Hit("https://mirror.example/b", "Synthetic direct hit")])],
                                         WebReader(resolver, connector), resolver=resolver, pauses=pauses).run("fixture")
            s0 = reports[0]["sources"][0]
            print(f"  {status} via redirect, final DNS {final_dns:7}: exchanges={connector.calls} "
                  f"| run1 source={s0['state']} text={'set' if s0.get('text') else None} "
                  f"| paused docs={bool(pauses.active(origin_scope('docs.example', 443)))} "
                  f"mirror={bool(pauses.active(origin_scope('mirror.example', 443)))} "
                  f"| run2={reports[1]['sources'][0]['state']} direct-to-mirror={direct['sources'][0]['state']}")
            shutil.rmtree(temp)

    section("2b refusal with truncated / oversized body: injected Reader vs real WebReader")
    for status in (401, 403, 429):
        for issue, extra in (("truncated", dict(complete=False)), ("too large", dict(body=b"x" * 128_001))):
            temp = tempfile.mkdtemp(prefix="g020-")
            pauses = ResearchPauses(Path(temp) / "pauses.sqlite3")
            reader = Reader({hit().url: dict(status=status, url="https://mirror.example/x", **extra)})
            for _ in range(2):
                ResearchCoordinator([Provider("p", [hit()])], reader, resolver=dns, pauses=pauses).run("fixture")
            injected = f"reads={len(reader.calls)} paused docs={bool(pauses.active(origin_scope('docs.example', 443)))} mirror={bool(pauses.active(origin_scope('mirror.example', 443)))}"
            shutil.rmtree(temp)
            temp = tempfile.mkdtemp(prefix="g020-")
            pauses = ResearchPauses(Path(temp) / "pauses.sqlite3")
            body = b"x" * (128_001 if issue == "too large" else 10)
            connector = Connector({"docs.example": (status, (("Content-Length", str(len(body) + (50 if issue == "truncated" else 0))),), body, issue != "truncated")})
            reports = [ResearchCoordinator([Provider("p", [hit()])], WebReader(dns, connector), resolver=dns, pauses=pauses).run("fixture") for _ in range(2)]
            real = f"exchanges={len(connector.calls)} state={reports[0]['sources'][0]['state']} paused={bool(pauses.active(origin_scope('docs.example', 443)))}"
            print(f"  {status} {issue:9} | injected Reader: {injected} | WebReader: {real}")
            shutil.rmtree(temp)

    section("2c 200 OK but the final destination resolves private after the response")
    temp = tempfile.mkdtemp(prefix="g020-")
    connector = Connector({"docs.example": (200, (("Content-Type", "text/plain"),), b"public text", True)})
    def rebinding(host, port):
        return ["10.0.0.9"] if connector.calls else ["9.9.9.9"]
    r = ResearchCoordinator([Provider("p", [hit()])], WebReader(rebinding, connector), resolver=rebinding,
                            pauses=ResearchPauses(Path(temp) / "p.sqlite3")).run("fixture")
    s = r["sources"][0]
    print(f"  source={s['state']} reason={s.get('reason')} text={s.get('text')} final_url={s.get('final_url')} readable={r['readable_pages']}")
    shutil.rmtree(temp)


# --- 3. parsers ------------------------------------------------------------------------------
def p3_parsers():
    section("3 command parsers: diagnostics")
    good = dict(protocol=CANCEL_PROTOCOL, store_id="s-" + "a" * 32, client_id="c", command_key="k",
                mission_id="m-" + "b" * 32, actor="a", reason="r")
    cases = (("empty object", "{}"), ("duplicate key", '{"protocol":1,"protocol":2}'), ("None", None), ("int", 42),
             ("dict", {}), ("invalid UTF-8 bytes", b"\xff"), ("lone surrogate", "\ud800"), ("BOM", "﻿{}"),
             ("NaN", json.dumps(good).replace('"r"', "NaN")), ("bad mission id", json.dumps(dict(good, mission_id="M-1"))),
             ("actor spaces", json.dumps(dict(good, actor="  "))), ("too large", json.dumps(dict(good, reason="x" * 33000))),
             ("deep nesting", "[" * 3000 + "]" * 3000))
    for label, raw in cases:
        print(f"  cancel parse {label:20} -> {outcome(lambda: parse_cancel_command(raw))}")
    decision = dict(good, protocol=PROTOCOL, mission_id="M-1", expected_revision=0, proposal_sha256="c" * 64, decision="approve")
    print(f"  decision parse bad mission id  -> {outcome(lambda: parse_command(json.dumps(decision)))}")
    temp = tempfile.mkdtemp(prefix="g020-")
    Store(temp)
    for label, data in (("duplicate key", b'{"protocol":1,"protocol":2}'), ("invalid UTF-8", b"\xff\xfe"),
                        ("bad mission id", json.dumps(dict(good, mission_id="M-1")).encode())):
        path = Path(temp) / "req.json"; path.write_bytes(data)
        p = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", temp, "command-cancel", "--request", str(path)],
                           capture_output=True, text=True, timeout=60, env=os.environ)
        print(f"  CLI command-cancel {label:15} exit={p.returncode} traceback={'Traceback' in p.stderr} | {p.stderr.strip()[:110]}")
    shutil.rmtree(temp)


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | tree: {TREE}")
    p1_cancellation()
    p1b_old_terminal(os.environ.get("G020_BASE_TREE"))
    p2_web()
    p3_parsers()
