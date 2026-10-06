# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g015.py
# Description : Sondes indépendantes des reçus d'annulation C-008c (C-TASK-G015)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G015 against the frozen target 9d1cc0f.

From eidolon-core/, with a frozen copy of 9d1cc0f (git archive):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen>/eidolon-core/src:<frozen>/eidolon-core \
        python docs/validation/2026-10-06/claude-g015/probes_g015.py

Each probe uses its own temporary store (synthetic restart of 'nas', no real
service). Production code is imported read-only. Faults are injected only in
the temporary SQLite files (triggers, a held write lock), through the
documented runtime.checkpoint hook, or by wrapping approvals.consume in the
probe process. FaultAction comes from the frozen tests/test_actions.py.
Each line prints observed facts; the classification is in README.md.
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
from dataclasses import replace
from pathlib import Path

from eidolon_core import actions as actions_module
from eidolon_core.action_view import action_view
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import (CANCEL_PROTOCOL, PROTOCOL, CancelCommands, DecisionCommands,
                                   lookup_receipt, parse_cancel_command, validate_cancel_command)
from eidolon_core.contracts import ContractError, encode
from eidolon_core.runtime import Limits
from eidolon_core.store import Busy, Store
from eidolon_core.tools import Registry

ACTOR, REASON = "probe-operator-G015", "synthetic stop request G015"


def section(title):
    print(f"\n== {title}")


def fresh(n=1, **runtime_options):
    temp = tempfile.mkdtemp(prefix="g015-")
    store = Store(temp)
    runtime = ActionRuntime(store, **runtime_options)
    missions = [runtime.run(runtime.create_restart("nas")["id"]) for _ in range(n)]
    return temp, store, runtime, missions


def store_id(store, mission_id):
    return ClientSync(store).snapshot(mission_id)["store_id"]


def cancel_cmd(store, mission_id, key="c-001", client="probe-desktop", **changes):
    cmd = dict(protocol=CANCEL_PROTOCOL, store_id=store_id(store, mission_id), client_id=client,
               command_key=key, mission_id=mission_id, actor=ACTOR, reason=REASON)
    cmd.update(changes)
    return cmd


def decision_cmd(store, mission, key="d-001", client="probe-desktop"):
    return dict(protocol=PROTOCOL, store_id=store_id(store, mission["id"]), client_id=client,
                command_key=key, mission_id=mission["id"], expected_revision=mission["revision"],
                proposal_sha256=mission["proposal"]["sha256"], decision="approve",
                actor=ACTOR, reason="synthetic approval G015")


def approve(runtime, m):
    return runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                          actor=ACTOR, reason="synthetic approval G015")


def lookup(store, cmd):
    return lookup_receipt(store, store_id=cmd["store_id"], client_id=cmd["client_id"],
                          command_key=cmd["command_key"])


def kinds(store, mission_id, *names):
    events = store.events(mission_id)
    return {n: sum(e["kind"] == n for e in events) for n in names} if names else len(events)


def restarts(runtime):
    return runtime.world.observe("sim-nas")["restarts"]


def outcome(fn):
    try:
        r = fn()
        if isinstance(r, dict) and r.get("protocol") == "eidolon-cancel-receipt/1":
            return f"{r['cancel_outcome']} at={r['mission_status_at_recording']} rev={r['mission_revision']} seq={r['event_sequence']}"
        if isinstance(r, dict) and r.get("status") == "RECORDED":
            return f"DECISION RECORDED rev={r['mission_revision']}"
        return repr(r)[:80]
    except (ContractError, Busy, sqlite3.Error, ValueError, KeyError) as exc:
        return f"{type(exc).__name__}: {str(exc)[:70]}"


def effect(m):
    view = action_view(m)
    return None if view is None else view["effect"]["code"]


def brief(m):
    return (f"status={m['status']} phase={m['phase']} error={(m.get('error') or {}).get('code')} "
            f"result={'present' if m.get('result') else 'None'} calls={[c['status'] for c in m['calls']]} "
            f"approval={(m.get('proposal') or {}).get('status')} effect={effect(m)} outcome={m['outcome']['status']} "
            f"cancel_requested={m['cancel_requested']}")


# --- R1: atomicity --------------------------------------------------------------------------
def r1_sql_faults():
    section("R1a injected SQLite faults: flag, event and receipt all-or-nothing")
    for name, sql in (("missions BEFORE UPDATE", "BEFORE UPDATE ON missions"),
                      ("events AFTER INSERT", "AFTER INSERT ON events"),
                      ("command_receipts AFTER INSERT", "AFTER INSERT ON command_receipts")):
        temp, store, runtime, (m,) = fresh()
        cmd = cancel_cmd(store, m["id"])
        before = (store.get(m["id"]), kinds(store, m["id"]))
        with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
            db.execute(f"CREATE TRIGGER g015_fault {sql} BEGIN SELECT RAISE(ABORT, 'g015 injected'); END;")
        result = outcome(lambda: CancelCommands(store).submit(cmd))
        same = (store.get(m["id"]), kinds(store, m["id"])) == before
        found = lookup(store, cmd)["status"]
        with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
            db.execute("DROP TRIGGER g015_fault")
        retry = outcome(lambda: CancelCommands(store).submit(cmd))
        print(f"  fault {name:30} -> {result} | mission+events unchanged={same} lookup={found} "
              f"| after removing fault: {retry}, CANCEL_REQUESTED={kinds(store, m['id'], 'CANCEL_REQUESTED')['CANCEL_REQUESTED']}")
        shutil.rmtree(temp)


CRASH_CHILD = r'''
import json, os, sqlite3, sys
real = sqlite3.connect
def connect(*a, **k):
    db = real(*a, **k)
    db.create_function("g015_die", 0, lambda: os._exit(91))
    return db
sqlite3.connect = connect
from eidolon_core.commands import CancelCommands
from eidolon_core.store import Store
CancelCommands(Store(sys.argv[1])).submit(json.loads(sys.argv[2]))
os._exit(92)  # committed, but the answer never reaches the caller
'''


def r1_process_kill():
    section("R1b real process killed after all three writes, before COMMIT; then after COMMIT")
    temp, store, runtime, (m,) = fresh()
    cmd = cancel_cmd(store, m["id"])
    before = (store.get(m["id"]), kinds(store, m["id"]))
    with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
        db.execute("CREATE TRIGGER g015_die AFTER INSERT ON command_receipts BEGIN SELECT g015_die(); END;")
    run = lambda: subprocess.run([sys.executable, "-c", CRASH_CHILD, temp, json.dumps(cmd)],
                                 capture_output=True, text=True, timeout=30, env=os.environ)
    first = run()
    print(f"  kill inside transaction: exit={first.returncode} | mission+events unchanged="
          f"{(store.get(m['id']), kinds(store, m['id'])) == before} | lookup={lookup(store, cmd)['status']}")
    with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
        db.execute("DROP TRIGGER g015_die")
    second = run()
    found = lookup(store, cmd)
    events = kinds(store, m["id"])
    again = CancelCommands(store).submit(cmd)
    print(f"  kill after commit: exit={second.returncode} | lookup={found['status']} flag={store.cancel_requested(m['id'])} "
          f"| resubmit identical to lookup={again == found['receipt']} events {events}->{kinds(store, m['id'])}")
    shutil.rmtree(temp)


def _child_submit(temp, cmd, start_at, out):
    store = Store(temp)
    while time.time() < start_at:
        pass
    try:
        if cmd["protocol"] == CANCEL_PROTOCOL:
            r = CancelCommands(store).submit(cmd)
            out.put(("cancel", r["cancel_outcome"], json.dumps(r, sort_keys=True)))
        else:
            r = DecisionCommands(ActionRuntime(store)).submit(cmd)
            out.put(("decision", "RECORDED", json.dumps(r, sort_keys=True)))
    except (ContractError, Busy, sqlite3.Error, KeyError) as exc:
        out.put((cmd["protocol"][8:14], f"{type(exc).__name__}: {str(exc)[:50]}", None))


def _race(temp, cmds):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    start = time.time() + 2.0
    procs = [ctx.Process(target=_child_submit, args=(temp, c, start, q)) for c in cmds]
    [p.start() for p in procs]
    results = [q.get(timeout=60) for _ in procs]
    [p.join(30) for p in procs]
    return results


def r1_concurrency():
    section("R1c real concurrent processes")
    temp, store, runtime, (m,) = fresh()
    cmd = cancel_cmd(store, m["id"])
    res = _race(temp, [cmd] * 4)
    bodies = {r[2] for r in res}
    print(f"  same command x4: outcomes={sorted(r[1] for r in res)} distinct receipts={len(bodies)} "
          f"events={kinds(store, m['id'], 'CANCEL_REQUESTED', 'CANCEL_COMMAND_RECORDED')}")
    shutil.rmtree(temp)

    temp, store, runtime, (m,) = fresh()
    res = _race(temp, [cancel_cmd(store, m["id"], key=f"c-00{i}") for i in range(4)])
    print(f"  4 different keys, same mission: outcomes={sorted(r[1] for r in res)} "
          f"events={kinds(store, m['id'], 'CANCEL_REQUESTED', 'CANCEL_COMMAND_RECORDED')} revision={store.get(m['id'])['revision']}->{m['revision']}")
    shutil.rmtree(temp)

    temp, store, runtime, (a, b) = fresh(2)
    res = _race(temp, [cancel_cmd(store, a["id"]), cancel_cmd(store, b["id"])])
    print(f"  same key on two missions: outcomes={sorted(r[1] for r in res)} "
          f"flags A={store.cancel_requested(a['id'])} B={store.cancel_requested(b['id'])}")
    shutil.rmtree(temp)

    tally = {}
    for _ in range(4):
        temp, store, runtime, (m,) = fresh()
        res = _race(temp, [cancel_cmd(store, m["id"], key="shared-1"), decision_cmd(store, m, key="shared-1")])
        final = store.get(m["id"])
        key = (tuple(sorted(r[1] for r in res)), final["cancel_requested"], final["proposal"]["status"],
               kinds(store, m["id"], "ACTION_DECISION")["ACTION_DECISION"])
        tally[key] = tally.get(key, 0) + 1
        shutil.rmtree(temp)
    temp, store, runtime, (m,) = fresh()
    first = outcome(lambda: DecisionCommands(runtime).submit(decision_cmd(store, m, key="shared-1")))
    second = outcome(lambda: CancelCommands(store).submit(cancel_cmd(store, m["id"], key="shared-1")))
    print(f"  same key, sequential approve then cancel: {first} | {second} | flag={store.cancel_requested(m['id'])}")
    shutil.rmtree(temp)
    for key, count in tally.items():
        print(f"  same key, cancel vs approve on one mission (x{count}): outcomes={list(key[0])} "
              f"flag={key[1]} approval={key[2]} decisions={key[3]}")


def _hold_mission_lock(temp, mission_id, ready, release):
    with Store(temp).lock(mission_id):
        ready.set()
        release.wait(30)


def _hold_write_lock(temp, seconds, ready):
    db = sqlite3.connect(Path(temp) / "missions.sqlite3", timeout=5)
    db.execute("BEGIN IMMEDIATE")
    ready.set()
    time.sleep(seconds)
    db.rollback()
    db.close()


def r1_locks():
    section("R1d execution lock held by another process; SQLite write lock held >5 s")
    ctx = mp.get_context("spawn")
    temp, store, runtime, (m,) = fresh()
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_mission_lock, args=(temp, m["id"], ready, release))
    holder.start(); ready.wait(20)
    t0 = time.monotonic()
    result = outcome(lambda: CancelCommands(store).submit(cancel_cmd(store, m["id"])))
    elapsed = time.monotonic() - t0
    other = outcome(lambda: DecisionCommands(runtime).submit(decision_cmd(store, m, key="d-lock")))
    print(f"  mission lock held elsewhere: cancel -> {result} in {elapsed:.2f}s | decision (other key) -> {other}")
    release.set(); holder.join(10)
    shutil.rmtree(temp)

    temp, store, runtime, (m,) = fresh()
    cmd = cancel_cmd(store, m["id"])
    ready = ctx.Event()
    holder = ctx.Process(target=_hold_write_lock, args=(temp, 12, ready))
    holder.start(); ready.wait(20)
    t0 = time.monotonic()
    result = outcome(lambda: CancelCommands(store).submit(cmd))
    elapsed = time.monotonic() - t0
    flag_now = store.cancel_requested(m["id"])
    request = Path(temp) / "cancel.json"
    request.write_text(json.dumps(dict(cmd, command_key="c-cli")), encoding="utf-8")
    cli = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", temp, "command-cancel",
                          "--request", str(request)], capture_output=True, text=True, timeout=30, env=os.environ)
    holder.join(15)
    last = (cli.stderr.strip().splitlines() or [""])[-1][:90]
    print(f"  write lock held 12 s: API -> {result} after {elapsed:.1f}s | flag={flag_now} "
          f"lookup={lookup(store, cmd)['status']}")
    print(f"  same situation via CLI command-cancel (other key): exit={cli.returncode} traceback={'Traceback' in cli.stderr} "
          f"last stderr line: {last} | flag after CLI={store.cancel_requested(m['id'])}")
    print(f"  after the lock is released, same command -> {outcome(lambda: CancelCommands(store).submit(cmd))}")
    shutil.rmtree(temp)


# --- R2: races with approval, progression and success --------------------------------------
def r2_races():
    section("R2a cancel before a decision; no revision needed while the mission progresses")
    temp, store, runtime, (m,) = fresh()
    print(f"  cancel -> {outcome(lambda: CancelCommands(store).submit(cancel_cmd(store, m['id'])))}")
    print(f"  approve after cancel (other key) -> {outcome(lambda: DecisionCommands(runtime).submit(decision_cmd(store, m)))}")
    print(f"  run -> {brief(runtime.run(m['id']))} restarts={restarts(runtime)}")
    shutil.rmtree(temp)
    temp = tempfile.mkdtemp(prefix="g015-")
    store = Store(temp)
    runtime = ActionRuntime(store)
    created = runtime.create_restart("nas")
    seen = ClientSync(store).snapshot(created["id"])["snapshot"]["mission"]["revision"]
    progressed = runtime.run(created["id"])
    receipt = CancelCommands(store).submit(cancel_cmd(store, created["id"]))
    print(f"  revision seen by client={seen}, mission progressed to {progressed['revision']} ({progressed['status']}); "
          f"cancel -> {receipt['cancel_outcome']} receipt mission_revision={receipt['mission_revision']}")
    shutil.rmtree(temp)

    section("R2b cancel committed at each step of an approved run (another writer, no lock)")
    for point in ("ACTION_CONDITION_CHECKED", "inside approvals.consume", "CALL_STARTED", "WORKER_SPAWNED",
                  "TOOL_RETURNED", "RESULT_SAVED", "RESULT_VERIFIED"):
        temp, store, runtime, (m,) = fresh()
        approve(runtime, m)
        cmd = cancel_cmd(store, m["id"])
        fired = []

        def inject(kind=None):
            if not fired:
                fired.append(CancelCommands(Store(temp)).submit(cmd)["cancel_outcome"])

        original_consume = actions_module.approvals.consume
        if point == "inside approvals.consume":
            def consume(mission, call):
                inject()
                return original_consume(mission, call)
            actions_module.approvals.consume = consume
            run_rt = ActionRuntime(store)
        else:
            run_rt = ActionRuntime(store, checkpoint=lambda kind, p=point: inject() if kind == p else None)
        try:
            final = run_rt.run(m["id"])
        finally:
            actions_module.approvals.consume = original_consume
        again = runtime.run(m["id"])
        events = kinds(store, m["id"], "CALL_STARTED", "SUCCEEDED", "CANCELLED", "REVIEW_REQUIRED")
        print(f"  at {point:26} cancel={fired} -> {brief(final)} restarts={restarts(runtime)} "
              f"| run again: {again['status']} | events {events}")
        if point in ("TOOL_RETURNED", "RESULT_SAVED"):
            for decision in ("use-receipt", "abandon"):
                print(f"      reconcile {decision} -> {outcome(lambda: runtime.reconcile(m['id'], decision=decision, actor=ACTOR, reason='probe'))}")
        shutil.rmtree(temp)

    section("R2c success already committed; other terminal states")
    temp, store, runtime, (m,) = fresh()
    approve(runtime, m)
    done = runtime.run(m["id"])
    before = store.get(m["id"])
    receipt = CancelCommands(store).submit(cancel_cmd(store, m["id"]))
    after = store.get(m["id"])
    print(f"  after SUCCEEDED: {receipt['cancel_outcome']} at={receipt['mission_status_at_recording']} "
          f"| mission body unchanged={after == before} flag={after['cancel_requested']} result kept={after['result'] == done['result']} "
          f"| event={kinds(store, m['id'], 'CANCEL_COMMAND_RECORDED')}")
    shutil.rmtree(temp)


# --- R3: committed effect, then cancellation -------------------------------------------------
def _lost_runtime(store):
    from tests.test_actions import FaultAction
    base = ActionRuntime(store)
    tool = replace(base.world.tool(), execute=FaultAction(base.world, "lost").execute)
    return ActionRuntime(store, registry=Registry([tool]))


def r3_effects():
    section("R3 effect committed by the child (child dies after commit), then cancellation")
    for decision in ("no-effect", "no-effect+confirm", "observed-result", "abandon"):
        temp = tempfile.mkdtemp(prefix="g015-")
        store = Store(temp)
        rt = _lost_runtime(store)
        m = rt.run(rt.create_restart("nas")["id"])
        approve(rt, m)
        review = rt.run(m["id"])
        receipt = CancelCommands(store).submit(cancel_cmd(store, m["id"]))
        rerun = rt.run(m["id"])
        kwargs = dict(actor=ACTOR, reason="probe reconciliation")
        if decision == "no-effect+confirm":
            kwargs.update(decision="no-effect", confirm_no_effect=True)
        elif decision == "observed-result":
            kwargs.update(decision="observed-result", output=rt.world.receipt(m["id"])["result"])
        else:
            kwargs.update(decision=decision)
        rec = outcome(lambda: rt.reconcile(m["id"], **kwargs)["status"])
        final = rt.run(m["id"])
        if decision == "no-effect":
            print(f"  before cancel: {brief(review)} restarts={restarts(rt)}")
            print(f"  cancel -> {receipt['cancel_outcome']} at={receipt['mission_status_at_recording']} "
                  f"effect_absence_evidence={receipt['effect_absence_evidence']} | run -> {brief(rerun)}")
        print(f"  reconcile {decision:18} -> {rec} | then run -> {brief(final)} restarts={restarts(rt)} "
              f"world receipt kept={rt.world.receipt(m['id']) is not None}")
        shutil.rmtree(temp)


# --- R4: what a client may wrongly conclude ---------------------------------------------------
def r4_client():
    section("R4 lookup of both receipt protocols, ClientSync exposure, parsing")
    temp, store, runtime, (m,) = fresh()
    dcmd = decision_cmd(store, m)
    DecisionCommands(runtime).submit(dcmd)
    sync = ClientSync(store)
    snap0 = sync.snapshot(m["id"])
    m1 = store.get(m["id"])
    ccmd = cancel_cmd(store, m["id"])
    CancelCommands(store).submit(ccmd)
    snap1 = sync.snapshot(m["id"])
    for label, cmd in (("decision", dcmd), ("cancel", ccmd)):
        r = lookup(store, cmd)
        print(f"  lookup {label:8}: status={r['status']} protocol={r['receipt']['protocol']} "
              f"authorizes_resend={r['authorizes_resend']} execution_evidence={r['execution_evidence']} "
              f"receipt keys={sorted(r['receipt'])}")
    m0, m2 = snap0["snapshot"]["mission"], snap1["snapshot"]["mission"]
    print(f"  ClientSync: revision {m0['revision']}->{m2['revision']} cursor {snap0['cursor']['sequence']}->{snap1['cursor']['sequence']} "
          f"cancel_requested {m0['cancel_requested']}->{m2['cancel_requested']} status={m2['status']} "
          f"applicability={m2['action_view']['applicability']['code'] if m2.get('action_view') else None}")
    poll = sync.poll(m["id"], snap0["cursor"])
    text = encode(snap1) + encode(poll)
    print(f"  poll after cancel: events={[e['kind'] for e in poll['events']]} keys={sorted(poll['events'][0])} "
          f"actor/reason leaked={ACTOR in text or REASON in text}")
    other = outcome(lambda: lookup_receipt(store, store_id="s-" + "e" * 32, client_id="probe-desktop", command_key="c-001"))
    print(f"  lookup with another store_id -> {other}")
    reordered = json.dumps(dict(reversed(list(ccmd.items()))))
    print(f"  same command, JSON keys reordered -> {outcome(lambda: CancelCommands(store).submit(parse_cancel_command(reordered)))}")
    print(f"  same key, actor with trailing space -> {outcome(lambda: CancelCommands(store).submit(dict(ccmd, actor=ACTOR + ' ')))}")
    for label, raw in (("extra expected_revision", json.dumps(dict(ccmd, expected_revision=m1['revision']))),
                       ("NaN in reason", json.dumps(ccmd).replace(json.dumps(REASON), "NaN")),
                       ("BOM", "﻿" + json.dumps(ccmd)),
                       ("uppercase mission id", json.dumps(dict(ccmd, mission_id=ccmd["mission_id"].upper()))),
                       ("actor only spaces", json.dumps(dict(ccmd, actor="   "))),
                       ("decision protocol", json.dumps(dict(ccmd, protocol=PROTOCOL))),
                       ("32769 bytes", json.dumps(dict(ccmd, reason="x" * 32700)))):
        try:
            direct = outcome(lambda: validate_cancel_command(json.loads(raw)))
        except ValueError as exc:
            direct = f"json.loads refuses: {type(exc).__name__}"
        print(f"  parse {label:24} -> {outcome(lambda: parse_cancel_command(raw))} | validator alone: {direct}")
    shutil.rmtree(temp)

    section("R4b CLI exit codes for command-cancel")
    temp, store, runtime, (m,) = fresh()
    approve(runtime, m)
    runtime.run(m["id"])
    cases = (("ALREADY_TERMINAL", cancel_cmd(store, m["id"], key="cli-1")),
             ("missing mission", dict(cancel_cmd(store, m["id"], key="cli-2"), mission_id="m-" + "f" * 32)),
             ("other store_id", dict(cancel_cmd(store, m["id"], key="cli-3"), store_id="s-" + "e" * 32)))
    for label, cmd in cases:
        path = Path(temp) / "req.json"
        path.write_text(json.dumps(cmd), encoding="utf-8")
        p = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", temp, "command-cancel", "--request", str(path)],
                           capture_output=True, text=True, timeout=30, env=os.environ)
        channel = "stdout" if p.stdout.strip() else "stderr"
        print(f"  {label:17} exit={p.returncode} {channel}: {(p.stdout or p.stderr).strip()[:100]}")
    shutil.rmtree(temp)


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | target source: {Path(actions_module.__file__).parent}")
    for probe in (r1_sql_faults, r1_process_kill, r1_concurrency, r1_locks, r2_races, r3_effects, r4_client):
        probe()
