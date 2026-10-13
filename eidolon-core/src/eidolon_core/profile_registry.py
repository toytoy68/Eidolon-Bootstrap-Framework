# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : profile_registry.py
# Description : Import atomique du plan privé vers un registre préparé, sans activation G170-A
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Linux operator-only preparation; never an account or an authorization store.

An explicit import publishes ONE immutable snapshot in an existing private
directory. Retrying the same plan is idempotent; a different plan is refused.
No service, session, credential, biometric template or memory scope is created.
Paths are pinned through directory descriptors, and cooperating writers use a
nonblocking flock. The directory owner/root remain trusted (not sandboxed).
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import uuid

from .contracts import ContractError, digest, encode
from .profile_plan import validate_profile_plan

SCHEMA = "eidolon-profile-registry/1"
SNAPSHOT = "profiles.json"
LOCK = ".profiles.lock"
MAX_PLAN_BYTES = 64 * 1024
MAX_REGISTRY_BYTES = 128 * 1024


class ProfileRegistryError(ContractError):
    """Stable diagnostic code only: never private identities or filesystem paths."""


def _require(condition, code):
    if not condition:
        raise ProfileRegistryError(code)


@contextmanager
def _directory(path):
    """Pin every component without following symlinks; final directory is private."""
    path = Path(path)
    _require(".." not in path.parts, "PROFILE_DIRECTORY_INVALID")
    absolute = path.absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in absolute.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=fd)
            os.close(fd)
            fd = next_fd
        info = os.fstat(fd)
        _require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
                 "PROFILE_DIRECTORY_NOT_PRIVATE")
        yield fd
    finally:
        os.close(fd)


def _private_file(fd, *, maximum):
    info = os.fstat(fd)
    _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
             and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) in (0o400, 0o600),
             "PROFILE_FILE_NOT_PRIVATE")
    _require(0 <= info.st_size <= maximum, "PROFILE_FILE_TOO_LARGE")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _no_constant(_):
    raise ValueError("non-finite value")


def _read_json(directory_fd, name, maximum):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory_fd)
    try:
        _private_file(fd, maximum=maximum)
        raw = bytearray()
        while len(raw) <= maximum:
            part = os.read(fd, min(8192, maximum + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        _require(len(raw) <= maximum, "PROFILE_FILE_TOO_LARGE")
    finally:
        os.close(fd)
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_no_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProfileRegistryError("PROFILE_JSON_INVALID") from None


def _validate_snapshot(value):
    _require(type(value) is dict and set(value) == {
        "schema", "status", "revision", "prepared_at", "plan_sha256", "plan", "runtime_active"
    }, "PROFILE_REGISTRY_FIELDS")
    _require(value["schema"] == SCHEMA and value["status"] == "PREPARED_NOT_ACTIVE"
             and type(value["revision"]) is int and value["revision"] == 1
             and value["runtime_active"] is False, "PROFILE_REGISTRY_STATE")
    try:
        stamp = datetime.fromisoformat(value["prepared_at"])
        _require(stamp.utcoffset() == timedelta(0), "PROFILE_REGISTRY_DATE")
    except (TypeError, ValueError):
        raise ProfileRegistryError("PROFILE_REGISTRY_DATE") from None
    plan = validate_profile_plan(value["plan"])
    _require(value["plan_sha256"] == digest(value["plan"]), "PROFILE_REGISTRY_DIGEST")
    return plan


def _summary(value):
    plan = _validate_snapshot(value)
    summary = plan.summary()
    summary.update(schema=SCHEMA, status="PREPARED_NOT_ACTIVE", revision=1,
                   prepared_at=value["prepared_at"])
    # No names, aliases, profile ids, paths or plan fingerprints in diagnostics.
    return summary


def _existing(directory_fd):
    try:
        value = _read_json(directory_fd, SNAPSHOT, MAX_REGISTRY_BYTES)
    except FileNotFoundError:
        return None
    _validate_snapshot(value)
    return value


def _check_pending(directory_fd):
    _require(not any(name.startswith(".profiles-") and name.endswith(".tmp")
                     for name in os.listdir(directory_fd)), "PROFILE_REGISTRY_PENDING")


def _check_no_live_writer(directory_fd):
    """Reader-only nonblocking lock check: live writer is BUSY, not crash residue."""
    try:
        fd = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory_fd)
    except FileNotFoundError:
        return
    try:
        _private_file(fd, maximum=0)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProfileRegistryError("PROFILE_REGISTRY_BUSY") from None
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


@contextmanager
def _writer_lock(directory_fd):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    created = False
    try:
        fd = os.open(LOCK, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
    except FileExistsError:
        fd = os.open(LOCK, flags, dir_fd=directory_fd)
    else:
        created = True
    try:
        if created:
            os.fchmod(fd, 0o600)
        _private_file(fd, maximum=0)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProfileRegistryError("PROFILE_REGISTRY_BUSY") from None
        yield
    finally:
        os.close(fd)


def _publish(directory_fd, value):
    raw = (encode(value) + "\n").encode("utf-8")
    _require(len(raw) <= MAX_REGISTRY_BYTES, "PROFILE_FILE_TOO_LARGE")
    temporary = ".profiles-" + uuid.uuid4().hex + ".tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory_fd)
    published = False
    try:
        # Explicit mode on our new file; never change the process-wide umask.
        os.fchmod(fd, 0o600)
        remaining = memoryview(raw)
        while remaining:
            count = os.write(fd, remaining)
            _require(count > 0, "PROFILE_REGISTRY_WRITE_FAILED")
            remaining = remaining[count:]
        os.fsync(fd)
        # The existing snapshot was checked while holding the writer lock.
        # Private owner/root must not mutate this directory behind that lock.
        os.replace(temporary, SNAPSHOT, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        published = True
        try:
            os.fsync(directory_fd)
        except OSError:
            raise ProfileRegistryError("PROFILE_REGISTRY_COMMIT_UNCERTAIN") from None
    finally:
        os.close(fd)
        if not published:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass


def prepare_registry(plan_path, directory, *, apply=False):
    """Dry-run by default. Never replace a different or invalid existing registry.

    Both source parent and destination must already be owned by the current
    effective user and mode 0700. A successful apply fsyncs file and directory.
    COMMIT_UNCERTAIN means the snapshot may exist: inspect, never roll back blindly.
    """
    _require(type(apply) is bool, "PROFILE_APPLY_INVALID")
    source = Path(plan_path)
    try:
        with _directory(source.parent) as source_fd:
            value = _read_json(source_fd, source.name, MAX_PLAN_BYTES)
        plan = validate_profile_plan(value)
        expected = digest(value)
        with _directory(directory) as directory_fd:
            if not apply:
                _check_no_live_writer(directory_fd)
                _check_pending(directory_fd)
                current = _existing(directory_fd)
                if current is not None:
                    _require(current["plan_sha256"] == expected, "PROFILE_REGISTRY_CONFLICT")
                result = _summary(current) if current is not None else plan.summary()
                return dict(result, operation="dry_run", would_import=current is None)
            with _writer_lock(directory_fd):
                _check_pending(directory_fd)
                current = _existing(directory_fd)
                if current is not None:
                    _require(current["plan_sha256"] == expected, "PROFILE_REGISTRY_CONFLICT")
                    # Complete a durability confirmation even after a previous uncertain publication.
                    snapshot_fd = os.open(SNAPSHOT, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                          dir_fd=directory_fd)
                    try:
                        os.fsync(snapshot_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        raise ProfileRegistryError("PROFILE_REGISTRY_COMMIT_UNCERTAIN") from None
                    finally:
                        os.close(snapshot_fd)
                    return dict(_summary(current), operation="already_prepared")
                snapshot = {"schema": SCHEMA, "status": "PREPARED_NOT_ACTIVE", "revision": 1,
                            "prepared_at": datetime.now(timezone.utc).isoformat(),
                            "plan_sha256": expected, "plan": value, "runtime_active": False}
                _publish(directory_fd, snapshot)
                return dict(_summary(snapshot), operation="imported")
    except OSError:
        raise ProfileRegistryError("PROFILE_REGISTRY_IO") from None


def inspect_registry(directory):
    """Read and revalidate, without creating a directory, file or lock."""
    try:
        with _directory(directory) as directory_fd:
            _check_no_live_writer(directory_fd)
            _check_pending(directory_fd)
            value = _existing(directory_fd)
            _require(value is not None, "PROFILE_REGISTRY_MISSING")
            return _summary(value)
    except OSError:
        raise ProfileRegistryError("PROFILE_REGISTRY_IO") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Préparer les profils Eidolon Core, sans activation.")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    prepare = subparsers.add_parser("prepare", help="Vérifier le plan ; écrire seulement avec --apply.")
    prepare.add_argument("--plan", required=True)
    prepare.add_argument("--directory", required=True)
    prepare.add_argument("--apply", action="store_true")
    inspect = subparsers.add_parser("inspect", help="Vérifier le registre sans afficher les identités.")
    inspect.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    try:
        result = (prepare_registry(args.plan, args.directory, apply=args.apply)
                  if args.operation == "prepare" else inspect_registry(args.directory))
    except ContractError as exc:
        print(encode({"ok": False, "error": str(exc), "runtime_active": False}))
        return 1
    except ValueError:
        print(encode({"ok": False, "error": "PROFILE_REGISTRY_INVALID_INPUT", "runtime_active": False}))
        return 1
    print(encode({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
