# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g017.py
# Description : Sondes indépendantes des copies historiques C-008d (C-TASK-G017)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent probes for C-TASK-G017 against the frozen target 3a2a081.

From eidolon-core/, with a frozen copy of 3a2a081 (git archive):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen>/eidolon-core/src \
        python docs/validation/2026-10-06/claude-g017/probes_g017.py

Synthetic temporary states only. Production code is imported read-only.
Faults: os._exit in child processes at named steps of prepare_review (by
patching a module attribute in the child only), a proxy around the read-only
source connection (as Codex's own WAL test does) to slow the backup steps,
manual directory manipulations that the contract names. No activation path
is created; nothing is written to src/ or tests/.
"""
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

import eidolon_core.recovery as recovery
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands, lookup_receipt
from eidolon_core.contracts import ContractError
from eidolon_core.recovery import inspect_review, prepare_review
from eidolon_core.store import Store

ACTOR, REASON = "probe-operator-G017", "synthetic restore rehearsal G017"
SECRET = "SECRET-G017-REQUEST-TEXT"


def section(title):
    print(f"\n== {title}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16] if Path(path).exists() else None


def files(directory):
    d = Path(directory)
    return sorted(p.name for p in d.iterdir()) if d.exists() else None


def outcome(fn):
    try:
        r = fn()
        return "OK " + (repr(r)[:70] if not isinstance(r, dict) else f"keys={len(r)}")
    except (ContractError, sqlite3.Error, ValueError, KeyError, OSError) as exc:
        return f"{type(exc).__name__}: {str(exc)[:72]}"


def source_state(root, approved=True, cancel=True):
    """A source with an APPROVED pending action, a cancel receipt and a succeeded mission."""
    state = Path(root) / "source"
    store = Store(state)
    rt = ActionRuntime(store)
    pending = rt.run(rt.create_restart("nas")["id"])
    if approved:
        rt.decide(pending["id"], expected_sha256=pending["proposal"]["sha256"], decision="approve",
                  actor=ACTOR, reason="approval kept for history")
    if cancel:
        other = rt.run(rt.create_restart("nas")["id"])
        sid = ClientSync(store).snapshot(other["id"])["store_id"]
        CancelCommands(store).submit(dict(protocol=CANCEL_PROTOCOL, store_id=sid, client_id="probe",
                                          command_key="c-1", mission_id=other["id"], actor=ACTOR, reason=REASON))
    secret = store.create(SECRET, {"probe": "g017"})
    return state, store, rt, pending, secret


# --- 1. consistency with a concurrent writer, default journal and WAL -------------------------
def _writer(state, until, out):
    store = Store(state)
    lat, failures, created = [], [], 0
    while time.time() < until:
        t0 = time.monotonic()
        try:
            store.create("writer mission", {"probe": "writer"})
            created += 1
        except sqlite3.Error as exc:
            failures.append(type(exc).__name__ + ": " + str(exc))
        lat.append(time.monotonic() - t0)
        time.sleep(0.02)
    out.put((created, max(lat), failures[:2], len(failures)))


class SlowSource:
    """Delegates to the read-only source connection; each backup step sleeps (slow disk simulation)."""
    def __init__(self, db, delay):
        self.db, self.delay = db, delay

    def __getattr__(self, name):
        return getattr(self.db, name)

    def backup(self, target, *, pages, progress, sleep):
        def slowed(status, remaining, total):
            time.sleep(self.delay)
            progress(status, remaining, total)
        return self.db.backup(target, pages=pages, progress=slowed, sleep=sleep)


def linked(db_path):
    with closing(sqlite3.connect(Path(db_path).as_uri() + "?mode=ro", uri=True)) as db:
        missions = {r[0]: r[1] for r in db.execute("SELECT id, revision FROM missions")}
        orphans = db.execute("SELECT count(*) FROM events WHERE mission_id NOT IN (SELECT id FROM missions)").fetchone()[0]
        missing_created = sum(1 for m in missions if not db.execute(
            "SELECT 1 FROM events WHERE mission_id=? AND kind='CREATED'", (m,)).fetchone())
        receipts = [json.loads(r[0]) for r in db.execute("SELECT body FROM command_receipts")]
        bad = sum(1 for r in receipts if r["mission_id"] not in missions or not db.execute(
            "SELECT 1 FROM events WHERE sequence=?", (r["event_sequence"],)).fetchone())
    return len(missions), orphans, missing_created, bad


def p1_concurrent_writer():
    section("1 concurrent writer during prepare: default journal (as Store creates it) and WAL")
    ctx = mp.get_context("spawn")
    for mode, delay in (("default", 0.0), ("default", 0.4), ("wal", 0.4)):
        root = Path(tempfile.mkdtemp(prefix="g017-"))
        state, store, rt, *_ = source_state(root)
        with closing(sqlite3.connect(store.path)) as db:
            journal = db.execute("PRAGMA journal_mode" + ("=WAL" if mode == "wal" else "")).fetchone()[0]
            db.execute("CREATE TABLE g017_filler (b BLOB)")
            db.executemany("INSERT INTO g017_filler VALUES (?)", [(os.urandom(4096),) for _ in range(4000)])
            db.commit()
        q = ctx.Queue()
        until = time.time() + (2 if delay == 0 else 9)
        w = ctx.Process(target=_writer, args=(str(state), until, q))
        w.start(); time.sleep(0.3)
        original = recovery._readonly
        recovery._readonly = lambda path, d=delay: SlowSource(original(path), d) if d else original(path)
        t0 = time.monotonic()
        try:
            res = outcome(lambda: prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON))
        finally:
            recovery._readonly = original
        took = time.monotonic() - t0
        created, worst, failures, nfail = q.get(timeout=60); w.join(10)
        copy = linked(root / "review" / "missions.sqlite3") if (root / "review" / "missions.sqlite3").exists() else None
        print(f"  journal={journal:7} backup step delay={delay}s prepare {took:.1f}s -> {res}")
        print(f"      writer: {created} commits, worst latency {worst:.2f}s, failures={nfail} {failures[:1]}")
        print(f"      copy (missions, orphan events, missions without CREATED, receipts unlinked) = {copy}; "
              f"source missions now = {linked(store.path)[0]}")
        shutil.rmtree(root)


# --- 2. guards: prebuilt Store, replaced file, removed marker, incomplete state ---------------
def p2_guards():
    section("2 guards on a published copy")
    root = Path(tempfile.mkdtemp(prefix="g017-"))
    state, store, rt, pending, secret = source_state(root)
    before = sha(store.path)
    report = prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON)
    print(f"  source unchanged={sha(store.path) == before} | copy files={files(root / 'review')} "
          f"| simulation.sqlite3 in source={(state / 'simulation.sqlite3').exists()} artifacts_restored={report['artifacts_restored']}")
    review = root / "review"
    sid_new, sid_old = report["store_id"], report["source_store_id"]
    for label, fn in (("Store(copy)", lambda: Store(review)),
                      ("source store still live: lookup", lambda: lookup_receipt(store, store_id=sid_old, client_id="probe", command_key="c-1"))):
        print(f"  {label:28} -> {outcome(fn)}")
    marker = review / "RECOVERY-REVIEW-ONLY"
    marker.rename(root / "marker.saved")
    print(f"  marker removed, Store(copy) -> {outcome(lambda: Store(review))} | files={files(review)}")
    marker_back = (root / "marker.saved").rename(marker)

    # Store already constructed on a live directory, then its file replaced by the guarded copy.
    live = root / "live"
    live_store = Store(live)
    live_rt = ActionRuntime(live_store)
    m = live_rt.run(live_rt.create_restart("nas")["id"])
    shutil.copy2(review / "missions.sqlite3", root / "guarded.sqlite3")
    os.replace(root / "guarded.sqlite3", live / "missions.sqlite3")
    print(f"  prebuilt Store, file replaced by guarded copy (no marker in that directory):")
    for label, fn in (("store.get", lambda: live_store.get(pending["id"])),
                      ("ClientSync.snapshot", lambda: ClientSync(live_store).snapshot(pending["id"])),
                      ("CancelCommands.submit (new id)", lambda: CancelCommands(live_store).submit(dict(
                          protocol=CANCEL_PROTOCOL, store_id=sid_new, client_id="probe", command_key="c-9",
                          mission_id=pending["id"], actor=ACTOR, reason=REASON))),
                      ("lookup_receipt (new id)", lambda: lookup_receipt(live_store, store_id=sid_new, client_id="probe", command_key="c-1")),
                      ("runtime.run (APPROVED mission)", lambda: live_rt.run(pending["id"])),
                      ("runtime.decide", lambda: live_rt.decide(m["id"], expected_sha256="0" * 64, decision="approve", actor=ACTOR, reason="x")),
                      ("ActionRuntime(prebuilt)", lambda: ActionRuntime(live_store).run(pending["id"]))):
        print(f"      {label:32} -> {outcome(fn)}")
    print(f"      restarts in the live world: {live_rt.world.observe('sim-nas')['restarts']} | files={files(live)}")

    hist = inspect_review(review, mission_id=pending["id"])["mission"]
    leaked = SECRET in json.dumps(inspect_review(review, mission_id=secret["id"]))
    full = json.dumps(inspect_review(review))
    print(f"  inspect APPROVED mission: status={hist['status_at_snapshot']} approval={hist['proposal_status_at_snapshot']} "
          f"calls={hist['calls_at_snapshot'][0]['status'] if hist['calls_at_snapshot'] else None}")
    print(f"  inspect leaks request text={leaked} | report has source path={str(state) in full} "
          f"actor/reason of preparation present={ACTOR in full and REASON in full}")
    with closing(sqlite3.connect(review / "missions.sqlite3")) as db:  # raw SQL: out of the protected interfaces
        db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ("s-" + "a" * 32,))
        db.commit()
    print(f"  identity changed by raw SQL -> inspect: {outcome(lambda: inspect_review(review))}")
    shutil.rmtree(root)


# --- 3. abrupt exits at each step of prepare_review --------------------------------------------
CHILD = r'''
import os, sys, pathlib, hashlib, time
import eidolon_core.recovery as recovery
point = sys.argv[3]
die = lambda *a, **k: os._exit(77)
if point == "during-backup":
    original = recovery._readonly
    class P:
        def __init__(s, db): s.db = db
        def __getattr__(s, n): return getattr(s.db, n)
        def backup(s, target, **kw): kw["progress"] = die; return s.db.backup(target, **kw)
    recovery._readonly = lambda p: P(original(p))
elif point == "after-backup-before-guard":
    recovery.hashlib.file_digest = die
elif point == "after-guard-before-link":
    recovery.os.link = die
elif point == "after-link-before-unlink":
    pathlib.Path.unlink = die
elif point == "after-publication-before-reply":
    recovery.inspect_review = die
recovery.prepare_review(sys.argv[1], sys.argv[2], actor="probe", reason="crash probe")
os._exit(0)
'''


def p3_crashes():
    section("3 abrupt exit at each step of prepare_review (real child process)")
    for point in ("during-backup", "after-backup-before-guard", "after-guard-before-link",
                  "after-link-before-unlink", "after-publication-before-reply"):
        root = Path(tempfile.mkdtemp(prefix="g017-"))
        state, store, *_ = source_state(root)
        before = sha(store.path)
        dest = root / "review"
        p = subprocess.run([sys.executable, "-c", CHILD, str(store.path), str(dest), point],
                           capture_output=True, text=True, timeout=60, env=os.environ)
        print(f"  {point:31} exit={p.returncode} files={files(dest)} source unchanged={sha(store.path) == before}")
        print(f"      Store(dest) -> {outcome(lambda: Store(dest))} | inspect -> {outcome(lambda: inspect_review(dest))}")
        print(f"      prepare again, same destination -> {outcome(lambda: prepare_review(store.path, dest, actor=ACTOR, reason=REASON))}")
        code, tb, text = cli(dest, "recovery-inspect")
        print(f"      CLI recovery-inspect exit={code} traceback={tb} | {text[:110]}")
        (dest / "RECOVERY-REVIEW-ONLY").unlink(missing_ok=True)
        res = outcome(lambda: Store(dest))
        live_db = dest / "missions.sqlite3"
        fresh_db = False
        if live_db.exists():
            with closing(sqlite3.connect(live_db)) as db:
                fresh_db = db.execute("SELECT count(*) FROM missions").fetchone()[0] == 0
        print(f"      after manual marker removal: Store(dest) -> {res} | files={files(dest)} "
              f"| empty live store created={fresh_db}")
        shutil.rmtree(root)


# --- 4. CLI: guarded copy and SQLite errors --------------------------------------------------
def cli(state, *args, stdin=None):
    p = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(state), *args],
                       capture_output=True, text=True, timeout=60, env=os.environ)
    text = (p.stdout + p.stderr).strip().replace("\n", " ")
    return p.returncode, "Traceback" in p.stderr, text[:120]


def _hold(path, seconds, ready):
    db = sqlite3.connect(path, timeout=5)
    db.execute("BEGIN IMMEDIATE")
    ready.set()
    time.sleep(seconds)
    db.rollback()


def p4_cli():
    section("4 CLI on a guarded copy, and SQLite errors")
    root = Path(tempfile.mkdtemp(prefix="g017-"))
    state, store, rt, pending, secret = source_state(root)
    code, tb, text = cli(root, "recovery-prepare", "--source", str(store.path), "--destination", str(root / "review"),
                         "--actor", ACTOR, "--reason", REASON)
    print(f"  recovery-prepare exit={code} traceback={tb}")
    review = root / "review"
    before = files(review)
    req = root / "cancel.json"
    report = inspect_review(review)
    req.write_text(json.dumps(dict(protocol=CANCEL_PROTOCOL, store_id=report["store_id"], client_id="probe",
                                   command_key="c-2", mission_id=pending["id"], actor=ACTOR, reason=REASON)))
    for args in (("show", pending["id"]), ("run", pending["id"]), ("--profile", "action-sim", "run", pending["id"]),
                 ("cancel", pending["id"]), ("command-cancel", "--request", str(req)),
                 ("command-receipt", "--store-id", report["store_id"], "--client-id", "probe", "--command-key", "c-1"),
                 ("client-snapshot", pending["id"]), ("recovery-inspect",)):
        code, tb, text = cli(review, *args)
        print(f"  {' '.join(a if not a.startswith('m-') else 'm-…' for a in args)[:40]:40} exit={code} tb={tb} {text[:90]}")
    print(f"  files created in the copy by these commands: {sorted(set(files(review)) - set(before))}")
    code, tb, text = cli(root, "recovery-prepare", "--source", str(store.path), "--destination", str(review),
                         "--actor", ACTOR, "--reason", REASON)
    print(f"  prepare again on the same destination: exit={code} tb={tb} {text[:90]}")

    ctx = mp.get_context("spawn")
    ready = ctx.Event()
    holder = ctx.Process(target=_hold, args=(str(store.path), 14, ready))
    holder.start(); ready.wait(20)
    live_req = root / "live-cancel.json"
    with closing(sqlite3.connect(Path(store.path).as_uri() + "?mode=ro", uri=True)) as db:
        live_sid = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()[0]
    live_req.write_text(json.dumps(dict(protocol=CANCEL_PROTOCOL, store_id=live_sid, client_id="probe",
                                        command_key="c-3", mission_id=pending["id"], actor=ACTOR, reason=REASON)))
    for args in (("command-cancel", "--request", str(live_req)), ("cancel", pending["id"])):
        code, tb, text = cli(state, *args)
        raw = "database is locked" in text
        print(f"  write lock held, {args[0]:15} exit={code} traceback={tb} raw SQL text={raw} | {text[:110]}")
    holder.join(20)
    print(f"  after the lock: lookup c-3 -> {lookup_receipt(Store(state), store_id=live_sid, client_id='probe', command_key='c-3')['status']}")

    corrupt = root / "corrupt"
    corrupt.mkdir()
    (corrupt / "missions.sqlite3").write_bytes(b"not a database" * 100)
    for args in (("show", pending["id"]), ("recovery-inspect",)):
        code, tb, text = cli(corrupt, *args)
        print(f"  corrupt file, {args[0]:16} exit={code} traceback={tb} raw SQL text={'not a database' in text} | {text[:100]}")
    code, tb, text = cli(root, "recovery-prepare", "--source", str(corrupt / "missions.sqlite3"),
                         "--destination", str(root / "review2"), "--actor", ACTOR, "--reason", REASON)
    print(f"  prepare from corrupt source: exit={code} tb={tb} destination created={(root / 'review2').exists()} | {text[:90]}")
    shutil.rmtree(root)


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version} | target: {Path(recovery.__file__).parent.parent.parent.name}")
    for probe in (p1_concurrent_writer, p2_guards, p3_crashes, p4_cli):
        probe()
