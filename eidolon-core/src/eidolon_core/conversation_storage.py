# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_storage.py
# Description : Inspection hors ligne, sauvegarde vérifiable et migration explicite du dépôt des conversations (C-TASK-G099)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Storage evolution of the conversation store, operator side.

- inspect(): read-only (SQLite mode=ro), never migrates, never repairs; the file is unchanged.
- backup(): a NEW private file (O_EXCL, 0600) written with SQLite's online backup, then verified:
  integrity, same schema/version/store, and the same logical digest as the source snapshot.
- migrate_with_backup(): backup first, then the explicit stepwise migration, which starts only if the
  database still has the backed-up content (checked under the write lock). Missions are never touched:
  the mission Store is only read for its identity, and nothing is replayed.
Rollback: stop the server and put the backup file back in place (see docs/CONVERSATION-STORE.md).
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from . import conversation_store as cs
from .contracts import ContractError, digest

# Tables present in every supported version, and the order that defines their logical content.
CORE_TABLES = {"conversations": "conversation_id", "turns": "conversation_id, sequence", "replies": "turn_id",
               "proposals": "proposal_id, version", "submissions": "client_id, command_key"}
# G099-R1: every table added by a later version is part of the logical content (and of BACKUP_STALE).
OPTIONAL_TABLES = {"attempts": "turn_id", "attachments": "conversation_id, artifact_id",
                   "media_links": "conversation_id, proposal_sha256", "media_proposals": "proposal_id, version"}
INSPECTION = "eidolon-conversation-store-inspection/1"


class StorageError(ContractError):
    pass


def _regular(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise StorageError("CONVERSATION_STORE_MISSING: no such database") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise StorageError("CONVERSATION_STORE_UNAVAILABLE: a regular file is required")
    return info


def _read_only(path):
    _regular(path)
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2, isolation_level=None)


def logical_digest(db):
    """Digest of the rows that carry meaning (identifiers, order, references), version-independent."""
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    content = {}
    for table, order in {**CORE_TABLES, **OPTIONAL_TABLES}.items():
        if table in names:
            content[table] = [list(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY {order}")]
    return digest(content), {table: len(rows) for table, rows in content.items()}


def _describe(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    try:
        meta = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('schema','store_id')"))
    except sqlite3.DatabaseError:
        meta = {}
    if version == cs.VERSION and meta.get("schema") == cs.SCHEMA:
        state = "CURRENT"
    elif version in cs.MIGRATIONS and meta.get("schema") == cs.SCHEMAS.get(version):
        state = "MIGRATION_REQUIRED"
    elif isinstance(version, int) and version > cs.VERSION:
        state = "FUTURE_VERSION"
    else:
        state = "UNKNOWN"
    return {"version": version, "schema": meta.get("schema"), "store_id": meta.get("store_id"), "state": state}


def inspect(path):
    """Offline report. Opens read-only: no migration, no repair, no journal written by this process."""
    try:
        db = _read_only(path)
        try:
            db.execute("BEGIN")
            report = _describe(db)
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if report["state"] == "UNKNOWN":
                sha, counts = None, None
            else:
                sha, counts = logical_digest(db)
            db.execute("COMMIT")
        finally:
            db.close()
    except sqlite3.DatabaseError as exc:
        code = "CONVERSATION_STORE_BUSY" if "locked" in str(exc) else "CONVERSATION_STORE_UNAVAILABLE"
        raise StorageError(code + ": database unreadable") from None
    return {"protocol": INSPECTION, **report, "integrity": "ok" if integrity == "ok" else "FAILED",
            "logical_sha256": sha, "rows": counts, "supported_versions": sorted(cs.SCHEMAS),
            "migrated": False, "authorizes_execution": False}


def backup(source, output):
    """Consistent copy to a new private file, then verified against the source snapshot."""
    _regular(source)
    out = Path(output)
    parent = os.lstat(out.parent) if out.parent.exists() else None
    if parent is None or stat.S_ISLNK(parent.st_mode) or not stat.S_ISDIR(parent.st_mode):
        raise StorageError("BACKUP_PATH_REFUSED: the output folder must be a real directory")
    try:
        os.close(os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
    except FileExistsError:
        raise StorageError("BACKUP_PATH_REFUSED: the output file already exists") from None
    except OSError:
        raise StorageError("BACKUP_FAILED: cannot create the backup file") from None
    try:
        src = _read_only(source)
        try:
            src.execute("BEGIN")                      # one snapshot for the digest AND the copy
            expected = _describe(src), logical_digest(src)[0]
            dst = sqlite3.connect(out, isolation_level=None)
            try:
                src.backup(dst)
            finally:
                dst.close()
            src.execute("COMMIT")
        finally:
            src.close()
        with open(out, "rb") as handle:
            os.fsync(handle.fileno())
    except (sqlite3.DatabaseError, OSError):
        _discard(out)
        raise StorageError("BACKUP_FAILED: the copy could not be written") from None
    report = verify_backup(out)
    if (report["version"], report["schema"], report["store_id"], report["logical_sha256"]) != (
            expected[0]["version"], expected[0]["schema"], expected[0]["store_id"], expected[1]):
        _discard(out)
        raise StorageError("BACKUP_FAILED: the copy differs from the source")
    return report


def verify_backup(path):
    """A backup is usable when it is intact and of a supported version; its file digest is reported."""
    report = inspect(path)
    if report["integrity"] != "ok" or report["state"] not in ("CURRENT", "MIGRATION_REQUIRED"):
        raise StorageError("BACKUP_INVALID: integrity or version check failed")
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return {**report, "file_sha256": sha.hexdigest(), "bytes": os.path.getsize(path)}


def _discard(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def migrate_with_backup(store, output, *, checkpoint=None):
    """Explicit migration, only after a verified backup of exactly the content being migrated."""
    path = Path(store.directory) / "conversations" / "conversations.sqlite3"
    before = inspect(path)
    if before["state"] == "CURRENT":
        return {"status": "ALREADY_CURRENT", "version": before["version"], "backup": None}
    if before["state"] != "MIGRATION_REQUIRED":
        raise StorageError("CONVERSATION_STORE_UNAVAILABLE: no supported migration from this database")
    saved = backup(path, output)

    def unchanged(db):
        if logical_digest(db)[0] != saved["logical_sha256"]:
            raise StorageError("BACKUP_STALE: the database changed after the backup; nothing was migrated")
    cs.ConversationStore(store, migrate=True, checkpoint=checkpoint, before_migration=unchanged)
    after = inspect(path)
    if after["state"] != "CURRENT" or after["integrity"] != "ok":
        raise StorageError("CONVERSATION_STORE_UNAVAILABLE: migration did not complete")
    return {"status": "MIGRATED", "from_version": before["version"], "version": after["version"],
            "backup": {"file_sha256": saved["file_sha256"], "logical_sha256": saved["logical_sha256"]},
            "rows_before": before["rows"], "rows_after": after["rows"]}
