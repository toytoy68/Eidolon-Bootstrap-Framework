# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : rotation.py
# Description : PROTOTYPE ISOLÉ — export puis retrait explicite d'anciennes recherches de la garde (C-TASK-G057)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Prototype only: never imported by Core, never run on a real journal.

rotate(directory, archive_dir, count=K, operations=()) exports the K oldest FINISHED runs
(COMPLETED or RESOLVED_UNKNOWN), with their audit events and cleaned-query rows copied
byte for byte, into ONE new private file, then removes exactly those rows and appends a
chain entry, in one SQLite transaction. The journal becomes schema 3 (table `archives`),
which today's research_guard refuses on purpose: Codex decides the integration.

Refusals: lock held (IN_FLIGHT), any INTENT, invalid journal, leftover partial export,
unknown or uncommitted export, run linked to a mission (operation_id) not explicitly
released, nothing eligible. No age rule, no retention duration, no lock re-creation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile

import fcntl

PROTOCOL = "eidolon-research-archive/1"
FINISHED = {"COMPLETED", "RESOLVED_UNKNOWN"}


class RotationError(Exception):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _crash(point):
    # Fault injection for the probes only: G057_CRASH_AT=<point> kills the process there.
    if os.environ.get("G057_CRASH_AT") == point:
        os._exit(9)


def _private_file(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RotationError("NOT_PRIVATE")


def _lock(directory):
    path = Path(directory) / "research-runs.lock"
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)   # never created here
    except FileNotFoundError:
        raise RotationError("RESEARCH_LOCK_MISSING") from None
    _private_file(path)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RotationError("WEB_RESEARCH_IN_FLIGHT") from None
    return fd


def _chain(db):
    rows = db.execute("SELECT seq, body FROM archives ORDER BY seq").fetchall() if _has_archives(db) else []
    previous = "0" * 64
    for i, (seq, body) in enumerate(rows, 1):
        entry = json.loads(body)
        if seq != i or entry["index"] != i or entry["previous_chain_sha256"] != previous:
            raise RotationError("ARCHIVE_CHAIN_BROKEN")
        previous = _sha(_canon(entry))
    return rows, previous


def _has_archives(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='archives'").fetchone() is not None


def _validate_with_guard(directory, guard_src):
    """Validate the journal with the UNCHANGED research_guard, on a schema-2 shadow copy."""
    import sys
    if guard_src not in sys.path:
        sys.path.insert(0, guard_src)
    from eidolon_core.research_guard import ResearchGuard
    with tempfile.TemporaryDirectory(prefix="g057-shadow-") as tmp:
        shadow = Path(tmp) / "guard"
        shadow.mkdir(mode=0o700)
        shutil.copy2(Path(directory) / "research-runs.sqlite3", shadow / "research-runs.sqlite3")
        os.chmod(shadow / "research-runs.sqlite3", 0o600)
        fd = os.open(shadow / "research-runs.lock", os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        db = sqlite3.connect(shadow / "research-runs.sqlite3")
        if _has_archives(db):
            db.execute("DROP TABLE archives")
            db.execute("PRAGMA user_version=2")
            db.commit()
        db.close()
        guard = ResearchGuard(shadow, create=False)
        return guard.inspect()["runs"]


def _exports(archive_dir):
    return sorted(p for p in Path(archive_dir).glob("research-archive-*.json"))


def verify(directory, archive_dir):
    """Chain in the journal vs export files: missing, altered, unknown or rolled-back."""
    db = sqlite3.connect(Path(directory) / "research-runs.sqlite3")
    try:
        rows, head = _chain(db)
        present = {r[0] for r in db.execute("SELECT id FROM runs")}
    finally:
        db.close()
    known = {}
    for seq, body in rows:
        entry = json.loads(body)
        path = Path(archive_dir) / entry["file"]
        if not path.exists():
            raise RotationError("ARCHIVE_MISSING")
        _private_file(path)
        data = path.read_bytes()
        if _sha(data) != entry["export_sha256"]:
            raise RotationError("ARCHIVE_ALTERED")
        if any(run["id"] in present for run in json.loads(data)["runs"]):
            raise RotationError("ARCHIVED_RUN_REAPPEARED")
        known[entry["file"]] = entry
    unknown = [json.loads(p.read_bytes()) for p in _exports(archive_dir) if p.name not in known]
    if unknown:
        # Exactly one export extending the chain head: a crash between publication and
        # commit (resume_uncommitted can finish it). It is indistinguishable from a journal
        # restored to just before ONE rotation. Anything else: the journal went back further.
        single = (len(unknown) == 1 and unknown[0]["chain_index"] == len(rows) + 1
                  and unknown[0]["previous_chain_sha256"] == head)
        raise RotationError("UNCOMMITTED_EXPORT" if single else "JOURNAL_ROLLED_BACK")
    if list(Path(archive_dir).glob("*.partial")):
        raise RotationError("PARTIAL_EXPORT_PRESENT")
    return {"archives": len(rows), "chain_head": head}


def rotate(directory, archive_dir, *, count, operations=(), guard_src, clock_ms):
    directory, archive_dir = Path(directory), Path(archive_dir)
    if type(count) is not int or not 1 <= count <= 256:
        raise RotationError("INVALID_COUNT")
    if not archive_dir.is_dir() or archive_dir.stat().st_mode & 0o077 or archive_dir.resolve() == directory.resolve():
        raise RotationError("ARCHIVE_DIR_NOT_PRIVATE")
    fd = _lock(directory)
    try:
        verify(directory, archive_dir)                 # refuses partials, unknown exports, rollback
        runs = _validate_with_guard(directory, guard_src)
        if any(r["state"] == "INTENT" for r in runs):
            raise RotationError("WEB_RESEARCH_UNCERTAIN")
        db = sqlite3.connect(directory / "research-runs.sqlite3", isolation_level=None)
        rows, head = _chain(db)
        released = set(operations)
        eligible = [r for r in sorted(runs, key=lambda r: (r["started_at_ms"], r["id"]))
                    if r["state"] in FINISHED
                    and ("operation_id" not in r["descriptor"] or r["descriptor"]["operation_id"] in released)]
        chosen = eligible[:count]
        if not chosen:
            raise RotationError("NOTHING_ELIGIBLE")
        ids = [r["id"] for r in chosen]
        exported = []
        for identity in ids:
            body = db.execute("SELECT body FROM runs WHERE id=?", (identity,)).fetchone()[0]
            events = db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? ORDER BY sequence",
                                (identity,)).fetchall()
            query = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone() \
                if db.execute("PRAGMA user_version").fetchone()[0] >= 2 else None
            exported.append({"id": identity, "body": body, "events": [list(e) for e in events],
                             "cleaned_query": query[0] if query else None})
        index = len(rows) + 1
        meta = {"protocol": PROTOCOL, "guard_id": runs[0]["guard_id"], "chain_index": index,
                "previous_chain_sha256": head, "created_at_ms": clock_ms, "runs": exported,
                "removed_ids_sha256": _sha(_canon(ids)), "authorizes_execution": False}
        data = _canon(meta)
        name = f"research-archive-{index:06d}.json"
        partial = archive_dir / (name + "." + os.urandom(8).hex() + ".partial")
        out = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.write(out, data)
            _crash("after_partial_write")
            os.fsync(out)
        finally:
            os.close(out)
        os.link(partial, archive_dir / name)          # exclusive publication: fails if the name exists
        os.unlink(partial)
        dfd = os.open(archive_dir, os.O_RDONLY)
        os.fsync(dfd)
        os.close(dfd)
        _crash("after_publish")
        entry = {"index": index, "file": name, "export_sha256": _sha(data), "previous_chain_sha256": head,
                 "removed_ids_sha256": meta["removed_ids_sha256"], "count": len(ids)}
        db.execute("BEGIN IMMEDIATE")
        try:
            if not _has_archives(db):
                db.execute("CREATE TABLE archives (seq INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            for identity in ids:
                db.execute("DELETE FROM run_events WHERE run_id=?", (identity,))
                db.execute("DELETE FROM cleaned_queries WHERE run_id=?", (identity,)) \
                    if db.execute("PRAGMA user_version").fetchone()[0] >= 2 else None
                db.execute("DELETE FROM runs WHERE id=?", (identity,))
            db.execute("INSERT INTO archives VALUES (?,?)", (index, _canon(entry).decode()))
            db.execute("PRAGMA user_version=3")
            _crash("inside_transaction")
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()
        _crash("after_commit")
        return {"archived": len(ids), "file": name, "chain_index": index, "request_sent": False}
    finally:
        os.close(fd)


def resume_uncommitted(directory, archive_dir, *, guard_src):
    """After a crash between publication and commit: commit only if the export still
    matches the journal byte for byte and extends its chain head. Never re-exports."""
    directory, archive_dir = Path(directory), Path(archive_dir)
    fd = _lock(directory)
    try:
        db = sqlite3.connect(directory / "research-runs.sqlite3", isolation_level=None)
        rows, head = _chain(db)
        known = {json.loads(b)["file"] for _, b in rows}
        orphans = [p for p in _exports(archive_dir) if p.name not in known]
        if len(orphans) != 1:
            raise RotationError("NO_SINGLE_UNCOMMITTED_EXPORT")
        data = orphans[0].read_bytes()
        meta = json.loads(data)
        if meta["previous_chain_sha256"] != head or meta["chain_index"] != len(rows) + 1:
            raise RotationError("JOURNAL_ROLLED_BACK")
        runs = _validate_with_guard(directory, guard_src)
        if any(r["state"] == "INTENT" for r in runs):
            raise RotationError("WEB_RESEARCH_UNCERTAIN")
        for run in meta["runs"]:
            body = db.execute("SELECT body FROM runs WHERE id=?", (run["id"],)).fetchone()
            events = [list(e) for e in db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? "
                                                  "ORDER BY sequence", (run["id"],))]
            if body is None or body[0] != run["body"] or events != run["events"]:
                raise RotationError("EXPORT_DOES_NOT_MATCH_JOURNAL")
        ids = [r["id"] for r in meta["runs"]]
        entry = {"index": meta["chain_index"], "file": orphans[0].name, "export_sha256": _sha(data),
                 "previous_chain_sha256": head, "removed_ids_sha256": meta["removed_ids_sha256"], "count": len(ids)}
        db.execute("BEGIN IMMEDIATE")
        if not _has_archives(db):
            db.execute("CREATE TABLE archives (seq INTEGER PRIMARY KEY, body TEXT NOT NULL)")
        for identity in ids:
            db.execute("DELETE FROM run_events WHERE run_id=?", (identity,))
            db.execute("DELETE FROM cleaned_queries WHERE run_id=?", (identity,))
            db.execute("DELETE FROM runs WHERE id=?", (identity,))
        db.execute("INSERT INTO archives VALUES (?,?)", (meta["chain_index"], _canon(entry).decode()))
        db.execute("PRAGMA user_version=3")
        db.execute("COMMIT")
        db.close()
        return {"archived": len(ids), "file": orphans[0].name, "resumed": True}
    finally:
        os.close(fd)
