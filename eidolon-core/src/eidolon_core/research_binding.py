# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_binding.py
# Description : Accès sans création au Store pour migration des pauses
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Existing mission database access for the explicit local binding operation.

Does not initialize or repair a mission Store. This is not a read-only command:
the caller may commit the reviewed research identity in sync_metadata.
"""
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3

from .contracts import ContractError


class ExistingResearchStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / 'missions.sqlite3'

    @contextmanager
    def connection(self):
        if any((self.directory / name).exists() for name in
               ('RECOVERY-REVIEW-ONLY', 'review.pending.sqlite3')):
            raise ContractError('RECOVERY_REVIEW_ONLY')
        db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            # Validation remains in the SAME write transaction as the binding.
            # _binding_connection begins that transaction before using this Store.
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def validate(db):
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ContractError('INVALID_RESEARCH_MISSION_STORE')
        if db.execute("SELECT value FROM sync_metadata WHERE key='recovery_mode'").fetchone() is not None:
            raise ContractError('RECOVERY_REVIEW_ONLY')
        row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
        if row is None or type(row[0]) is not str or re.fullmatch(r's-[0-9a-f]{32}', row[0]) is None:
            raise ContractError('INVALID_RESEARCH_MISSION_STORE')
        # Missing mission evidence must not be interpreted as a new empty Store.
        db.execute('SELECT id,body FROM missions LIMIT 0')
