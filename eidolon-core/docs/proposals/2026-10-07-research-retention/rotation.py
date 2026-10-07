# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : rotation.py
# Description : PROTOTYPE ISOLÉ v2 — export puis retrait des anciennes recherches de la garde (C-TASK-G057/G062)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Prototype only: never imported by Core, never run on a real journal.

v2 (G062) after Codex's counter-probes (codex-g057-review):
- every removal (rotate, resume, auto) first validates the WHOLE archive chain, then the
  export against the journal rows byte for byte, cleaned_queries and guard identity
  included; nothing is removed on any doubt;
- the journal is read through SQLite's online backup API (WAL included), under the
  guard lock, then re-compared row by row inside the deleting transaction;
- exports are read with bounds (size, count, strict JSON) and descriptors are closed
  on every refusal path;
- auto_rotate() keeps TARGET active runs (C-D17: about 100), never removes a run linked
  to a mission that the caller does not declare terminal, and reports any overshoot.

The journal becomes schema 3 (table `archives`); today's research_guard refuses it on
purpose. liste.md and the export reader belong to Codex (C-028): not implemented here."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile

import fcntl

PROTOCOL = "eidolon-research-archive/1"
FINISHED = {"COMPLETED", "RESOLVED_UNKNOWN"}
TARGET = 100                       # C-D17: « une centaine », read as 100 (follow-up answer)
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_EXPORTS = 4096
MAX_RUNS_PER_EXPORT = 256
EXPORT_KEYS = {"protocol", "guard_id", "chain_index", "previous_chain_sha256", "created_at_ms", "runs",
               "removed_ids_sha256", "released_operations", "authorizes_execution"}
RUN_KEYS = {"id", "body", "events", "cleaned_query"}


class RotationError(Exception):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _strict_json(data):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("duplicate key")
            out[k] = v
        return out

    def no_constant(_):
        raise ValueError("non-finite")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=no_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise RotationError("ARCHIVE_UNREADABLE") from None


def _crash(point):
    # Fault injection for the probes only: G057_CRASH_AT=<point> kills the process there.
    if os.environ.get("G057_CRASH_AT") == point:
        os._exit(9)


def _read_private(path, limit=None):
    """Open without following links, check owner/mode/size on the descriptor, always close it."""
    limit = MAX_EXPORT_BYTES if limit is None else limit
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise RotationError("ARCHIVE_MISSING") from None
    except OSError:
        raise RotationError("ARCHIVE_UNREADABLE") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RotationError("NOT_PRIVATE")
        if info.st_size > limit:
            raise RotationError("ARCHIVE_TOO_LARGE")
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise RotationError("ARCHIVE_TOO_LARGE")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _lock(directory):
    path = Path(directory) / "research-runs.lock"
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)   # never created here
    except FileNotFoundError:
        raise RotationError("RESEARCH_LOCK_MISSING") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RotationError("NOT_PRIVATE")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RotationError("WEB_RESEARCH_IN_FLIGHT") from None
    except BaseException:
        os.close(fd)
        raise
    return fd


def _has_archives(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='archives'").fetchone() is not None


def _chain(db):
    rows = db.execute("SELECT seq, body FROM archives ORDER BY seq").fetchall() if _has_archives(db) else []
    previous, entries = "0" * 64, []
    for i, (seq, body) in enumerate(rows, 1):
        entry = _strict_json(body.encode())
        if (seq != i or type(entry) is not dict or entry.get("index") != i
                or entry.get("previous_chain_sha256") != previous):
            raise RotationError("ARCHIVE_CHAIN_BROKEN")
        previous = _sha(_canon(entry))
        entries.append(entry)
    return entries, previous


def _exports(archive_dir):
    names = sorted(p for p in Path(archive_dir).glob("research-archive-*.json"))
    if len(names) > MAX_EXPORTS:
        raise RotationError("TOO_MANY_EXPORTS")
    return names


class _Snapshot:
    """Consistent copy of the live journal (online backup: WAL included), validated by the
    UNCHANGED research_guard on a schema-2 shadow. Rows are read from the same copy."""

    def __init__(self, directory, guard_src):
        import sys
        if guard_src not in sys.path:
            sys.path.insert(0, guard_src)
        from eidolon_core.research_guard import ResearchGuard
        self.tmp = tempfile.mkdtemp(prefix="g062-shadow-")
        try:
            shadow = Path(self.tmp) / "guard"
            shadow.mkdir(mode=0o700)
            target = shadow / "research-runs.sqlite3"
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            src = sqlite3.connect(f"file:{Path(directory) / 'research-runs.sqlite3'}?mode=ro", uri=True)
            dst = sqlite3.connect(target)
            try:
                src.backup(dst)
            finally:
                src.close()
            self.version = dst.execute("PRAGMA user_version").fetchone()[0]
            self.chain, self.head = _chain(dst)
            self.guard_id = dst.execute("SELECT value FROM metadata WHERE key='guard_id'").fetchone()[0]
            self.rows = {}
            for identity, body in dst.execute("SELECT id, body FROM runs"):
                events = [list(e) for e in dst.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? "
                                                        "ORDER BY sequence", (identity,))]
                query = (dst.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone()
                         if self.version >= 2 else None)
                self.rows[identity] = {"id": identity, "body": body, "events": events,
                                       "cleaned_query": query[0] if query else None}
            if _has_archives(dst):
                dst.execute("DROP TABLE archives")
                dst.execute("PRAGMA user_version=2")
                dst.commit()
            dst.close()
            fd = os.open(shadow / "research-runs.lock", os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)
            self.runs = ResearchGuard(shadow, create=False).inspect()["runs"]
        except BaseException:
            shutil.rmtree(self.tmp, ignore_errors=True)
            raise
        shutil.rmtree(self.tmp, ignore_errors=True)


def _check_archives(directory, archive_dir, snap, *, allow_uncommitted):
    """Every chained export present, private, bounded, unaltered and absent from the journal.
    Unknown exports: none, or (when allowed) exactly one extending the head."""
    known = {}
    for entry in snap.chain:
        if type(entry.get("file")) is not str or not re.fullmatch(r"research-archive-[0-9]{6}\.json", entry["file"]):
            raise RotationError("ARCHIVE_CHAIN_BROKEN")
        data = _read_private(Path(archive_dir) / entry["file"])
        if _sha(data) != entry["export_sha256"]:
            raise RotationError("ARCHIVE_ALTERED")
        meta = _strict_json(data)
        if meta.get("guard_id") != snap.guard_id or meta.get("chain_index") != entry["index"]:
            raise RotationError("ARCHIVE_ALTERED")
        if any(run.get("id") in snap.rows for run in meta.get("runs", [])):
            raise RotationError("ARCHIVED_RUN_REAPPEARED")
        known[entry["file"]] = entry
    if list(Path(archive_dir).glob("*.partial")):
        raise RotationError("PARTIAL_EXPORT_PRESENT")
    unknown = [p for p in _exports(archive_dir) if p.name not in known]
    if not unknown:
        return None
    metas = [(p, _read_private(p)) for p in unknown]
    parsed = [(p, d, _strict_json(d)) for p, d in metas]
    single = (len(parsed) == 1 and parsed[0][2].get("chain_index") == len(snap.chain) + 1
              and parsed[0][2].get("previous_chain_sha256") == snap.head)
    if not single:
        raise RotationError("JOURNAL_ROLLED_BACK")
    if not allow_uncommitted:
        raise RotationError("UNCOMMITTED_EXPORT")
    return parsed[0]


def _check_export(meta, snap, *, operations):
    """The export must be EXACTLY the journal rows it will remove (G062: no null cleaned_query,
    no foreign guard, no unreleased mission run, no state other than finished)."""
    if type(meta) is not dict or set(meta) != EXPORT_KEYS:
        raise RotationError("EXPORT_FORMAT")
    runs = meta["runs"]
    if (meta["protocol"] != PROTOCOL or meta["guard_id"] != snap.guard_id
            or meta["chain_index"] != len(snap.chain) + 1 or meta["previous_chain_sha256"] != snap.head
            or meta["authorizes_execution"] is not False or type(runs) is not list
            or not 1 <= len(runs) <= MAX_RUNS_PER_EXPORT or type(meta["released_operations"]) is not list):
        raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
    ids = [r.get("id") if type(r) is dict else None for r in runs]
    if len(set(ids)) != len(ids) or meta["removed_ids_sha256"] != _sha(_canon(ids)):
        raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
    if not set(meta["released_operations"]) <= set(operations):
        raise RotationError("MISSION_NOT_RELEASED")
    states = {r["id"]: r for r in snap.runs}
    for run in runs:
        if type(run) is not dict or set(run) != RUN_KEYS or run != snap.rows.get(run["id"]):
            raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
        record = states[run["id"]]
        if record["state"] not in FINISHED:
            raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
        operation = record["descriptor"].get("operation_id")
        if operation is not None and operation not in operations:
            raise RotationError("MISSION_NOT_RELEASED")
        if "query_history_sha256" in record["descriptor"] and run["cleaned_query"] is None:
            raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
    return ids


def _commit(directory, archive_name, data, meta, snap, ids):
    """Delete exactly the exported rows and chain the export, re-comparing the LIVE rows."""
    entry = {"index": meta["chain_index"], "file": archive_name, "export_sha256": _sha(data),
             "previous_chain_sha256": snap.head, "removed_ids_sha256": meta["removed_ids_sha256"], "count": len(ids)}
    db = sqlite3.connect(Path(directory) / "research-runs.sqlite3", isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        try:
            chain, head = _chain(db)
            if head != snap.head or len(chain) != len(snap.chain):
                raise RotationError("JOURNAL_CHANGED")
            v = db.execute("PRAGMA user_version").fetchone()[0]
            for run in meta["runs"]:
                live_body = db.execute("SELECT body FROM runs WHERE id=?", (run["id"],)).fetchone()
                live_events = [list(e) for e in db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? "
                                                           "ORDER BY sequence", (run["id"],))]
                live_query = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (run["id"],)).fetchone() \
                    if v >= 2 else None
                if (live_body is None or live_body[0] != run["body"] or live_events != run["events"]
                        or (live_query[0] if live_query else None) != run["cleaned_query"]):
                    raise RotationError("JOURNAL_CHANGED")
            if not _has_archives(db):
                db.execute("CREATE TABLE archives (seq INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            for identity in ids:
                db.execute("DELETE FROM run_events WHERE run_id=?", (identity,))
                if v >= 2:
                    db.execute("DELETE FROM cleaned_queries WHERE run_id=?", (identity,))
                db.execute("DELETE FROM runs WHERE id=?", (identity,))
            db.execute("INSERT INTO archives VALUES (?,?)", (meta["chain_index"], _canon(entry).decode()))
            db.execute("PRAGMA user_version=3")
            _crash("inside_transaction")
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    finally:
        db.close()
    _crash("after_commit")


def _publish(archive_dir, index, data):
    name = f"research-archive-{index:06d}.json"
    partial = Path(archive_dir) / (name + "." + os.urandom(8).hex() + ".partial")
    out = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        os.write(out, data)
        _crash("after_partial_write")
        os.fsync(out)
    finally:
        os.close(out)
    try:
        os.link(partial, Path(archive_dir) / name)   # exclusive publication: fails if the name exists
    finally:
        os.unlink(partial)
    dfd = os.open(archive_dir, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    _crash("after_publish")
    return name


def _check_dirs(directory, archive_dir):
    directory, archive_dir = Path(directory), Path(archive_dir)
    if (not archive_dir.is_dir() or archive_dir.is_symlink() or archive_dir.stat().st_mode & 0o077
            or archive_dir.resolve() == directory.resolve()):
        raise RotationError("ARCHIVE_DIR_NOT_PRIVATE")
    return directory, archive_dir


def _rotate_locked(directory, archive_dir, snap, *, count, operations, clock_ms):
    if any(r["state"] == "INTENT" for r in snap.runs):
        raise RotationError("WEB_RESEARCH_UNCERTAIN")
    released = set(operations)
    eligible = [r for r in sorted(snap.runs, key=lambda r: (r["started_at_ms"], r["id"]))
                if r["state"] in FINISHED
                and ("operation_id" not in r["descriptor"] or r["descriptor"]["operation_id"] in released)]
    chosen = eligible[:count]
    if not chosen:
        raise RotationError("NOTHING_ELIGIBLE")
    ids = [r["id"] for r in chosen]
    used = sorted({r["descriptor"]["operation_id"] for r in chosen if "operation_id" in r["descriptor"]})
    meta = {"protocol": PROTOCOL, "guard_id": snap.guard_id, "chain_index": len(snap.chain) + 1,
            "previous_chain_sha256": snap.head, "created_at_ms": clock_ms,
            "runs": [snap.rows[i] for i in ids], "removed_ids_sha256": _sha(_canon(ids)),
            "released_operations": used, "authorizes_execution": False}
    _check_export(meta, snap, operations=operations)       # same validation as a resume
    data = _canon(meta)
    if len(data) > MAX_EXPORT_BYTES:
        raise RotationError("ARCHIVE_TOO_LARGE")
    name = _publish(archive_dir, meta["chain_index"], data)
    _commit(directory, name, data, meta, snap, ids)
    return {"archived": len(ids), "file": name, "chain_index": meta["chain_index"], "request_sent": False}


def verify(directory, archive_dir, *, guard_src):
    """Read-only check of the journal (snapshot) against its archives."""
    directory, archive_dir = _check_dirs(directory, archive_dir)
    snap = _Snapshot(directory, guard_src)
    _check_archives(directory, archive_dir, snap, allow_uncommitted=False)
    return {"archives": len(snap.chain), "chain_head": snap.head, "active": len(snap.runs)}


def rotate(directory, archive_dir, *, count, operations=(), guard_src, clock_ms):
    if type(count) is not int or not 1 <= count <= MAX_RUNS_PER_EXPORT:
        raise RotationError("INVALID_COUNT")
    directory, archive_dir = _check_dirs(directory, archive_dir)
    fd = _lock(directory)
    try:
        snap = _Snapshot(directory, guard_src)
        _check_archives(directory, archive_dir, snap, allow_uncommitted=False)
        return _rotate_locked(directory, archive_dir, snap, count=count, operations=operations, clock_ms=clock_ms)
    finally:
        os.close(fd)


def _resume_locked(directory, archive_dir, snap, operations):
    orphan = _check_archives(directory, archive_dir, snap, allow_uncommitted=True)
    if orphan is None:
        raise RotationError("NO_SINGLE_UNCOMMITTED_EXPORT")
    path, data, meta = orphan
    if any(r["state"] == "INTENT" for r in snap.runs):
        raise RotationError("WEB_RESEARCH_UNCERTAIN")
    ids = _check_export(meta, snap, operations=operations)
    _commit(directory, path.name, data, meta, snap, ids)
    return {"archived": len(ids), "file": path.name, "resumed": True, "request_sent": False}


def resume_uncommitted(directory, archive_dir, *, operations=(), guard_src):
    """After a crash between publication and commit: commit only if the whole chain is intact
    and the export is exactly the current rows. Never re-exports, never guesses."""
    directory, archive_dir = _check_dirs(directory, archive_dir)
    fd = _lock(directory)
    try:
        return _resume_locked(directory, archive_dir, _Snapshot(directory, guard_src), operations)
    finally:
        os.close(fd)


def auto_rotate(directory, archive_dir, *, target=TARGET, terminal_operations=(), guard_src, clock_ms):
    """Safe boundary: call AFTER a research run is COMPLETED (lock free, no INTENT expected),
    never inside guard.execute. A refusal here says nothing about that research's effects.

    - stale .partial files (never referenced, data still in the journal) are removed;
    - a single uncommitted export extending the chain is finished first (resume rules);
    - then the oldest finished runs above `target` are archived, except runs of missions the
      caller does not declare terminal: if those keep the journal above target, it is reported."""
    if type(target) is not int or not 1 <= target <= 256:
        raise RotationError("INVALID_TARGET")
    directory, archive_dir = _check_dirs(directory, archive_dir)
    fd = _lock(directory)
    try:
        report = {"partials_removed": 0, "resumed": None, "archived": 0, "request_sent": False}
        for p in Path(archive_dir).glob("research-archive-*.partial"):
            info = os.lstat(p)
            if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid():
                os.unlink(p)
                report["partials_removed"] += 1
        snap = _Snapshot(directory, guard_src)
        if _check_archives(directory, archive_dir, snap, allow_uncommitted=True) is not None:
            report["resumed"] = _resume_locked(directory, archive_dir, snap, terminal_operations)
            snap = _Snapshot(directory, guard_src)
        excess = len(snap.runs) - target
        if excess > 0:
            try:
                done = _rotate_locked(directory, archive_dir, snap, count=min(excess, MAX_RUNS_PER_EXPORT),
                                      operations=terminal_operations, clock_ms=clock_ms)
                report.update(archived=done["archived"], file=done["file"])
            except RotationError as exc:
                if str(exc) != "NOTHING_ELIGIBLE":
                    raise
        after = len(snap.runs) - report["archived"]
        report.update(active=after, target=target, above_target=max(0, after - target))
        return report
    finally:
        os.close(fd)
