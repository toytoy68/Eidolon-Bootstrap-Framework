# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recovery.py
# Description : Copie historique de restauration bloquée pour revue locale
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Prepare a NEW review directory; never restore over a working runtime.

Only the mission SQLite snapshot is copied. Worker leases/receipts, simulation
worlds, external effects and Memory Engine are NOT restored or reconciled.
"""
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .contracts import ContractError, encode, snapshot
from .store import now

MAX_DATABASE_BYTES = 256 * 1024 * 1024
MAX_INSPECTION_MISSIONS = 10000
MAX_INSPECTION_BODY = 16 * 1024 * 1024
MAX_INSPECTION_REPORT = 32768
INSPECTION_SECONDS = 2.0
REPORT_PROTOCOL = "eidolon-recovery-review/1"


def _readonly(path):
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only=ON")
    return db


def _source_identity(db):
    if db.execute("PRAGMA user_version").fetchone()[0] != 1:
        raise ContractError("UNSUPPORTED_RECOVERY_SCHEMA: expected mission database version 1")
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"missions", "events", "sync_metadata", "command_receipts"} <= tables:
        raise ContractError("UNSUPPORTED_RECOVERY_SCHEMA: required tables missing")
    if db.execute("SELECT 1 FROM sync_metadata WHERE key='recovery_mode'").fetchone():
        raise ContractError("RECOVERY_REVIEW_ONLY: cannot prepare a runtime from a review copy")
    row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
    if row is None or not re.fullmatch(r"s-[0-9a-f]{32}", row[0]):
        raise ContractError("INVALID_STORE_ID")
    return row[0]


def prepare_review(source_database, destination, *, actor, reason):
    """Bounded SQLite backup to a new directory, published only after guarding it."""
    for name, value, bound in (("actor", actor, 200), ("reason", reason, 4000)):
        if not isinstance(value, str) or not value.strip() or len(value) > bound:
            raise ContractError("explicit bounded " + name + " required")
    snapshot({"actor": actor, "reason": reason})
    source = Path(source_database).resolve(strict=True)
    target = Path(destination).resolve()
    if not source.is_file() or target == source.parent or target.is_relative_to(source.parent):
        raise ContractError("RECOVERY_DESTINATION: use a new directory outside the source state")
    if target.exists():
        raise FileExistsError("recovery destination must not already exist")
    if source.stat().st_size > MAX_DATABASE_BYTES:
        raise ContractError("RECOVERY_SIZE_LIMIT: database exceeds 256 MiB")
    # Validate in a short transaction, then release it BEFORE incremental backup.
    # Pinning it for the whole copy starves commits in rollback-journal mode.
    with closing(_readonly(source)) as original:
        original.execute("BEGIN")
        source_id = _source_identity(original)
        pages = original.execute("PRAGMA page_count").fetchone()[0]
        size = original.execute("PRAGMA page_size").fetchone()[0]
        if pages * size > MAX_DATABASE_BYTES:
            raise ContractError("RECOVERY_SIZE_LIMIT: logical database exceeds 256 MiB")
        original.rollback()
        target.mkdir(mode=0o700)  # no overwrite, no auto-created parent hierarchy
        with (target / "RECOVERY-REVIEW-ONLY").open("x", encoding="utf-8") as marker:
            marker.write("Historical recovery copy. Use recovery-inspect; never start a runtime here.\n")
            marker.flush()
            os.fsync(marker.fileno())
        pending = target / "review.pending.sqlite3"
        deadline = time.monotonic() + 30

        def progress(status, remaining, total):
            if total * size > MAX_DATABASE_BYTES or time.monotonic() >= deadline:
                raise ContractError("RECOVERY_BACKUP_LIMIT: review copy is incomplete")

        with closing(sqlite3.connect(pending)) as copied:
            original.backup(copied, pages=256, progress=progress, sleep=0.01)
            # External commits can restart SQLite's backup. Validate the finished
            # snapshot itself; never attach stale preflight identity/schema to it.
            if _source_identity(copied) != source_id:
                raise ContractError("RECOVERY_SOURCE_CHANGED: copied identity differs from preflight")
            copied_pages = copied.execute("PRAGMA page_count").fetchone()[0]
            copied_size = copied.execute("PRAGMA page_size").fetchone()[0]
            if copied_pages * copied_size > MAX_DATABASE_BYTES:
                raise ContractError("RECOVERY_SIZE_LIMIT: completed snapshot exceeds 256 MiB")
            copied.execute("PRAGMA journal_mode=DELETE")
    # Digest describes the snapshot BEFORE its new identity and guard, not a
    # checksum of a concurrently changing source file or an external effect.
    with pending.open("rb") as handle:
        source_snapshot_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    report = {"protocol": REPORT_PROTOCOL, "recovery_id": "r-" + uuid.uuid4().hex,
              "mode": "REVIEW_ONLY", "source_store_id": source_id,
              "store_id": "s-" + uuid.uuid4().hex, "source_snapshot_sha256": source_snapshot_sha,
              "prepared_at": now(), "actor": actor, "reason": reason,
              "capture_semantics": "sqlite-online-backup",
              "historical_only": True, "execution_authority": False,
              "external_effects_reconciled": False, "artifacts_restored": ["mission_sqlite_only"]}
    with closing(sqlite3.connect(pending)) as copied:
        copied.execute("PRAGMA synchronous=FULL")
        if copied.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ContractError("RECOVERY_INTEGRITY: copied database failed quick_check")
        with copied:
            copied.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", (report["store_id"],))
            copied.execute("INSERT INTO sync_metadata(key,value) VALUES ('recovery_mode','REVIEW_ONLY')")
            copied.execute("INSERT INTO sync_metadata(key,value) VALUES ('recovery_report',?)", (encode(report),))
    # An incomplete copy never has the runtime database filename. link() is
    # atomic and refuses an existing destination; rename() could overwrite it.
    with pending.open("rb") as handle:
        os.fsync(handle.fileno())
    os.link(pending, target / "missions.sqlite3")
    pending.unlink()
    directory_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return inspect_review(target)


def _inspection_json(raw, maximum):
    if type(raw) is not bytes or len(raw) > maximum:
        raise ContractError("RECOVERY_INSPECTION_LIMIT")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError()
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("INVALID_RECOVERY_RECORD") from None


def _inspection_report(raw):
    report = _inspection_json(raw, MAX_INSPECTION_REPORT)
    required = {"protocol", "recovery_id", "mode", "source_store_id", "store_id",
                "source_snapshot_sha256", "prepared_at", "actor", "reason", "historical_only",
                "execution_authority", "external_effects_reconciled", "artifacts_restored"}
    try:
        if (type(report) is not dict or not required <= set(report)
                or not set(report) <= required | {"capture_semantics"}
                or report["protocol"] != REPORT_PROTOCOL or report["mode"] != "REVIEW_ONLY"
                or report["historical_only"] is not True or report["execution_authority"] is not False
                or report["external_effects_reconciled"] is not False
                or report["artifacts_restored"] != ["mission_sqlite_only"]
                or ("capture_semantics" in report and report["capture_semantics"] != "sqlite-online-backup")):
            raise ValueError()
        for field, pattern in (("recovery_id", r"r-[0-9a-f]{32}"), ("source_store_id", r"s-[0-9a-f]{32}"),
                               ("store_id", r"s-[0-9a-f]{32}"), ("source_snapshot_sha256", r"[0-9a-f]{64}")):
            if type(report[field]) is not str or re.fullmatch(pattern, report[field]) is None:
                raise ValueError()
        if report["source_store_id"] == report["store_id"]:
            raise ValueError()
        for field, maximum in (("actor", 200), ("reason", 4000), ("prepared_at", 80)):
            if type(report[field]) is not str or not report[field].strip() or len(report[field]) > maximum:
                raise ValueError()
            report[field].encode("utf-8")
        if datetime.fromisoformat(report["prepared_at"]).utcoffset() is None:
            raise ValueError()
        return report
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ContractError("RECOVERY_REPORT_MISMATCH") from None


def _inspection_mission(row):
    from .store import Store, TERMINAL
    identity, revision, cancel, raw = row
    mission = _inspection_json(raw, MAX_INSPECTION_BODY)
    try:
        Store.check_id(identity)
        if (type(mission) is not dict or mission.get("id") != identity
                or type(revision) is not int or not 0 <= revision <= 2**53-1
                or type(cancel) is not int or cancel not in (0, 1)
                or mission.get("status") not in TERMINAL | {"NEW", "RUNNING", "BLOCKED", "REVIEW_REQUIRED"}
                or mission.get("phase") not in {"RECALL", "PLAN", "READY", "EXECUTING", "VERIFY", "DONE"}
                or type(mission.get("calls")) is not list or len(mission["calls"]) > 5):
            raise ValueError()
        proposal = mission.get("proposal")
        if proposal is not None and (type(proposal) is not dict
                or proposal.get("status") not in {"PENDING", "APPROVED", "REJECTED", "REVOKED", "USED"}):
            raise ValueError()
        calls = []
        for call in mission["calls"]:
            if (type(call) is not dict or type(call.get("id")) is not str or not 1 <= len(call["id"]) <= 120
                    or call.get("status") not in {"PREPARED", "STARTED", "RETURNED", "VERIFIED", "UNKNOWN"}):
                raise ValueError()
            call["id"].encode("utf-8")
            calls.append({"id": call["id"], "status": call["status"]})
        return {"id": identity, "revision": revision, "status_at_snapshot": mission["status"],
                "phase_at_snapshot": mission["phase"], "cancel_requested_at_snapshot": bool(cancel),
                "proposal_status_at_snapshot": proposal["status"] if proposal is not None else None,
                "calls_at_snapshot": calls}
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ContractError("INVALID_RECOVERY_MISSION") from None


def _inspect_review(directory, *, mission_id=None):
    """Read historical metadata and optionally one mission; never construct Store."""
    root = Path(directory).resolve()
    path = root / "missions.sqlite3"
    if not path.exists() and any((root / name).exists() for name in
                                ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3")):
        raise ContractError("RECOVERY_INCOMPLETE: review copy was not published; retain its files")
    with closing(_readonly(path)) as db:
        deadline = time.monotonic() + INSPECTION_SECONDS
        db.execute("PRAGMA busy_timeout=2000")
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute("BEGIN")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ContractError("UNSUPPORTED_RECOVERY_SCHEMA")
        if db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0] > MAX_DATABASE_BYTES:
            raise ContractError("RECOVERY_INSPECTION_LIMIT")
        mode = db.execute("SELECT substr(value,1,17) FROM sync_metadata WHERE key='recovery_mode'").fetchone()
        if mode != ("REVIEW_ONLY",):
            raise ContractError("NOT_A_RECOVERY_COPY")
        row = db.execute("SELECT substr(CAST(value AS BLOB),1,?) FROM sync_metadata WHERE key='recovery_report'",
                         (MAX_INSPECTION_REPORT + 1,)).fetchone()
        if row is None:
            raise ContractError("RECOVERY_REPORT_MISSING")
        report = _inspection_report(row[0])
        identity = db.execute("SELECT substr(value,1,35) FROM sync_metadata WHERE key='store_id'").fetchone()
        if identity != (report["store_id"],):
            raise ContractError("RECOVERY_REPORT_MISMATCH")
        report["counts"] = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                            for table in ("missions", "events", "command_receipts")}
        report["historical_status_counts"] = {}
        if report["counts"]["missions"] > MAX_INSPECTION_MISSIONS:
            raise ContractError("RECOVERY_INSPECTION_LIMIT")
        selected = None
        if mission_id is not None:
            from .store import Store
            Store.check_id(mission_id)
        for row in db.execute("SELECT id,revision,cancel_requested,substr(CAST(body AS BLOB),1,?) FROM missions LIMIT ?",
                              (MAX_INSPECTION_BODY + 1, MAX_INSPECTION_MISSIONS + 1)):
            if time.monotonic() >= deadline:
                raise ContractError("RECOVERY_INSPECTION_LIMIT")
            projection = _inspection_mission(row)
            status = projection["status_at_snapshot"]
            report["historical_status_counts"][status] = report["historical_status_counts"].get(status, 0) + 1
            if projection["id"] == mission_id:
                selected = projection
        if mission_id is not None:
            if selected is None:
                raise ContractError("RECOVERY_MISSION_NOT_FOUND")
            report["mission"] = selected
        return report


def inspect_review(directory, *, mission_id=None):
    """Strict bounded historical inspection; no repair, activation or writes."""
    try:
        return _inspect_review(directory, mission_id=mission_id)
    except sqlite3.OperationalError as exc:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ContractError("RECOVERY_INSPECTION_LIMIT") from None
        raise
