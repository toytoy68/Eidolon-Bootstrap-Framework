# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : profile_files.py
# Description : Bounded read-only access to operator-approved Linux/NAS roots
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Mounted NAS paths use the same descriptor traversal as local roots.

No glob, symlink traversal, write, command, or implicit model ingestion. Operator
owns roots and mount credentials. Browser-selected PC files are separate uploads.
"""
from contextlib import contextmanager
import hashlib
import os
import stat
from .runtime_json import _open_directory

MAX_BYTES = 64000


@contextmanager
def opened(root, relative, *, directory=False):
    if (type(relative) is not str or len(relative) > 1024 or "\\" in relative or "\0" in relative
            or relative.startswith("/") or any(p in (".", "..", "") for p in relative.split("/") if relative)):
        raise ValueError("invalid relative file")
    fd = _open_directory(root)
    try:
        parts = relative.split("/") if relative else []
        for i, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
            if directory or i < len(parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_bytes(root, relative, *, max_bytes=MAX_BYTES):
    with opened(root, relative) as fd:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > max_bytes:
            raise ValueError("bounded regular file required")
        data = bytearray()
        while len(data) <= max_bytes:
            part = os.read(fd, max_bytes + 1 - len(data))
            if not part:
                break
            data.extend(part)
        after = os.fstat(fd)
        version = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns)
        if len(data) > max_bytes or version(before) != version(after) or len(data) != before.st_size:
            raise ValueError("file changed or too large")
        return bytes(data)


def read(root, relative):
    data = read_bytes(root, relative)
    text = data.decode("utf-8")
    if "\0" in text:
        raise ValueError("UTF-8 text file required")
    return {"text": text, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def listing(root, relative):
    with opened(root, relative, directory=True) as fd:
        result = []
        with os.scandir(fd) as items:
            for item in items:
                if len(result) == 100:
                    return {"entries": sorted(result, key=lambda x: x["name"]), "truncated": True}
                if item.is_symlink():
                    continue
                if item.is_dir(follow_symlinks=False):
                    result.append({"name": item.name, "kind": "directory"})
                elif item.is_file(follow_symlinks=False):
                    result.append({"name": item.name, "kind": "file"})
        return {"entries": sorted(result, key=lambda x: x["name"]), "truncated": False}
