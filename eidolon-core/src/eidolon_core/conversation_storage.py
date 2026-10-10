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
Rollback: stop the server, then restore_backup() (restore-backup): a SIGNED backup only, signature checked first.
"""
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat

from . import conversation_store as cs
from .contracts import ContractError, digest, encode
from .sqlite_errors import is_busy

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
    counts = {table: len(rows) for table, rows in content.items()}
    # C-070: the kept personality copy is part of what a backup must carry (absent: digest unchanged).
    row = db.execute("SELECT value FROM meta WHERE key=?", (cs.PERSONALITY_KEY,)).fetchone() \
        if "meta" in names else None
    if row is not None:
        content["personality_copy"] = row[0]
        counts["personality_copy"] = 1
    return digest(content), counts


def _personality(db):
    """What the kept personality copy is, for the operator: version and sha256, never its text."""
    from .personality import parse_copy
    row = db.execute("SELECT value FROM meta WHERE key=?", (cs.PERSONALITY_KEY,)).fetchone()
    if row is None:
        return None
    try:
        value = parse_copy(row[0])
    except ContractError:
        return "INVALID"
    return {"version": value["version"], "sha256": digest(value)}


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
                sha, counts, personality = None, None, None
            else:
                sha, counts = logical_digest(db)
                personality = _personality(db)
            db.execute("COMMIT")
        finally:
            db.close()
    except sqlite3.DatabaseError as exc:
        code = "CONVERSATION_STORE_BUSY" if is_busy(exc) else "CONVERSATION_STORE_UNAVAILABLE"
        raise StorageError(code + ": database unreadable") from None
    return {"protocol": INSPECTION, **report, "integrity": "ok" if integrity == "ok" else "FAILED",
            "logical_sha256": sha, "rows": counts, "personality": personality, "supported_versions": sorted(cs.SCHEMAS),
            "migrated": False, "authorizes_execution": False}


def _new_private_file(output):
    """A NEW 0600 file in a real directory, never an existing one; returns (path, open write fd)."""
    out = Path(output)
    parent = os.lstat(out.parent) if out.parent.exists() else None
    if parent is None or stat.S_ISLNK(parent.st_mode) or not stat.S_ISDIR(parent.st_mode):
        raise StorageError("BACKUP_PATH_REFUSED: the output folder must be a real directory")
    try:
        return out, os.open(out, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise StorageError("BACKUP_PATH_REFUSED: the output file already exists") from None
    except OSError:
        raise StorageError("BACKUP_FAILED: cannot create the backup file") from None


def backup(source, output, *, encrypt_to=None, sign_with=None):
    """Consistent copy to a new private file, then verified against the source snapshot.

    encrypt_to: an operator file of public age recipients. The copy is then made and verified IN
    MEMORY, and only its encrypted form is written: no plaintext backup ever touches the disk.
    Every backup is SIGNED (toytoy, 10/10/2026): <output>.sig signs the file actually written, with
    sign_with (an Ed25519 private key, PEM, 0600) or else the server's own key, created once at the
    first backup next to the database (backup_signature.server_key). Any failure leaves neither the
    backup nor its signature.
    """
    from . import backup_signature as bs
    from .backup_encryption import _open_owned
    _regular(source)
    signature_path = Path(str(output) + ".sig")
    if os.path.lexists(signature_path):
        raise StorageError("BACKUP_PATH_REFUSED: the signature file already exists")
    if sign_with is None:
        key, key_state = bs.server_key(Path(source).parent, create=False)    # SIGNING_KEY_LOST before writing
    else:
        key, key_state = sign_with, "OPERATOR"
    if key is not None:
        os.close(_open_owned(key, "SIGNING_KEY_REFUSED", private=True))     # refused before writing
    report = (_encrypted_backup(source, output, encrypt_to) if encrypt_to is not None
              else _plain_backup(source, output))
    try:
        if key is None:
            key, key_state = bs.server_key(Path(source).parent)
        return {**_sign(report, Path(output), signature_path, key), "signing_key": key_state}
    except BaseException:
        _discard(output)
        raise


def _sign(report, output, signature_path, key):
    from . import backup_signature as bs
    from .store import now
    manifest = {"purpose": bs.PURPOSE, "file_sha256": report["file_sha256"], "bytes": report["bytes"],
                "encrypted": bool(report.get("encrypted")), "store_id": report["store_id"],
                "version": report["version"], "logical_sha256": report["logical_sha256"],
                "plaintext_sha256": report.get("plaintext_sha256", report["file_sha256"]), "signed_at": now()}
    document = bs.sign(manifest, key)
    if _file_sha(output) != manifest["file_sha256"]:
        raise StorageError("BACKUP_FAILED: the backup changed while it was being signed")
    written, fd = _new_private_file(signature_path)
    try:
        os.write(fd, encode(document).encode("utf-8"))
        os.fsync(fd)
    except OSError:
        os.close(fd)
        _discard(written)
        raise StorageError("BACKUP_SIGNING_FAILED: the signature could not be written") from None
    os.close(fd)
    return {**report, "signed": True, "signer": document["signer"], "signed_at": manifest["signed_at"]}


def verify_signature(path, signer):
    """The signed manifest of this backup, if the EXPECTED key signed exactly this file.

    signer: the expected Ed25519 public key (PEM). Checked: signer, signature, then file sha256 and size.
    """
    from . import backup_signature as bs
    _regular(path)
    public = bs.read_public_key(signer)
    manifest = bs.verify(bs.read_document(str(path) + ".sig"), public)
    if (_file_sha(path), os.path.getsize(path)) != (manifest["file_sha256"], manifest["bytes"]):
        raise StorageError("BACKUP_SIGNATURE_INVALID: the file is not the one that was signed")
    from .backup_encryption import is_encrypted
    if is_encrypted(path) != manifest["encrypted"]:
        raise StorageError("BACKUP_SIGNATURE_INVALID: the file is not the one that was signed")
    return {**manifest, "signer": bs.fingerprint(public), "signature": "VERIFIED"}


def verify_signed_backup(path, signer):
    """Signature first; then, for a plain backup, the usual checks against the signed manifest."""
    manifest = verify_signature(path, signer)
    if manifest["encrypted"]:
        return {"signature": manifest, "backup": None}
    report = verify_backup(path)
    if (report["logical_sha256"], report["store_id"], report["version"]) != (
            manifest["logical_sha256"], manifest["store_id"], manifest["version"]):
        raise StorageError("BACKUP_SIGNATURE_INVALID: the content differs from the signed manifest")
    return {"signature": manifest, "backup": report}


def _plain_backup(source, output):
    out, fd = _new_private_file(output)
    os.close(fd)
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


# An encrypted backup is made in memory (no plaintext file). Measured peak (G140 review, 50 and 200 MB
# databases): about 3.1 times the database size in the Python process, because serialize() copies the
# in-memory database once more. Above 512 MiB (about 1.6 GiB of RAM) it is refused.
# Not used on purpose: a memfd opened by SQLite through /proc/self/fd/N, since SQLite resolves that
# link and wrote a plaintext file under "/memfd:… (deleted)" on disk during the trial.
MAX_IN_MEMORY_BACKUP = 512 << 20


def _snapshot(source):
    """(report, serialized bytes) of one read snapshot, checked IN MEMORY before it is serialized.

    The checks of verify_backup (integrity, version, store, logical digest, kept personality) run on the
    in-memory copy itself, which must match the digest of the source snapshot taken in the same
    transaction; only then is it serialized. No second in-memory copy is made.
    """
    src = _read_only(source)
    try:
        src.execute("BEGIN")
        expected = _describe(src), logical_digest(src)[0]
        memory = sqlite3.connect(":memory:", isolation_level=None)
        try:
            src.backup(memory)
            src.execute("COMMIT")
            memory.execute("BEGIN")
            report = _describe(memory)
            integrity = memory.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok" or report["state"] not in ("CURRENT", "MIGRATION_REQUIRED"):
                raise StorageError("BACKUP_INVALID: integrity or version check failed")
            sha, counts = logical_digest(memory)
            personality = _personality(memory)
            memory.execute("COMMIT")
            data = memory.serialize()
        finally:
            memory.close()
    finally:
        src.close()
    if (report["version"], report["schema"], report["store_id"], sha) != (
            expected[0]["version"], expected[0]["schema"], expected[0]["store_id"], expected[1]):
        raise StorageError("BACKUP_FAILED: the copy differs from the source")
    return {"protocol": INSPECTION, **report, "integrity": "ok", "logical_sha256": sha, "rows": counts,
            "personality": personality, "supported_versions": sorted(cs.SCHEMAS), "migrated": False,
            "authorizes_execution": False}, data


def _encrypted_backup(source, output, recipients_path):
    from . import backup_encryption as be
    recipients = be.read_recipients(recipients_path)
    be.find_age()                                   # refused before any file is created
    if os.path.getsize(source) > MAX_IN_MEMORY_BACKUP:
        raise StorageError("BACKUP_TOO_LARGE_FOR_MEMORY: an encrypted backup is made in memory (about twice "
                           "the database size); above 512 MiB it is refused")
    try:
        report, data = _snapshot(source)
    except sqlite3.DatabaseError as exc:
        code = "CONVERSATION_STORE_BUSY" if is_busy(exc) else "BACKUP_FAILED"
        raise StorageError(code + ": the copy could not be made") from None
    out, fd = _new_private_file(output)
    try:
        stanzas = be.encrypt(data, recipients, fd)
    except BaseException:
        os.close(fd)
        _discard(out)
        raise
    os.close(fd)
    return {**report, "encrypted": True, "format": "age-encryption.org/v1", "recipients": stanzas,
            "plaintext_sha256": hashlib.sha256(data).hexdigest(), "file_sha256": _file_sha(out),
            "bytes": os.path.getsize(out)}


def decrypt_backup(source, identity, output, *, signer):
    """Decrypt an encrypted backup into a NEW private file, then verify it like any backup.

    signer (mandatory): the expected Ed25519 public key; the signature is checked BEFORE decrypting
    (nothing is written otherwise), and the decrypted content must match the signed manifest.
    """
    from . import backup_encryption as be
    if signer is None:
        raise StorageError("BACKUP_SIGNER_REQUIRED: a backup is only restored after its signature is verified")
    manifest = verify_signature(source, signer)
    if not manifest["encrypted"]:
        raise StorageError("BACKUP_SIGNATURE_INVALID: the signed backup is not encrypted")
    out, fd = _new_private_file(output)
    try:
        be.decrypt(source, identity, fd)
    except BaseException:
        os.close(fd)
        _discard(out)
        raise
    os.close(fd)
    try:
        report = verify_backup(out)
        if (report["file_sha256"], report["logical_sha256"], report["store_id"]) != (
                manifest["plaintext_sha256"], manifest["logical_sha256"], manifest["store_id"]):
            raise StorageError("BACKUP_SIGNATURE_INVALID: the content differs from the signed manifest")
    except ContractError:
        _discard(out)
        raise
    return {**report, "decrypted_from_sha256": _file_sha(source), "signature": "VERIFIED"}


def restore_backup(store, source, *, signer, identity=None, checkpoint=None):
    """Put a SIGNED backup back in place of the conversation store (server stopped).

    Order: signature (expected key, exact file), same Store identity, then the content is decrypted if
    needed into a private file NEXT TO the database, verified against the signed manifest, and only then
    swapped in. The replaced database is kept as conversations.sqlite3.before-restore-<time> (0600).
    Refused while another process holds the database (STORE_BUSY), if a journal is pending, or if the
    database file was replaced by a concurrent restore (checked under the lock).
    checkpoint(name), tests only: "staged", "locked", "linked" (fault injection).
    """
    from . import backup_encryption as be
    from .store import now
    if signer is None:
        raise StorageError("BACKUP_SIGNER_REQUIRED: a backup is only restored after its signature is verified")
    manifest = verify_signature(source, signer)
    with store.connection() as db:
        store_id = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()[0]
    if manifest["store_id"] != store_id:
        raise StorageError("RESTORE_REFUSED: the backup belongs to another Store")
    if manifest["encrypted"] and identity is None:
        raise StorageError("RESTORE_REFUSED: an encrypted backup needs the private age identity")
    directory = Path(store.directory) / "conversations"
    info = os.lstat(directory) if directory.exists() else None
    if info is None or stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise StorageError("RESTORE_REFUSED: the conversations folder is missing")
    target = directory / "conversations.sqlite3"
    staged, fd = _new_private_file(directory / (".restore-" + os.urandom(8).hex() + ".sqlite3"))
    try:
        try:
            if manifest["encrypted"]:
                be.decrypt(source, identity, fd)
            else:
                with open(source, "rb") as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        os.write(fd, block)
                os.fsync(fd)
        finally:
            os.close(fd)
        report = verify_backup(staged)
        if (report["file_sha256"], report["logical_sha256"], report["store_id"]) != (
                manifest["plaintext_sha256"], manifest["logical_sha256"], manifest["store_id"]):
            raise StorageError("BACKUP_SIGNATURE_INVALID: the content differs from the signed manifest")
        checkpoint = checkpoint or (lambda name: None)
        checkpoint("staged")
        kept = _swap(target, staged, now(), checkpoint)
    except BaseException:
        _discard(staged)
        raise
    return {"status": "RESTORED", "version": report["version"], "logical_sha256": report["logical_sha256"],
            "rows": report["rows"], "personality": report["personality"], "signature": "VERIFIED",
            "signer": manifest["signer"], "signed_at": manifest["signed_at"], "replaced_kept_as": kept}


def _swap(target, staged, stamp, checkpoint):
    """Swap under an EXCLUSIVE lock on the current database; keep it under a dated name.

    The lock is taken on the file found BEFORE connecting; once held, that file must still be the
    database (device, inode): otherwise a concurrent restore replaced it and this one is refused.
    """
    pending = any(os.path.lexists(str(target) + suffix) for suffix in ("-journal", "-wal"))
    if not os.path.lexists(target):
        if pending:
            raise StorageError("RESTORE_REFUSED: a journal is pending next to a missing database")
        try:
            os.link(staged, target)               # never over a database created meanwhile
        except FileExistsError:
            raise StorageError("RESTORE_REFUSED: a database appeared during the restore") from None
        os.unlink(staged)
        _sync_directory(target.parent)
        return None
    info = _regular(target)
    locked_file = (info.st_dev, info.st_ino)
    kept = target.with_name(target.name + ".before-restore-" + re.sub(r"[^0-9]", "", stamp)[:20])
    if os.path.lexists(kept):
        raise StorageError("RESTORE_REFUSED: a kept copy with this name already exists")
    db = sqlite3.connect(target.resolve().as_uri() + "?mode=rw", uri=True, timeout=2, isolation_level=None)
    try:
        try:
            db.execute("BEGIN EXCLUSIVE")         # also rolls back a hot journal of the current database
        except sqlite3.DatabaseError as exc:
            if is_busy(exc):
                raise StorageError("CONVERSATION_STORE_BUSY: stop the server before restoring") from None
            if pending:
                raise StorageError("RESTORE_REFUSED: a journal is pending on an unreadable database") from None
        checkpoint("locked")
        now_info = os.lstat(target)
        if (now_info.st_dev, now_info.st_ino) != locked_file:
            raise StorageError("RESTORE_REFUSED: the database was replaced by a concurrent restore")
        os.link(target, kept)
        checkpoint("linked")
        os.replace(staged, target)
        _sync_directory(target.parent)
    finally:
        db.close()
    return kept.name


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _file_sha(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def verify_backup(path):
    """A backup is usable when it is intact and of a supported version; its file digest is reported."""
    from .backup_encryption import is_encrypted
    _regular(path)
    if is_encrypted(path):
        raise StorageError("BACKUP_ENCRYPTED: decrypt it first (decrypt-backup), with the private identity")
    report = inspect(path)
    if report["integrity"] != "ok" or report["state"] not in ("CURRENT", "MIGRATION_REQUIRED"):
        raise StorageError("BACKUP_INVALID: integrity or version check failed")
    return {**report, "file_sha256": _file_sha(path), "bytes": os.path.getsize(path)}


def _discard(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def migrate_with_backup(store, output, *, checkpoint=None, encrypt_to=None, sign_with=None):
    """Explicit migration, only after a verified backup of exactly the content being migrated."""
    path = Path(store.directory) / "conversations" / "conversations.sqlite3"
    before = inspect(path)
    if before["state"] == "CURRENT":
        return {"status": "ALREADY_CURRENT", "version": before["version"], "backup": None}
    if before["state"] != "MIGRATION_REQUIRED":
        raise StorageError("CONVERSATION_STORE_UNAVAILABLE: no supported migration from this database")
    options = {k: v for k, v in (("encrypt_to", encrypt_to), ("sign_with", sign_with)) if v is not None}
    saved = backup(path, output, **options)

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
