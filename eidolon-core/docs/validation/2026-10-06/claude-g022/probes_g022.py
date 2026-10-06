# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g022.py
# Description : Contre-revue du suivi restauration 3f16d7d (C-TASK-G022)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Independent probes for C-TASK-G022, frozen target 3f16d7d (and, for comparison, 3a2a081).

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen>/eidolon-core/src \
        python docs/validation/2026-10-06/claude-g022/probes_g022.py

Synthetic temporary states only. A writer in another process commits during
prepare_review; backup steps can be slowed through a proxy around the
read-only source connection (as in G017 and Codex's own test); os._exit in a
child process at named steps. No activation path is created.
"""
import hashlib, json, multiprocessing as mp, os, shutil, sqlite3, subprocess, sys, tempfile, time
from contextlib import closing
from pathlib import Path

import eidolon_core.recovery as recovery
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands
from eidolon_core.contracts import ContractError
from eidolon_core.recovery import inspect_review, prepare_review
from eidolon_core.store import Store

ACTOR, REASON = "probe-G022", "synthetic restore rehearsal G022"


def section(t): print(f"\n== {t}")
def files(d): return sorted(p.name for p in Path(d).iterdir()) if Path(d).exists() else None
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def outcome(fn):
    try:
        r = fn()
        return "OK" if isinstance(r, dict) else ("OK " + type(r).__name__)
    except (ContractError, sqlite3.Error, ValueError, KeyError, OSError) as exc:
        return f"{type(exc).__name__}: {str(exc)[:70]}"


def source_state(root):
    store = Store(Path(root) / "source"); rt = ActionRuntime(store)
    m = rt.run(rt.create_restart("nas")["id"])
    rt.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve", actor=ACTOR, reason="kept as history")
    other = rt.run(rt.create_restart("nas")["id"])
    sid = ClientSync(store).snapshot(other["id"])["store_id"]
    CancelCommands(store).submit(dict(protocol=CANCEL_PROTOCOL, store_id=sid, client_id="probe", command_key="c-1",
                                      mission_id=other["id"], actor=ACTOR, reason=REASON))
    return store, m


def filler(store, mib):
    with closing(sqlite3.connect(store.path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS g022_filler (b BLOB)")
        db.executemany("INSERT INTO g022_filler VALUES (?)", [(os.urandom(4096),) for _ in range(mib * 256)])
        db.commit()


def _writer(path, until, period, out):
    store = Store(path); lat, fails, made = [], [], 0
    while time.time() < until:
        t0 = time.monotonic()
        try:
            store.create("writer mission", {"probe": "writer"}); made += 1
        except sqlite3.Error as exc:
            fails.append(str(exc))
        lat.append(time.monotonic() - t0); time.sleep(period)
    out.put((made, max(lat) if lat else 0, len(fails), fails[:1]))


class SlowSource:
    def __init__(self, db, delay): self.db, self.delay, self.steps = db, delay, 0
    def __getattr__(self, n): return getattr(self.db, n)
    def backup(self, target, *, pages, progress, sleep):
        def slowed(status, remaining, total):
            self.steps += 1; time.sleep(self.delay); progress(status, remaining, total)
        return self.db.backup(target, pages=pages, progress=slowed, sleep=sleep)


def linked(db_path):
    with closing(sqlite3.connect(Path(db_path).as_uri() + "?mode=ro", uri=True)) as db:
        missions = {r[0] for r in db.execute("SELECT id FROM missions")}
        orphans = db.execute("SELECT count(*) FROM events WHERE mission_id NOT IN (SELECT id FROM missions)").fetchone()[0]
        no_created = sum(1 for m in missions if not db.execute("SELECT 1 FROM events WHERE mission_id=? AND kind='CREATED'", (m,)).fetchone())
        bad = sum(1 for (b,) in db.execute("SELECT body FROM command_receipts")
                  if json.loads(b)["mission_id"] not in missions or not db.execute("SELECT 1 FROM events WHERE sequence=?", (json.loads(b)["event_sequence"],)).fetchone())
        return len(missions), orphans, no_created, bad


def p1_writer():
    section("1 writer in another process during prepare (default journal and WAL)")
    ctx = mp.get_context("spawn")
    for journal, delay, period, seconds in (("delete", 0.4, 0.02, 9), ("delete", 0.4, 1.5, 9), ("wal", 0.4, 1.5, 9), ("delete", 0.0, 0.02, 3)):
        root = Path(tempfile.mkdtemp(prefix="g022-")); store, _ = source_state(root); filler(store, 16)
        if journal == "wal":
            with closing(sqlite3.connect(store.path)) as db: db.execute("PRAGMA journal_mode=WAL")
        q = ctx.Queue(); w = ctx.Process(target=_writer, args=(str(store.directory), time.time() + seconds, period, q)); w.start(); time.sleep(0.3)
        original = recovery._readonly; proxies = []
        def wrapped(path, d=delay):
            db = original(path)
            if not d: return db
            proxies.append(SlowSource(db, d)); return proxies[-1]
        recovery._readonly = wrapped
        t0 = time.monotonic()
        try:
            res = outcome(lambda: prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON))
        finally:
            recovery._readonly = original
        took = time.monotonic() - t0
        made, worst, nfail, fails = q.get(timeout=90); w.join(10)
        pub = root / "review" / "missions.sqlite3"
        rep = inspect_review(root / "review") if pub.exists() else None
        print(f"  journal={journal:6} step delay={delay}s writer every {period}s: prepare {took:.1f}s -> {res} | backup steps={sum(p.steps for p in proxies)}")
        print(f"      writer: {made} commits, worst wait {worst:.2f}s, failures={nfail} {fails}")
        print(f"      copy (missions, orphan events, missions w/o CREATED, unlinked receipts)={linked(pub) if pub.exists() else None} "
              f"| capture_semantics={rep and rep.get('capture_semantics')} | dest files={files(root / 'review')}")
        shutil.rmtree(root)


def p2_identity_change():
    section("2 source identity changed (raw SQL) between preflight and end of backup")
    root = Path(tempfile.mkdtemp(prefix="g022-")); store, _ = source_state(root); filler(store, 4)
    original = recovery._readonly
    class Changer(SlowSource):
        def backup(self, target, *, pages, progress, sleep):
            def change(status, remaining, total):
                if self.steps == 0:
                    with closing(sqlite3.connect(store.path)) as db:
                        db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ("s-" + "c" * 32,)); db.commit()
                self.steps += 1; progress(status, remaining, total)
            return self.db.backup(target, pages=pages, progress=change, sleep=sleep)
    recovery._readonly = lambda p: Changer(original(p), 0)
    try:
        res = outcome(lambda: prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON))
    finally:
        recovery._readonly = original
    print(f"  -> {res} | dest files={files(root / 'review')} | Store(dest) -> {outcome(lambda: Store(root / 'review'))} "
          f"| inspect -> {outcome(lambda: inspect_review(root / 'review'))}")
    shutil.rmtree(root)


CHILD = r'''
import os, sys, pathlib
import eidolon_core.recovery as recovery
point = sys.argv[3]; die = lambda *a, **k: os._exit(77)
if point == "during-backup":
    original = recovery._readonly
    class P:
        def __init__(s, db): s.db = db
        def __getattr__(s, n): return getattr(s.db, n)
        def backup(s, target, **kw): kw["progress"] = die; return s.db.backup(target, **kw)
    recovery._readonly = lambda p: P(original(p))
elif point == "after-backup-before-guard": recovery.hashlib.file_digest = die
elif point == "after-guard-before-link": recovery.os.link = die
elif point == "after-link-before-unlink": pathlib.Path.unlink = die
elif point == "after-publication-before-reply": recovery.inspect_review = die
recovery.prepare_review(sys.argv[1], sys.argv[2], actor="probe", reason="crash probe")
'''


def p3_crashes():
    section("3 abrupt exit at each step; then manual marker removal (G017 L1)")
    for point in ("during-backup", "after-backup-before-guard", "after-guard-before-link", "after-link-before-unlink", "after-publication-before-reply"):
        root = Path(tempfile.mkdtemp(prefix="g022-")); store, _ = source_state(root); before = sha(store.path); dest = root / "review"
        p = subprocess.run([sys.executable, "-c", CHILD, str(store.path), str(dest), point], capture_output=True, text=True, timeout=90, env=os.environ)
        cli = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(dest), "recovery-inspect"], capture_output=True, text=True, timeout=60, env=os.environ)
        print(f"  {point:31} exit={p.returncode} files={files(dest)} source unchanged={sha(store.path) == before}")
        print(f"      Store(dest) -> {outcome(lambda: Store(dest))} | inspect -> {outcome(lambda: inspect_review(dest))} "
              f"| CLI inspect exit={cli.returncode} {(cli.stderr or cli.stdout).strip()[:80]}")
        (dest / "RECOVERY-REVIEW-ONLY").unlink(missing_ok=True)
        print(f"      marker removed: Store(dest) -> {outcome(lambda: Store(dest))} | inspect -> {outcome(lambda: inspect_review(dest))} | files={files(dest)}")
        shutil.rmtree(root)


def p4_published():
    section("4 published copy: historical only, never activatable")
    root = Path(tempfile.mkdtemp(prefix="g022-")); store, m = source_state(root)
    rep = prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON)
    hist = inspect_review(root / "review", mission_id=m["id"])["mission"]
    (root / "review" / "RECOVERY-REVIEW-ONLY").unlink()
    print(f"  report: capture_semantics={rep['capture_semantics']} execution_authority={rep['execution_authority']} "
          f"| APPROVED kept as history: {hist['proposal_status_at_snapshot']} | marker removed, Store -> {outcome(lambda: Store(root / 'review'))}")
    live = root / "live"; live.mkdir(); (live / "review.pending.sqlite3").write_bytes(b"")
    print(f"  live directory holding a stray review.pending.sqlite3 -> {outcome(lambda: Store(live))} | files={files(live)}")
    shutil.rmtree(root)


if __name__ == "__main__" and not os.environ.get("G022_ONLY"):
    print(f"python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version} | recovery.py sha={sha(recovery.__file__)}")
    for probe in (p1_writer, p2_identity_change, p3_crashes, p4_published):
        probe()


def p5_continuous():
    section("5 continuous writes for longer than the 30 s backup budget (default journal)")
    ctx = mp.get_context("spawn")
    root = Path(tempfile.mkdtemp(prefix="g022-")); store, _ = source_state(root); filler(store, 16)
    q = ctx.Queue(); w = ctx.Process(target=_writer, args=(str(store.directory), time.time() + 40, 0.05, q)); w.start(); time.sleep(0.3)
    original = recovery._readonly
    recovery._readonly = lambda p: SlowSource(original(p), 0.2)
    t0 = time.monotonic()
    try:
        res = outcome(lambda: prepare_review(store.path, root / "review", actor=ACTOR, reason=REASON))
    finally:
        recovery._readonly = original
    took = time.monotonic() - t0
    made, worst, nfail, fails = q.get(timeout=90); w.join(10)
    print(f"  prepare {took:.1f}s -> {res} | writer {made} commits, failures={nfail}, worst wait {worst:.2f}s")
    print(f"  dest files={files(root / 'review')} | Store(dest) -> {outcome(lambda: Store(root / 'review'))} | inspect -> {outcome(lambda: inspect_review(root / 'review'))}")
    shutil.rmtree(root)


if __name__ == "__main__" and os.environ.get("G022_ONLY") == "p5":
    p5_continuous()
