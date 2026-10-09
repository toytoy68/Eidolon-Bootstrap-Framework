# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : client_credentials.py
# Description : Appairage des clients de conversation : jeton d'écriture distinct du jeton de lecture (C-TASK-G087)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""<state>/conversations/clients.sqlite3: one row per paired client, the token's SHA-256 only.

A conversation credential lets its client talk, submit ITS proposals and request cancellation of
ITS missions. It is created by the operator on the server (pair), shown once, revocable, and is
never the read token: the read token keeps no write right anywhere.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat

from .contracts import ContractError
from .store import now

TOKEN_PATTERN = r"ecc_[A-Za-z0-9_-]{43}"
ACTOR_MAX = 200


class CredentialError(ContractError):
    pass


def _hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class ClientCredentials:
    def __init__(self, store, *, create=False):
        self.directory = Path(store.directory) / "conversations"
        self.path = self.directory / "clients.sqlite3"
        if create:
            try:
                os.mkdir(self.directory, 0o700)
            except FileExistsError:
                pass
            try:
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
                with self._db(write=True) as db:
                    db.execute("CREATE TABLE clients (client_id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
                               "token_sha256 TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, revoked_at TEXT)")
            except FileExistsError:
                pass
        with self._db():
            pass

    def _check(self):
        for path, kind in ((self.directory, stat.S_ISDIR), (self.path, stat.S_ISREG)):
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                raise CredentialError("CREDENTIALS_MISSING: pair a client first") from None
            if stat.S_ISLNK(info.st_mode) or not kind(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise CredentialError("CREDENTIALS_UNAVAILABLE: not a private regular file or directory")

    @contextmanager
    def _db(self, *, write=False):
        self._check()
        try:
            db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=2, isolation_level=None)
        except sqlite3.Error:
            raise CredentialError("CREDENTIALS_UNAVAILABLE: cannot open") from None
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.execute("COMMIT")
        except sqlite3.Error as exc:
            if db.in_transaction:
                db.rollback()
            raise CredentialError("CREDENTIALS_UNAVAILABLE: " + str(exc)[:60]) from None
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def pair(self, *, client_id, actor):
        """Create a client and return its token ONCE. Refuses an existing client id."""
        if not isinstance(client_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", client_id) is None:
            raise CredentialError("INVALID_CLIENT: invalid client_id")
        if not isinstance(actor, str) or not actor.strip() or len(actor) > ACTOR_MAX:
            raise CredentialError("INVALID_CLIENT: bounded actor name required")
        token = "ecc_" + secrets.token_urlsafe(32)
        with self._db(write=True) as db:
            if db.execute("SELECT 1 FROM clients WHERE client_id=?", (client_id,)).fetchone():
                raise CredentialError("CLIENT_EXISTS: revoke and pair under a new id")
            db.execute("INSERT INTO clients VALUES (?,?,?,?,NULL)", (client_id, actor, _hash(token), now()))
        return {"client_id": client_id, "actor": actor, "token": token}

    def revoke(self, client_id):
        with self._db(write=True) as db:
            if db.execute("UPDATE clients SET revoked_at=? WHERE client_id=? AND revoked_at IS NULL",
                          (now(), client_id)).rowcount != 1:
                raise CredentialError("CLIENT_UNKNOWN: no active client with this id")

    def authenticate(self, token):
        """Active client for this token, or None. Only the token's digest is compared."""
        if not isinstance(token, str) or re.fullmatch(TOKEN_PATTERN, token) is None:
            return None
        with self._db() as db:
            row = db.execute("SELECT client_id, actor FROM clients WHERE token_sha256=? AND revoked_at IS NULL",
                             (_hash(token),)).fetchone()
        return {"client_id": row[0], "actor": row[1]} if row else None
