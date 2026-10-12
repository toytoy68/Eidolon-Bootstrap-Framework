# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_credentials.py
# Description : Vue en lecture seule des identites et clients de Core
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read existing databases only; never initialize or migrate Core from a media service."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import stat

from .client_credentials import ClientCredentials, CredentialError

class ReadOnlyCredentialStore:
    def __init__(self, directory):
        self.directory=Path(directory).absolute()
        if any(p.is_symlink() for p in (self.directory,*self.directory.parents)):
            raise ValueError('COMM_STATE_LINK_REFUSED')
        # A private owner directory encloses fixtures/state whose inner modes may
        # retain the operator's group-writable umask; other users cannot traverse it.
        self.enclosed=any(p.is_dir() and p.stat().st_uid==os.getuid() and not p.stat().st_mode & 0o077
                          for p in (self.directory,*self.directory.parents))
        info=self.directory.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid()
                or (info.st_mode & 0o022 and not self.enclosed)):
            raise ValueError('COMM_STATE_UNTRUSTED')
        self.path=self.directory/'missions.sqlite3'
        self.identity=self._identity()

    def _identity(self):
        info=self.path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or (info.st_mode & 0o022 and not self.enclosed)):
            raise ValueError('COMM_MISSION_STORE_UNTRUSTED')
        return info.st_dev,info.st_ino

    @contextmanager
    def connection(self):
        if self._identity()!=self.identity:
            raise ValueError('COMM_STORE_CHANGED')
        if any((self.directory/name).exists() for name in ('RECOVERY-REVIEW-ONLY','review.pending.sqlite3')):
            raise ValueError('RECOVERY_REVIEW_ONLY')
        db=None
        try:
            db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=2)
            if db.execute('PRAGMA user_version').fetchone()[0]!=1:
                raise ValueError('COMM_MISSION_SCHEMA_UNSUPPORTED')
            if db.execute("SELECT value FROM sync_metadata WHERE key='recovery_mode'").fetchone() is not None:
                raise ValueError('RECOVERY_REVIEW_ONLY')
            yield db
        except sqlite3.Error:
            raise ValueError('COMM_STATE_UNAVAILABLE') from None
        finally:
            if db is not None:
                db.close()

class ReadOnlyClientCredentials(ClientCredentials):
    def __init__(self, store):
        super().__init__(store,create=False)

    def _connect(self):
        try:
            return sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,
                                   timeout=2,isolation_level=None)
        except sqlite3.Error:
            raise CredentialError('CREDENTIALS_UNAVAILABLE: readonly pairing store unavailable') from None

    def pair(self, **kwargs):
        raise CredentialError('READ_ONLY_CREDENTIALS')

    def revoke(self, client_id):
        raise CredentialError('READ_ONLY_CREDENTIALS')
