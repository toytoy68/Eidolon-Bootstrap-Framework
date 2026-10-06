# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g014.py
# Description : Sondes indépendantes des reçus de décisions C-008b (C-TASK-G014)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G014 against the frozen target 176c1d2.

From eidolon-core/, with a frozen copy of 176c1d2:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen 176c1d2>/eidolon-core/src \
        python docs/validation/2026-10-06/claude-g014/probes_g014.py

Every probe uses its own temporary store (synthetic restart of 'nas', no real
service). Production code is imported read-only; faults are injected only in
the temporary SQLite files (triggers) or through documented test hooks
(runtime.checkpoint, runtime._prepare_decision wrapped in this process).
Each line prints observed facts; the classification is in README.md.
"""
import json
import multiprocessing as mp
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import PROTOCOL, DecisionCommands, lookup_receipt, parse_command
from eidolon_core.contracts import ContractError
from eidolon_core.store import Busy, Store


def section(title):
    print(f"\n== {title}")


def fresh(n=1):
    temp = tempfile.mkdtemp(prefix="g014-")
    store = Store(temp)
    runtime = ActionRuntime(store)
    missions = [runtime.run(runtime.create_restart("nas")["id"]) for _ in range(n)]
    return temp, store, runtime, missions


def command(store, mission, **changes):
    base = dict(protocol=PROTOCOL, store_id=ClientSync(store).snapshot(mission["id"])["store_id"],
                client_id="probe-desktop", command_key="k-001", mission_id=mission["id"],
                expected_revision=mission["revision"], proposal_sha256=mission["proposal"]["sha256"],
                decision="approve", actor="probe-operator", reason="synthetic probe G014")
    base.update(changes)
    return base


def lookup(store, cmd):
    return lookup_receipt(store, store_id=cmd["store_id"], client_id=cmd["client_id"], command_key=cmd["command_key"])


def decisions(store, mission_id):
    return [e for e in store.events(mission_id) if e["kind"] == "ACTION_DECISION"]


def outcome(fn):
    try:
        r = fn()
        return f"RECORDED rev={r['mission_revision']} seq={r['event_sequence']}" if isinstance(r, dict) and r.get("status") == "RECORDED" else repr(r)[:80]
    except (ContractError, Busy, sqlite3.Error, ValueError) as exc:
        return f"{type(exc).__name__}: {str(exc)[:70]}"


# --- R1: atomicity under injected SQL faults ------------------------------------------------
def r1_sql_faults():
    section("R1 injected SQLite faults: decision, event and receipt all-or-nothing")
    for table, when in (("command_receipts", "BEFORE INSERT"), ("events", "BEFORE INSERT"), ("missions", "AFTER UPDATE")):
        temp, store, runtime, (m,) = fresh()
        cmd = command(store, m)
        before = (store.get(m["id"])["revision"], len(store.events(m["id"])))
        with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
            db.execute(f"CREATE TRIGGER g014_fault {when} ON {table} BEGIN SELECT RAISE(ABORT, 'g014 injected'); END;")
        result = outcome(lambda: DecisionCommands(runtime).submit(cmd))
        after = (store.get(m["id"])["revision"], len(store.events(m["id"])))
        found = lookup(store, cmd)["status"]
        with sqlite3.connect(Path(temp) / "missions.sqlite3") as db:
            db.execute("DROP TRIGGER g014_fault")
        retry = outcome(lambda: DecisionCommands(runtime).submit(cmd))
        print(f"  fault {when} {table:17} -> {result} | revision/events {before}->{after} | lookup={found} "
              f"| after removing fault: {retry}, decisions={len(decisions(store, m['id']))}")
        shutil.rmtree(temp)


# --- R2: real concurrent processes --------------------------------------------------------
def _submit_in_child(temp, cmd, start_at, out):
    store = Store(temp)
    runtime = ActionRuntime(store)
    while time.time() < start_at:
        pass
    out.put((cmd["mission_id"][-6:], outcome(lambda: DecisionCommands(runtime).submit(cmd))))


def r2_concurrency():
    section("R2 concurrent processes: same key on two missions, same command twice")
    ctx = mp.get_context("spawn")
    temp, store, runtime, (a, b) = fresh(2)
    cmds = [command(store, a), command(store, b)]  # same client/key, different content
    q = ctx.Queue()
    start = time.time() + 1.5
    procs = [ctx.Process(target=_submit_in_child, args=(temp, c, start, q)) for c in cmds]
    [p.start() for p in procs]; [p.join(20) for p in procs]
    results = sorted(q.get() for _ in procs)
    print(f"  key shared by 2 missions: {results}")
    print(f"  decisions A={len(decisions(store, a['id']))} B={len(decisions(store, b['id']))} "
          f"revisions A={store.get(a['id'])['revision']} B={store.get(b['id'])['revision']} "
          f"lookup={lookup(store, cmds[0])['receipt']['mission_id'][-6:]}")
    shutil.rmtree(temp)
    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    q = ctx.Queue()
    start = time.time() + 1.5
    procs = [ctx.Process(target=_submit_in_child, args=(temp, cmd, start, q)) for _ in range(4)]
    [p.start() for p in procs]; [p.join(20) for p in procs]
    results = sorted(r for _, r in (q.get() for _ in procs))
    print(f"  same command x4 processes: {results}")
    print(f"  decisions={len(decisions(store, m['id']))} revision {m['revision']}->{store.get(m['id'])['revision']}")
    shutil.rmtree(temp)


# --- R3/R4: replay, reuse and stale requests ---------------------------------------------
def r3_r4_replay():
    section("R3 replay after progression; R4 key reuse, other client, new key")
    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    first = DecisionCommands(runtime).submit(cmd)
    ran = runtime.run(m["id"])
    events = len(store.events(m["id"]))
    again = DecisionCommands(runtime).submit(cmd)
    print(f"  after run (status {ran['status']}, approval {ran['proposal']['status']}): replay identical={again == first}, "
          f"events {events}->{len(store.events(m['id']))}, restarts={runtime.world.observe('sim-nas')['restarts']}, "
          f"receipt still says approval_status_at_recording={again['approval_status_at_recording']}")
    for label, changes in (("same key, decision revoke", {"decision": "revoke"}),
                           ("same key, other reason", {"reason": "another reason"}),
                           ("other client, same content", {"client_id": "probe-other"}),
                           ("new key, same old revision", {"command_key": "k-002"})):
        print(f"  {label:28} -> {outcome(lambda: DecisionCommands(runtime).submit(dict(cmd, **changes)))}")
    print(f"  decisions recorded in total: {len(decisions(store, m['id']))}")
    shutil.rmtree(temp)


# --- R5: cancellation at constant revision -------------------------------------------------
def r5_cancel():
    section("R5 cancellation: before the command, and between preparation and commit")
    temp, store, runtime, (m,) = fresh()
    store.request_cancel(m["id"])
    cur = store.get(m["id"])
    cmd = command(store, cur)
    print(f"  cancel first (revision {m['revision']}->{cur['revision']}): {outcome(lambda: DecisionCommands(runtime).submit(cmd))} "
          f"| lookup={lookup(store, cmd)['status']}")
    shutil.rmtree(temp)
    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    original = runtime._prepare_decision

    def prepare_then_cancel(*args, **kwargs):
        entry = original(*args, **kwargs)
        store.request_cancel(m["id"])  # lands after preparation, before save
        return entry
    runtime._prepare_decision = prepare_then_cancel
    print(f"  cancel races the decision: {outcome(lambda: DecisionCommands(runtime).submit(cmd))} | lookup={lookup(store, cmd)['status']} "
          f"| decisions={len(decisions(store, m['id']))} cancel_requested={store.get(m['id'])['cancel_requested']}")
    shutil.rmtree(temp)
    temp, store, runtime, (m,) = fresh()
    stale = command(store, m, proposal_sha256="0" * 64)
    print(f"  wrong proposal_sha256: {outcome(lambda: DecisionCommands(runtime).submit(stale))} | lookup={lookup(store, stale)['status']}")
    shutil.rmtree(temp)


# --- R6: submit while the mission lock is held, lookup meanwhile ----------------------------
def _hold_lock(temp, mission_id, ready, release):
    store = Store(temp)
    with store.lock(mission_id):
        ready.set()
        release.wait(10)


def r6_locked():
    section("R6 mission lock held by another process (as during run)")
    ctx = mp.get_context("spawn")
    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    ready, release = ctx.Event(), ctx.Event()
    p = ctx.Process(target=_hold_lock, args=(temp, m["id"], ready, release))
    p.start(); ready.wait(10)
    t0 = time.time()
    during = outcome(lambda: DecisionCommands(runtime).submit(cmd))
    lk = lookup(store, cmd)["status"]
    elapsed = time.time() - t0
    release.set(); p.join(10)
    after = outcome(lambda: DecisionCommands(runtime).submit(cmd))
    print(f"  during lock: submit -> {during}; lookup -> {lk} ({elapsed:.2f}s, no wait) | after release: {after}")
    shutil.rmtree(temp)


# --- R7: lost answer after commit, NOT_FOUND while in flight --------------------------------
def r7_lost_and_inflight():
    section("R7 answer lost after commit; NOT_FOUND while the first emission is in flight")
    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    original_checkpoint = runtime.checkpoint

    def crash_after_commit(name):
        if name == "COMMAND_RECORDED":
            raise RuntimeError("answer lost after commit (injected)")
        return original_checkpoint(name)
    runtime.checkpoint = crash_after_commit
    try:
        DecisionCommands(runtime).submit(cmd)
        lost = "returned"
    except RuntimeError as exc:
        lost = f"RuntimeError: {exc}"
    runtime.checkpoint = original_checkpoint
    found = lookup(store, cmd)
    print(f"  submit -> {lost} | lookup={found['status']} authorizes_resend={found['authorizes_resend']} "
          f"| same-key resend -> {outcome(lambda: DecisionCommands(runtime).submit(cmd))} "
          f"| new-key resend -> {outcome(lambda: DecisionCommands(runtime).submit(dict(cmd, command_key='k-003')))} "
          f"| decisions={len(decisions(store, m['id']))}")
    shutil.rmtree(temp)

    temp, store, runtime, (m,) = fresh()
    cmd = command(store, m)
    original = runtime._prepare_decision
    entered, proceed = threading.Event(), threading.Event()

    def slow_prepare(*args, **kwargs):
        entered.set(); proceed.wait(10)
        return original(*args, **kwargs)
    runtime._prepare_decision = slow_prepare
    box = {}
    t = threading.Thread(target=lambda: box.update(r=outcome(lambda: DecisionCommands(runtime).submit(cmd))))
    t.start(); entered.wait(10)
    other = ActionRuntime(Store(temp))  # a second client process would see the same files
    inflight_lookup = lookup(other.store, cmd)["status"]
    same_key = outcome(lambda: DecisionCommands(other).submit(cmd))
    proceed.set(); t.join(10)
    print(f"  in flight: lookup={inflight_lookup}; same-key resend -> {same_key} | first emission -> {box['r']} "
          f"| decisions={len(decisions(store, m['id']))}")
    shutil.rmtree(temp)


# --- R8: historical APPROVED after revoke --------------------------------------------------
def r8_after_revoke():
    section("R8 historical receipt APPROVED after a later revoke")
    temp, store, runtime, (m,) = fresh()
    approve = command(store, m)
    r1 = DecisionCommands(runtime).submit(approve)
    cur = store.get(m["id"])
    revoke = command(store, cur, command_key="k-revoke", decision="revoke")
    r2 = DecisionCommands(runtime).submit(revoke)
    again = lookup(store, approve)["receipt"]
    snap = ClientSync(store).snapshot(m["id"])["snapshot"]["mission"]["action_view"]["decision"]["status"]
    print(f"  approve receipt: {again['approval_status_at_recording']} rev {again['mission_revision']} | revoke receipt: "
          f"{r2['approval_status_at_recording']} rev {r2['mission_revision']} | current capture: {snap} "
          f"| receipt fields mention current state: {any(k in again for k in ('current', 'current_status'))}")
    try:
        after = runtime.run(m["id"])
        ran = f"status={after['status']} approval={after['proposal']['status']} error={(after.get('error') or {}).get('code')}"
    except (ContractError, Busy) as exc:
        ran = f"{type(exc).__name__}: {str(exc)[:60]}"
    print(f"  run after revoke -> {ran} restarts={runtime.world.observe('sim-nas')['restarts']}")
    shutil.rmtree(temp)


# --- R9: restore from backup, clone ---------------------------------------------------------
def r9_restore_clone():
    section("R9 restore of an older copy, clone of the store (documented limits)")
    temp, store, runtime, (m,) = fresh()
    backup = tempfile.mkdtemp(prefix="g014-backup-")
    shutil.copytree(temp, backup, dirs_exist_ok=True)
    cmd = command(store, m)
    DecisionCommands(runtime).submit(cmd)
    shutil.rmtree(temp); shutil.copytree(backup, temp)  # restore the pre-decision copy, same store_id
    restored = Store(temp)
    lk = lookup(restored, cmd)
    again = outcome(lambda: DecisionCommands(ActionRuntime(restored)).submit(cmd))
    print(f"  restored copy: same store_id={ClientSync(restored).snapshot(m['id'])['store_id'] == cmd['store_id']} lookup={lk['status']} "
          f"| same command resubmitted -> {again} (a second 'first' recording)")
    clone = tempfile.mkdtemp(prefix="g014-clone-")
    shutil.copytree(temp, clone, dirs_exist_ok=True)
    print(f"  clone: same store_id={ClientSync(Store(clone)).snapshot(m['id'])['store_id'] == cmd['store_id']} "
          f"lookup in clone={lookup(Store(clone), cmd)['status']} (STORE_CHANGED not raised)")
    for d in (temp, backup, clone):
        shutil.rmtree(d)


# --- R10: JSON / JS compatibility and confidentiality ----------------------------------------
def r10_json():
    section("R10 command JSON edge cases; receipt confidentiality")
    temp, store, runtime, (m,) = fresh()
    base = command(store, m)
    def as_json(**changes):
        return json.dumps(dict(base, **changes))
    raw = json.dumps(base)
    cases = {
        "valid": raw,
        "revision NaN": raw.replace(f'"expected_revision": {base["expected_revision"]}', '"expected_revision": NaN'),
        "revision 1.0": raw.replace(f'"expected_revision": {base["expected_revision"]}', f'"expected_revision": {base["expected_revision"]}.0'),
        "revision true": as_json(expected_revision=True),
        "revision 2^53-1": as_json(expected_revision=2**53 - 1),
        "revision 2^53-2": as_json(expected_revision=2**53 - 2),
        "revision -0": raw.replace(f'"expected_revision": {base["expected_revision"]}', '"expected_revision": -0'),
        "lone surrogate in actor": raw.replace('"probe-operator"', '"probe\\ud800"'),
        "duplicate key": raw[:-1] + ', "decision": "reject"}',
        "extra field": as_json(extra=1),
        "UTF-8 BOM": "﻿" + raw,
        "invalid UTF-8 bytes": raw.encode("utf-8").replace(b"probe-operator", b"probe\xff"),
        "deep nesting": raw[:-1] + ', "x": ' + "[" * 20000 + "]" * 20000 + "}",
        "32769 bytes": raw[:-1] + ', "pad": "' + "p" * (32769 - len(raw) - 10) + '"}',
    }
    for name, payload in cases.items():
        try:
            v = parse_command(payload)
            res = f"accepted (expected_revision={v['expected_revision']!r})"
        except ContractError as exc:
            res = f"ContractError: {str(exc)[:60]}"
        except Exception as exc:  # noqa: BLE001 - an unexpected exception type is itself a finding
            res = f"UNEXPECTED {type(exc).__name__}: {str(exc)[:60]}"
        print(f"  {name:24} -> {res}")
    receipt = DecisionCommands(runtime).submit(base)
    text = json.dumps([receipt, lookup(store, base)])
    print(f"  receipt/lookup contain actor={'probe-operator' in text} reason={'synthetic probe G014' in text} "
          f"| integers safe={all(isinstance(receipt[k], int) and receipt[k] <= 2**53 - 1 for k in ('mission_revision', 'event_sequence'))}")
    try:
        lookup_receipt(store, store_id="s-" + "0" * 32, client_id=base["client_id"], command_key=base["command_key"])
        print("  lookup with another store_id -> answered (unexpected)")
    except ContractError as exc:
        print(f"  lookup with another store_id -> ContractError: {exc}")
    shutil.rmtree(temp)


def main():
    print(f"Python {sys.version.split()[0]}; temporary stores only; no network, no real service.")
    r1_sql_faults(); r2_concurrency(); r3_r4_replay(); r5_cancel(); r6_locked(); r7_lost_and_inflight()
    r8_after_revoke(); r9_restore_clone(); r10_json()
    return 0


if __name__ == "__main__":
    sys.exit(main())
