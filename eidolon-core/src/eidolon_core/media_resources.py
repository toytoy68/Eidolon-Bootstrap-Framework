# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_resources.py
# Description : Réservation média coopérative durable, libération opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""One durable slot per explicitly configured pool, shared by cooperative callers.

This is admission control, not GPU measurement, engine cancellation or a lock on
external clients. No expiry, PID-based recovery or automatic release: queued work
and work with a lost response may outlive their caller. The operator reviews the
engine before releasing the exact current reservation. Own the parent directory;
hostile processes running as the same user are outside this contract.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import uuid

from .media_agents import MediaError, parse_json
from .media_workflows import OPERATIONS
from .presentation import header, message, section

POOL = r"mrp-[0-9a-f]{32}"
LEASE = r"mrl-[0-9a-f]{32}"
JOB = r"media-[0-9a-f]{32}"
LIMIT = 8192


def _id(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _private(info, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (not kind(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
            or not directory and info.st_nlink != 1):
        raise MediaError("RESOURCE_PERMISSIONS")


def _directory(path, parent=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        _private(os.fstat(fd), True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file(fd, name, flags):
    child = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        _private(os.fstat(child))
        return child
    except BaseException:
        os.close(child)
        raise


def _read(fd):
    with os.fdopen(_file(fd, "pool.json", os.O_RDONLY), "rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > LIMIT:
            raise MediaError("INVALID_RESOURCE_POOL")
        raw = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > LIMIT or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise MediaError("RESOURCE_POOL_CHANGED")
        value = parse_json(raw)
    if (type(value) is not dict or set(value) != {"schema", "pool_id", "current", "last_release"}
            or value["schema"] != "media-resource-pool/1" or not _id(value["pool_id"], POOL)):
        raise MediaError("INVALID_RESOURCE_POOL")
    for key in ("current", "last_release"):
        row = value[key]
        if row is None:
            continue
        fields = {"lease_id", "job_id", "operation", "reserved_at"}
        if key == "last_release":
            fields |= {"released_at", "reason", "engine_idle_operator_asserted"}
        if (type(row) is not dict or set(row) != fields
                or not _id(row["lease_id"], LEASE) or not _id(row["job_id"], JOB)
                or type(row["operation"]) is not str or row["operation"] not in OPERATIONS
                or type(row["reserved_at"]) is not str or len(row["reserved_at"]) > 40):
            raise MediaError("INVALID_RESOURCE_POOL")
        if key == "last_release" and (type(row["released_at"]) is not str or len(row["released_at"]) > 40
                or row["engine_idle_operator_asserted"] is not True or not _reason(row["reason"])):
            raise MediaError("INVALID_RESOURCE_POOL")
    return value


def _write(fd, value, *, initial=False):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    if len(data) > LIMIT:
        raise MediaError("INVALID_RESOURCE_POOL")
    name = "pool.json" if initial else ".pool-" + uuid.uuid4().hex
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(child, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if not initial:
            os.replace(name, "pool.json", src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        if not initial:
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass


def _reason(value):
    return (type(value) is str and bool(value.strip()) and len(value) <= 500
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and not any(0xD800 <= ord(c) <= 0xDFFF for c in value))


def initialize(path):
    """Create a NEW private pool. Existing directories are never initialized/repaired."""
    target = Path(path)
    parent = _directory(target.parent)
    fd = None
    try:
        os.mkdir(target.name, mode=0o700, dir_fd=parent)
        fd = _directory(target.name, parent)
        lock = os.open("writer.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            os.fsync(lock)
        finally:
            os.close(lock)
        value = {"schema": "media-resource-pool/1", "pool_id": "mrp-" + uuid.uuid4().hex,
                 "current": None, "last_release": None}
        _write(fd, value, initial=True)
        os.fsync(parent)  # persist the new pool directory's entry as well as its files
        return value
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def configured(config):
    if type(config) is not dict:
        raise MediaError("INVALID_MEDIA_CONFIG")
    if "resource_pool" not in config:
        return None
    item = config["resource_pool"]
    if (type(item) is not dict or set(item) != {"root", "pool_id"}
            or type(item["root"]) is not str or not item["root"] or not _id(item["pool_id"], POOL)):
        raise MediaError("INVALID_RESOURCE_CONFIG")
    return ResourcePool(item["root"], item["pool_id"])


class ResourcePool:
    def __init__(self, path, pool_id):
        if not _id(pool_id, POOL):
            raise MediaError("INVALID_RESOURCE_CONFIG")
        self.path, self.pool_id = Path(path), pool_id
        fd = _directory(self.path)
        try:
            info = os.fstat(fd)
            self.identity = (info.st_dev, info.st_ino)
            lock = _file(fd, "writer.lock", os.O_RDONLY)
            try:
                info = os.fstat(lock)
                self.lock_identity = (info.st_dev, info.st_ino)
            finally:
                os.close(lock)
            self._check(fd)
        finally:
            os.close(fd)

    def _check(self, fd):
        info = os.stat(self.path, follow_symlinks=False)
        opened = os.fstat(fd)
        if (info.st_dev, info.st_ino) != self.identity or (opened.st_dev, opened.st_ino) != self.identity:
            raise MediaError("RESOURCE_POOL_CHANGED")
        value = _read(fd)
        if value["pool_id"] != self.pool_id:
            raise MediaError("RESOURCE_POOL_MISMATCH")
        return value

    @contextmanager
    def _open(self, *, write=False):
        fd = _directory(self.path)
        lock = None
        try:
            lock = _file(fd, "writer.lock", os.O_RDWR if write else os.O_RDONLY)
            info = os.fstat(lock)
            if (info.st_dev, info.st_ino) != self.lock_identity:
                raise MediaError("RESOURCE_POOL_CHANGED")
            try:
                fcntl.flock(lock, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MediaError("RESOURCE_POOL_BUSY") from None
            yield fd, self._check(fd)
        finally:
            if lock is not None:
                os.close(lock)
            os.close(fd)

    def inspect(self):
        with self._open() as (_, value):
            return {**value, "state": "RESERVED" if value["current"] else "AVAILABLE",
                    "capacity": 1, "automatic_release": False, "engine_contacted": False,
                    "engine_idle_verified": False, "hardware_qualified": False,
                    "execution_authorized": False}

    def reserve(self, job_id, operation):
        if not _id(job_id, JOB) or type(operation) is not str or operation not in OPERATIONS:
            raise MediaError("INVALID_RESOURCE_RESERVATION")
        with self._open(write=True) as (fd, value):
            if value["current"] is not None:
                raise MediaError("RESOURCE_RESERVED")
            row = {"lease_id": "mrl-" + uuid.uuid4().hex, "job_id": job_id,
                   "operation": operation, "reserved_at": datetime.now(timezone.utc).isoformat()}
            value["current"] = row
            _write(fd, value)
            return {"pool_id": self.pool_id, **row, "automatic_release": False}

    def release(self, lease_id, *, reviewed_idle=False, reason):
        """Explicit operator assertion, never a measured engine-idle or success claim."""
        if not _id(lease_id, LEASE) or reviewed_idle is not True or not _reason(reason):
            raise MediaError("RESOURCE_RELEASE_REVIEW_REQUIRED")
        with self._open(write=True) as (fd, value):
            current = value["current"]
            if current is None or current["lease_id"] != lease_id:
                raise MediaError("RESOURCE_RESERVATION_MISMATCH")
            value["last_release"] = {**current, "released_at": datetime.now(timezone.utc).isoformat(),
                                     "reason": reason, "engine_idle_operator_asserted": True}
            value["current"] = None
            _write(fd, value)
            return {"state": "RELEASED_BY_OPERATOR", "pool_id": self.pool_id,
                    **value["last_release"], "engine_idle_verified": False, "automatic_retry": False}


def render_pool(value):
    lines = [header(title="Réservation des agents média"),
             message("INFO", "Lecture locale ; aucun moteur contacté et aucune mesure GPU."),
             section("Groupe de réservation"), message("INFO", value["pool_id"])]
    current = value["current"]
    if current:
        lines.extend([message("ATTENTION", "Réservation présente ; nouveau travail bloqué dans ce groupe."),
                      message("INFO", "Réservation : " + current["lease_id"]),
                      message("INFO", "Travail : " + current["job_id"] + " ; " + current["operation"]),
                      message("INFO", "Vérifier le moteur puis libérer explicitement cette réservation avec resource-release.")])
    else:
        lines.append(message("INFO", "Aucune réservation locale présente ; l'état réel du moteur reste inconnu."))
    lines.extend([message("ATTENTION", "Aucune expiration ni libération au décès du processus. Le dialogue et les clients externes ne sont pas couverts."),
                  message("INFO", "Une place est un contrôle de concurrence coopératif ; elle ne mesure pas la VRAM et n'autorise aucune exécution.")])
    return "\n".join(lines)
