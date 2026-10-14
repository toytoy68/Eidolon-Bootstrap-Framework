# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bridge_credentials.py
# Description : Lecture privée et bornée du jeton du pont mémoire.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Linux bridge credential reader; owner/root remain trusted, no credential cache."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat

MAX_TOKEN_BYTES = 4096


def _require(value):
    if not value:
        raise ValueError("invalid or changed memory bridge credential")


def _version(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _parent(path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        info = os.fstat(fd)
        _require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700)
        yield fd
    finally:
        os.close(fd)


def read_bridge_token(filename):
    """Read at most 4097 bytes from an anchored regular 0600 file in a 0700 parent.

    Reject links, hardlinks and changes during the read. Messages contain neither
    the private path nor the credential. The transport still validates its token.
    """
    path = Path(filename).expanduser()
    _require(".." not in path.parts)
    path = path.absolute()
    try:
        with _parent(path.parent) as parent_fd:
            parent = os.fstat(parent_fd)
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=parent_fd)
            try:
                before = os.fstat(fd)
                _require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
                         and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1
                         and 0 < before.st_size <= MAX_TOKEN_BYTES)
                raw = bytearray()
                while len(raw) <= MAX_TOKEN_BYTES:
                    block = os.read(fd, MAX_TOKEN_BYTES + 1 - len(raw))
                    if not block:
                        break
                    raw.extend(block)
                _require(len(raw) <= MAX_TOKEN_BYTES)
                after = os.fstat(fd)
                current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                _require(_version(before) == _version(after) == _version(current))
                with _parent(path.parent) as checked_fd:
                    checked = os.fstat(checked_fd)
                    _require((parent.st_dev, parent.st_ino) == (checked.st_dev, checked.st_ino))
            finally:
                os.close(fd)
        token = raw.decode("ascii").strip()
        _require(32 <= len(token) <= MAX_TOKEN_BYTES
                 and all(33 <= ord(c) <= 126 for c in token))
        return token
    except (OSError, UnicodeError):
        raise ValueError("unavailable or unsafe memory bridge credential") from None
