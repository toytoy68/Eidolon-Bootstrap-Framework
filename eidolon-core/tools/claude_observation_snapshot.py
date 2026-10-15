# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_observation_snapshot.py
# Description : Lecture bornée EXPÉRIMENTALE d'un instantané JSON d'observation hôte (Claude, G256-7)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""EXPERIMENTAL. Reads one JSON object the host wrote, or refuses; never guesses, never waits.

- every path component is opened without following links, from the filesystem root;
- the leaf must be a regular file, single link, not group- or world-writable, opened non-blocking
  (a FIFO cannot hang the caller);
- size is bounded before and during the read; the file must not change or be replaced while read;
- strict UTF-8 without BOM, duplicate keys and NaN/Infinity refused, bounded nesting, object at the top.
Not wired to any launcher. Proposal: docs/proposals/2026-10-15-host-policy-and-snapshot.md.
"""
import json
import os
import re
import stat

MAX_SNAPSHOT_BYTES = 1024 * 1024   # hard ceiling of this reader; the caller chooses a lower budget
_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}\.json\Z")
_after_read = None                 # test hook: runs between the read and the final identity check


class SnapshotRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _version(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _open_directory(path):
    if type(path) is not str or not os.path.isabs(path) or "\0" in path:
        raise SnapshotRefused("SNAPSHOT_PATH")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in [p for p in path.split("/") if p]:
            if part in (".", ".."):
                raise SnapshotRefused("SNAPSHOT_PATH")
            try:
                child = os.open(part, flags, dir_fd=fd)
            except OSError:
                raise SnapshotRefused("SNAPSHOT_PATH") from None   # missing, not a directory, or a link
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise SnapshotRefused("SNAPSHOT_DUPLICATE_KEY")
        value[key] = item
    return value


def _constant(name):
    raise SnapshotRefused("SNAPSHOT_INVALID_JSON")


def _depth(value, limit):
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            if depth > limit:
                raise SnapshotRefused("SNAPSHOT_TOO_DEEP")
            stack.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))


def read_json_snapshot(directory, name, *, max_bytes, max_depth=4):
    if type(name) is not str or _NAME.fullmatch(name) is None:
        raise SnapshotRefused("SNAPSHOT_PATH")
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_SNAPSHOT_BYTES:
        raise SnapshotRefused("SNAPSHOT_BUDGET")
    if type(max_depth) is not int or not 1 <= max_depth <= 16:
        raise SnapshotRefused("SNAPSHOT_BUDGET")
    dir_fd = _open_directory(directory)
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dir_fd)
        except OSError:
            raise SnapshotRefused("SNAPSHOT_UNAVAILABLE") from None    # absent, link, or unreadable
        try:
            before = os.fstat(fd)
            if stat.S_ISREG(before.st_mode) and before.st_nlink == 0:
                raise SnapshotRefused("SNAPSHOT_CHANGED")                  # replaced since our open
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise SnapshotRefused("SNAPSHOT_NOT_REGULAR")
            if before.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise SnapshotRefused("SNAPSHOT_WRITABLE_BY_OTHERS")
            if before.st_size > max_bytes:
                raise SnapshotRefused("SNAPSHOT_TOO_LARGE")
            chunks, total = [], 0
            while total <= max_bytes:
                part = os.read(fd, max_bytes + 1 - total)
                if not part:
                    break
                chunks.append(part)
                total += len(part)
            data = b"".join(chunks)
            if len(data) > max_bytes:
                raise SnapshotRefused("SNAPSHOT_TOO_LARGE")
            if _after_read is not None:
                _after_read()
            after = os.fstat(fd)
            try:
                current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            except OSError:
                raise SnapshotRefused("SNAPSHOT_CHANGED") from None
            if not (_version(before) == _version(after) == _version(current)) or len(data) != before.st_size:
                raise SnapshotRefused("SNAPSHOT_CHANGED")
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)
    if data.startswith(b"\xef\xbb\xbf"):
        raise SnapshotRefused("SNAPSHOT_ENCODING")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SnapshotRefused("SNAPSHOT_ENCODING") from None
    try:
        value = json.loads(text, object_pairs_hook=_unique, parse_constant=_constant)
    except RecursionError:
        raise SnapshotRefused("SNAPSHOT_TOO_DEEP") from None
    except json.JSONDecodeError:
        raise SnapshotRefused("SNAPSHOT_INVALID_JSON") from None
    if not isinstance(value, dict):
        raise SnapshotRefused("SNAPSHOT_INVALID_JSON")
    _depth(value, max_depth)
    return value
