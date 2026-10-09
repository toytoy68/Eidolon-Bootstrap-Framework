# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_artifacts.py
# Description : Artefacts média privés, références opaques et publication atomique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Local immutable media inputs. A reference is NOT an access grant.

The operator owns the parent directory. Cooperative writers serialize on flock.
Readers verify content hashes before returning bytes; no caller-supplied path
inside the store. Pending bundles after a crash block further imports for review.
No deletion, automatic recovery, HTTP upload or semantic media validation here.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from .media_agents import MediaError, identify, parse_json, read_regular

MAX_FILE = 200 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MAX_COUNT = 1024
MAX_TOTAL = 4 * 1024 * 1024 * 1024
TYPES = {"image/png", "image/jpeg", "image/webp", "video/mp4", "video/webm"}


def validate_reference(value):
    if type(value) is not dict or set(value) != {"schema", "store_id", "artifact_id", "sha256"}:
        raise MediaError("INVALID_ARTIFACT_REFERENCE")
    for key, pattern in (("store_id", r"mas-[0-9a-f]{32}"), ("artifact_id", r"ma-[0-9a-f]{32}"),
                         ("sha256", r"[0-9a-f]{64}")):
        if not isinstance(value[key], str) or not re.fullmatch(pattern, value[key]):
            raise MediaError("INVALID_ARTIFACT_REFERENCE")
    if value["schema"] != "media-artifact-ref/1":
        raise MediaError("INVALID_ARTIFACT_REFERENCE")
    return dict(value)


def _private(info, *, directory=False):
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or info.st_uid != os.getuid() or info.st_mode & 0o077 or (not directory and info.st_nlink != 1):
        raise MediaError("ARTIFACT_PERMISSIONS")


def _directory(path, parent=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        _private(os.fstat(fd), directory=True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(name, parent, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno()); _private(before)
        if before.st_size > limit:
            raise MediaError("ARTIFACT_TOO_LARGE")
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(body) != before.st_size or len(body) > limit or (
                before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise MediaError("ARTIFACT_CHANGED")
        return body


def _write(name, body, parent):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def _marker(root):
    value = parse_json(_read("store.json", root, 4096))
    if type(value) is not dict or set(value) != {"schema", "store_id", "max_artifacts", "max_bytes"}:
        raise MediaError("INVALID_ARTIFACT_STORE")
    if value["schema"] != "media-artifact-store/1" or not isinstance(value["store_id"], str) or not re.fullmatch(r"mas-[0-9a-f]{32}", value["store_id"]):
        raise MediaError("INVALID_ARTIFACT_STORE")
    if type(value["max_artifacts"]) is not int or not 1 <= value["max_artifacts"] <= MAX_COUNT:
        raise MediaError("INVALID_ARTIFACT_STORE")
    if type(value["max_bytes"]) is not int or not 1 <= value["max_bytes"] <= MAX_TOTAL:
        raise MediaError("INVALID_ARTIFACT_STORE")
    return value


def initialize(path, *, max_artifacts=128, max_bytes=1024 * 1024 * 1024):
    if type(max_artifacts) is not int or not 1 <= max_artifacts <= MAX_COUNT or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_TOTAL:
        raise MediaError("INVALID_ARTIFACT_BUDGET")
    target = Path(path)
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    fd = _directory(target)
    try:
        marker = {"schema": "media-artifact-store/1", "store_id": "mas-" + uuid.uuid4().hex,
                  "max_artifacts": max_artifacts, "max_bytes": max_bytes}
        _write("store.json", _encoded(marker), fd)
        _write("writer.lock", b"", fd)
        os.fsync(fd)
        return marker
    finally:
        os.close(fd)


class ArtifactStore:
    def __init__(self, path, *, expected_store_id=None):
        self.path = Path(path)
        fd = _directory(self.path)
        try:
            self.marker = _marker(fd)
        finally:
            os.close(fd)
        self.store_id = self.marker["store_id"]
        if expected_store_id is not None and expected_store_id != self.store_id:
            raise MediaError("ARTIFACT_STORE_MISMATCH")

    def _check(self, fd):
        current = os.stat(self.path, follow_symlinks=False)
        pinned = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino) or _marker(fd) != self.marker:
            raise MediaError("ARTIFACT_STORE_CHANGED")

    @contextmanager
    def _open(self, write=False):
        fd = _directory(self.path)
        lock = None
        try:
            self._check(fd)
            if write:
                lock = os.open("writer.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                _private(os.fstat(lock))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise MediaError("ARTIFACT_STORE_BUSY") from None
                self._check(fd)
            yield fd
            self._check(fd)
        finally:
            if lock is not None:
                os.close(lock)
            os.close(fd)

    def _manifest(self, fd, artifact_id, *, directory_name=None):
        sub = _directory(directory_name or artifact_id, fd)
        try:
            _bundle_names(sub, complete=True)
            value = parse_json(_read("manifest.json", sub, 4096))
            required = {"schema", "reference", "display_name", "size", "media_type", "created_at"}
            if type(value) is not dict or set(value) - {"provenance"} != required:
                raise MediaError("INVALID_ARTIFACT_MANIFEST")
            if "provenance" in value:
                _provenance(value["provenance"])
            ref = validate_reference(value["reference"])
            if value["schema"] != "media-artifact/1" or ref["store_id"] != self.store_id or ref["artifact_id"] != artifact_id:
                raise MediaError("INVALID_ARTIFACT_MANIFEST")
            if (type(value["size"]) is not int or not 1 <= value["size"] <= MAX_FILE
                    or not isinstance(value["media_type"], str) or value["media_type"] not in TYPES):
                raise MediaError("INVALID_ARTIFACT_MANIFEST")
            if value["media_type"].startswith("image/") and value["size"] > MAX_IMAGE:
                raise MediaError("INVALID_ARTIFACT_MANIFEST")
            _display_name(value["display_name"])
            if not isinstance(value["created_at"], str) or len(value["created_at"]) > 40:
                raise MediaError("INVALID_ARTIFACT_MANIFEST")
            info = os.stat("payload", dir_fd=sub, follow_symlinks=False); _private(info)
            if info.st_size != value["size"]:
                raise MediaError("ARTIFACT_CHANGED")
            return value
        finally:
            os.close(sub)

    def _inventory(self, fd):
        items, pending = [], []
        with os.scandir(fd) as entries:
            count = 0
            for entry in entries:
                count += 1
                if count > MAX_COUNT + 3:
                    raise MediaError("ARTIFACT_DIRECTORY_LIMIT")
                if entry.name in {"store.json", "writer.lock"}:
                    continue
                if re.fullmatch(r"pending-[0-9a-f]{32}", entry.name):
                    pending.append(entry.name)
                elif re.fullmatch(r"ma-[0-9a-f]{32}", entry.name):
                    items.append(self._manifest(fd, entry.name))
                else:
                    raise MediaError("ARTIFACT_UNEXPECTED_ENTRY")
        return sorted(items, key=lambda m: m["reference"]["artifact_id"]), sorted(pending)

    def inventory(self):
        with self._open() as fd:
            items, pending = self._inventory(fd)
            return {"store_id": self.store_id, "artifacts": items, "pending_review": pending,
                    "bytes": sum(i["size"] for i in items), "content_hashes_checked": False}

    def import_file(self, source, *, display_name=None):
        body = read_regular(source, MAX_FILE)
        return self.import_bytes(body, display_name=display_name or Path(source).name)

    def _checkpoint(self, stage):
        """Failure-injection seam; normal production behavior has no callback."""

    def import_bytes(self, body, *, display_name, provenance=None):
        if type(body) is not bytes or not 1 <= len(body) <= MAX_FILE:
            raise MediaError("ARTIFACT_TOO_LARGE")
        name = _display_name(display_name)
        media_type = identify(body)
        if media_type.startswith("image/") and len(body) > MAX_IMAGE:
            raise MediaError("IMAGE_TOO_LARGE")
        artifact_id = "ma-" + uuid.uuid4().hex
        ref = {"schema": "media-artifact-ref/1", "store_id": self.store_id,
               "artifact_id": artifact_id, "sha256": hashlib.sha256(body).hexdigest()}
        manifest = {"schema": "media-artifact/1", "reference": ref, "display_name": name,
                    "size": len(body), "media_type": media_type,
                    "created_at": datetime.now(timezone.utc).isoformat()}
        if provenance is not None:
            manifest["provenance"] = _provenance(provenance)
        with self._open(write=True) as fd:
            items, pending = self._inventory(fd)
            if pending:
                raise MediaError("ARTIFACT_RECOVERY_REQUIRED")
            if len(items) >= self.marker["max_artifacts"] or sum(m["size"] for m in items) + len(body) > self.marker["max_bytes"]:
                raise MediaError("ARTIFACT_QUOTA_EXCEEDED")
            staging = "pending-" + uuid.uuid4().hex
            os.mkdir(staging, 0o700, dir_fd=fd)
            sub = _directory(staging, fd)
            try:
                self._checkpoint("staging-created")
                _write("payload", body, sub)
                self._checkpoint("payload-durable")
                _write("manifest.json", _encoded(manifest), sub)
                os.fsync(sub)
                self._checkpoint("manifest-durable")
                self._check(fd)
                # Unique random name; never replace an existing artifact directory.
                if os.path.lexists(self.path / artifact_id):
                    raise MediaError("ARTIFACT_ID_COLLISION")
                os.rename(staging, artifact_id, src_dir_fd=fd, dst_dir_fd=fd)
                self._checkpoint("renamed")
                os.fsync(fd)
            finally:
                os.close(sub)
        return manifest

    def read(self, reference):
        ref = validate_reference(reference)
        if ref["store_id"] != self.store_id:
            raise MediaError("ARTIFACT_STORE_MISMATCH")
        with self._open() as fd:
            manifest = self._manifest(fd, ref["artifact_id"])
            if manifest["reference"] != ref:
                raise MediaError("ARTIFACT_REFERENCE_MISMATCH")
            sub = _directory(ref["artifact_id"], fd)
            try:
                body = _read("payload", sub, manifest["size"])
            finally:
                os.close(sub)
            if hashlib.sha256(body).hexdigest() != ref["sha256"] or identify(body) != manifest["media_type"]:
                raise MediaError("ARTIFACT_CONTENT_MISMATCH")
        return body, manifest

    def _pending(self, fd, name):
        if not isinstance(name, str) or not re.fullmatch(r"pending-[0-9a-f]{32}", name):
            raise MediaError("INVALID_PENDING_ARTIFACT")
        sub = _directory(name, fd)
        try:
            names = _bundle_names(sub, complete=False)
            if names != {"manifest.json", "payload"}:
                return {"pending": name, "state": "INCOMPLETE", "publishable": False,
                        "present_files": sorted(names)}
            raw = parse_json(_read("manifest.json", sub, 4096))
            ref = validate_reference(raw.get("reference") if type(raw) is dict else None)
            manifest = self._manifest(fd, ref["artifact_id"], directory_name=name)
            body = _read("payload", sub, manifest["size"])
            if hashlib.sha256(body).hexdigest() != ref["sha256"] or identify(body) != manifest["media_type"]:
                raise MediaError("ARTIFACT_CONTENT_MISMATCH")
            return {"pending": name, "state": "COMPLETE_UNPUBLISHED", "publishable": True,
                    "artifact": manifest, "content_hash_checked": True}
        finally:
            os.close(sub)

    def inspect_pending(self, name):
        with self._open() as fd:
            return self._pending(fd, name)

    def export_file(self, reference, destination):
        """Explicit immutable read -> NEW complete file in an owned private directory.

        A hard link publishes the separately written temporary file atomically,
        without replacing an existing destination. The store payload is not linked.
        A process death may leave an export temporary; no automatic replay/deletion.
        """
        body, manifest = self.read(reference)
        target = Path(destination)
        _display_name(target.name)
        if target.parent.resolve().is_relative_to(self.path.resolve()):
            raise MediaError("EXPORT_INSIDE_STORE")
        fd = _directory(target.parent)
        temporary = ".media-export-" + uuid.uuid4().hex
        created = False
        try:
            try:
                os.stat(target.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("export destination exists")
            _write(temporary, body, fd)
            created = True
            self._checkpoint("export-durable")
            current, pinned = os.stat(target.parent, follow_symlinks=False), os.fstat(fd)
            if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
                raise MediaError("EXPORT_PARENT_CHANGED")
            os.link(temporary, target.name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            self._checkpoint("export-published")
            os.fsync(fd)
            return {"exported": True, "reference": manifest["reference"], "size": len(body),
                    "content_hash_checked": True, "semantic_content_verified": False}
        finally:
            try:
                if created:
                    os.unlink(temporary, dir_fd=fd)
                    os.fsync(fd)
            finally:
                os.close(fd)

    def publish_pending(self, name, expected_reference):
        """Explicit recovery of complete bytes only. Never adopts or deletes partial data."""
        expected = validate_reference(expected_reference)
        with self._open(write=True) as fd:
            items, pending = self._inventory(fd)
            if pending != [name]:
                raise MediaError("ARTIFACT_RECOVERY_SCOPE")
            inspected = self._pending(fd, name)
            if not inspected["publishable"]:
                raise MediaError("ARTIFACT_INCOMPLETE")
            manifest = inspected["artifact"]
            if manifest["reference"] != expected:
                raise MediaError("ARTIFACT_REFERENCE_MISMATCH")
            if len(items) >= self.marker["max_artifacts"] or sum(m["size"] for m in items) + manifest["size"] > self.marker["max_bytes"]:
                raise MediaError("ARTIFACT_QUOTA_EXCEEDED")
            artifact_id = expected["artifact_id"]
            try:
                os.stat(artifact_id, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise MediaError("ARTIFACT_ID_COLLISION")
            self._check(fd)
            os.rename(name, artifact_id, src_dir_fd=fd, dst_dir_fd=fd)
            self._checkpoint("recovery-renamed")
            os.fsync(fd)
            return {"recovered": True, "published_from": name, "artifact": manifest,
                    "content_hash_checked": True, "semantic_content_verified": False}


def _display_name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 255 or value in {".", ".."} or any(
            ord(c) < 32 or ord(c) == 127 or c in "/\\" for c in value):
        raise MediaError("INVALID_ARTIFACT_NAME")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise MediaError("INVALID_ARTIFACT_NAME") from None
    return value


def _provenance(value):
    keys = {"kind", "job_id", "prompt_id", "node_id", "output_index", "collection_id"}
    if type(value) is not dict or set(value) != keys or value["kind"] != "comfy-output":
        raise MediaError("INVALID_ARTIFACT_PROVENANCE")
    for key in keys - {"kind", "output_index"}:
        if not isinstance(value[key], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value[key]):
            raise MediaError("INVALID_ARTIFACT_PROVENANCE")
    if type(value["output_index"]) is not int or not 0 <= value["output_index"] < 16:
        raise MediaError("INVALID_ARTIFACT_PROVENANCE")
    return dict(value)


def _bundle_names(fd, *, complete):
    names = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            if entry.name not in {"payload", "manifest.json"}:
                raise MediaError("ARTIFACT_UNEXPECTED_ENTRY")
            names.add(entry.name)
    if complete and names != {"payload", "manifest.json"}:
        raise MediaError("ARTIFACT_INCOMPLETE")
    return names
