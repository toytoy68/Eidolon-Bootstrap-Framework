# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : offline_state.py
# Description : Services hors VM G273, configuration opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Private Linux SQLite state; descriptor anchored, no existing file replacement."""
from contextlib import contextmanager, closing
import os
import sqlite3
import stat
from .runtime_json import _open_directory

@contextmanager
def database(directory, name, *, write=False):
    fd = _open_directory(str(directory))
    try:
        st = os.fstat(fd)
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise ValueError("PRIVATE_DIRECTORY_REQUIRED")
        flags = os.O_RDWR | os.O_CREAT if write else os.O_RDONLY
        leaf = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
        try:
            st = os.fstat(leaf)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
                raise ValueError("PRIVATE_FILE_REQUIRED")
            uri = f"file:/proc/self/fd/{fd}/{name}?mode={'rw' if write else 'ro'}"
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA synchronous=FULL")
                if not write: db.execute("PRAGMA query_only=ON")
                with db:
                    db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                    yield db
        finally: os.close(leaf)
    finally: os.close(fd)


@contextmanager
def lease(directory,name):
    import fcntl
    fd=_open_directory(str(directory))
    child=None
    try:
        info=os.fstat(fd)
        if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700: raise ValueError('PRIVATE_DIRECTORY_REQUIRED')
        child=os.open(name,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=fd)
        info=os.fstat(child)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1: raise ValueError('PRIVATE_FILE_REQUIRED')
        try: fcntl.flock(child,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('LIBRARY_SCAN_BUSY') from None
        yield
    finally:
        if child is not None: os.close(child)
        os.close(fd)
