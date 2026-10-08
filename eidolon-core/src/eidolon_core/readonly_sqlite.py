# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : readonly_sqlite.py
# Description : Refus du mode WAL avant une consultation SQLite sans mutation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Core's read-only paths support rollback journals, not externally enabled WAL.

SQLite mode=ro alone can create WAL sidecars. Check before connecting, without
immutable=1 (which would ignore normal writer locks). Directory and mode changes
by arbitrary external writers remain outside this cooperative local contract.
"""
import os
import stat

from .contracts import ContractError


def require_rollback_journal(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ContractError('READ_ONLY_DATABASE_UNAVAILABLE') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ContractError('READ_ONLY_DATABASE_FILE_TYPE')
        header = os.read(fd, 100)
        if header[:16] == b'SQLite format 3\x00' and (header[18:19] == b'\x02' or header[19:20] == b'\x02'):
            raise ContractError('READ_ONLY_WAL_UNSUPPORTED')
    finally:
        os.close(fd)
