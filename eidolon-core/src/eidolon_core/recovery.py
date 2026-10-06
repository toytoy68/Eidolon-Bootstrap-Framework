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


def inspect_review(directory, *, mission_id=None):
    """Read historical metadata and optionally one mission; never construct Store."""
    root = Path(directory).resolve()
    path = root / "missions.sqlite3"
    if not path.exists() and any((root / name).exists() for name in
                                ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3")):
        raise ContractError("RECOVERY_INCOMPLETE: review copy was not published; retain its files")
    with closing(_readonly(path)) as db:
        db.execute("BEGIN")
        mode = db.execute("SELECT value FROM sync_metadata WHERE key='recovery_mode'").fetchone()
        if mode != ("REVIEW_ONLY",):
            raise ContractError("NOT_A_RECOVERY_COPY")
        row = db.execute("SELECT value FROM sync_metadata WHERE key='recovery_report'").fetchone()
        if row is None:
            raise ContractError("RECOVERY_REPORT_MISSING")
        report = json.loads(row[0])
        identity = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
        if report.get("protocol") != REPORT_PROTOCOL or identity != (report.get("store_id"),):
            raise ContractError("RECOVERY_REPORT_MISMATCH")
        report["counts"] = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                            for table in ("missions", "events", "command_receipts")}
        report["historical_status_counts"] = {}
        for (body,) in db.execute("SELECT body FROM missions"):
            status = json.loads(body)["status"]
            report["historical_status_counts"][status] = report["historical_status_counts"].get(status, 0) + 1
        if mission_id is not None:
            from .store import Store
            Store.check_id(mission_id)
            row = db.execute("SELECT revision,cancel_requested,body FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise KeyError("mission not found in historical copy")
            mission = json.loads(row[2])
            report["mission"] = {"id": mission_id, "revision": row[0], "status_at_snapshot": mission["status"],
                                 "phase_at_snapshot": mission["phase"], "cancel_requested_at_snapshot": bool(row[1]),
                                 "proposal_status_at_snapshot": (mission.get("proposal") or {}).get("status"),
                                 "calls_at_snapshot": [{"id": call["id"], "status": call["status"]}
                                                       for call in mission["calls"]]}
        return report
