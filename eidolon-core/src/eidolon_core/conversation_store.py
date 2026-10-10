# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_store.py
# Description : Dépôt durable des conversations, séparé du Store des missions, idempotent après coupure (C-TASK-G085)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""<state>/conversations/conversations.sqlite3, bound to the mission Store identity.

The mission database is never migrated or written here; missions are created only through the
callable given to submit(). The two databases share no transaction, so a submission is reserved
BEFORE its mission is created: after a cut, a reserved submission without mission is resolved by
looking for candidate missions, and any candidate makes it UNCERTAIN (a human decides) rather
than creating a second mission. Model text, sources and replies are conversation data: nothing
here writes to Memory Engine, imports conversations or turns a reply into a fact.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

from . import conversation as cv
from .commands import validate_scope
from .contracts import ContractError, digest, encode
from .store import now
from .sqlite_errors import is_busy

SCHEMA = "eidolon-conversation-store/6"
SCHEMA_V1 = "eidolon-conversation-store/1"
VERSION = 6
SCHEMAS = {1: SCHEMA_V1, 2: "eidolon-conversation-store/2", 3: "eidolon-conversation-store/3",
           4: "eidolon-conversation-store/4",
           5: "eidolon-conversation-store/5", 6: SCHEMA}
# v2 adds one durable model attempt per turn (G090-R1). v1 is migrated only on explicit request.
ATTEMPTS_TABLE = ("CREATE TABLE attempts (turn_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, "
                  "started_at TEXT NOT NULL, deadline REAL NOT NULL)")
# v3 binds media artifact references to an owner and a conversation, server side (G097).
ATTACHMENTS_TABLE = ("CREATE TABLE attachments (conversation_id TEXT NOT NULL, artifact_id TEXT NOT NULL, "
                     "owner_client_id TEXT NOT NULL, reference TEXT NOT NULL, attached_at TEXT NOT NULL, "
                     "PRIMARY KEY(conversation_id, artifact_id))")
# One explicit step per version, each in its own transaction: an interrupted migration leaves a
# valid intermediate version that the same explicit command resumes.
# v4 links a submitted media proposal to the media job (and collection) that serves it. The private
# paths stay server side; they are never returned to a client.
MEDIA_LINKS_TABLE = ("CREATE TABLE media_links (conversation_id TEXT NOT NULL, proposal_sha256 TEXT NOT NULL, "
                     "owner_client_id TEXT NOT NULL, proposal TEXT NOT NULL, job_dir TEXT NOT NULL, "
                     "collection_dir TEXT, artifact_root TEXT NOT NULL, linked_at TEXT NOT NULL, "
                     "PRIMARY KEY(conversation_id, proposal_sha256))")
# v5 (Codex C-068, G123-R1) pins the exact job identity at link time. Existing v4 links stay
# NULL/unverifiable: never adopt the job currently found at an old path during migration.
MEDIA_LINK_JOB_ID = "ALTER TABLE media_links ADD COLUMN job_id TEXT"
# v6 (G122): media proposals are persisted next to mission proposals, each kind with its own version
# chain; "current" is the one frozen from the latest turn.
MEDIA_PROPOSALS_TABLE = ("CREATE TABLE media_proposals (proposal_id TEXT NOT NULL, version INTEGER NOT NULL, "
                         "conversation_id TEXT NOT NULL, source_sequence INTEGER NOT NULL, body TEXT NOT NULL, "
                         "sha256 TEXT NOT NULL, PRIMARY KEY(proposal_id, version))")
MIGRATIONS = {1: (ATTEMPTS_TABLE,), 2: (ATTACHMENTS_TABLE,), 3: (MEDIA_LINKS_TABLE,), 4: (MEDIA_LINK_JOB_ID,),
              5: (MEDIA_PROPOSALS_TABLE,)}
RECEIPT_PROTOCOL = "eidolon-proposal-submission-receipt/1"
# C-070: the last valid dialogue personality, a meta row like the profile selection (no schema change).
PERSONALITY_KEY = "personality_last_valid"
MAX_TURNS = 1000
MAX_PAGE = 50
MAX_CANDIDATES = 10
MAX_CONTEXT_TURNS = 200
MAX_CONTEXT_CHARS = 200_000
BUSY_SECONDS = 2.0


class ConversationError(ContractError):
    pass


def _key(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value) is None:
        raise ConversationError("INVALID_CONVERSATION: invalid " + name)
    return value


class ConversationStore:
    def __init__(self, store, *, create=False, migrate=False, checkpoint=None, before_migration=None):
        """create=True creates a missing store; otherwise an existing one is reopened, never created.

        before_migration(db), if given, runs inside the FIRST migration transaction, under the write lock
        (G099: the verified backup must still match the database being migrated).
        """
        self.store = store
        self.directory = Path(store.directory) / "conversations"
        self.path = self.directory / "conversations.sqlite3"
        self.checkpoint = checkpoint or (lambda name: None)   # fault injection in tests only
        self.before_migration = before_migration
        self._identity = None
        with store.connection() as db:
            row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
        self.store_id = row[0]
        if create:
            try:
                os.mkdir(self.directory, 0o700)
            except FileExistsError:
                pass
            self._check_directory()
            try:
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
            except FileExistsError:
                pass                       # an existing file is checked below like any reopening
            except OSError:
                raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: cannot create") from None
        self._check_directory()
        self._identity = self._check_file()
        try:
            db = self._connect()
            try:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, *SCHEMAS):
                    raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: unsupported schema version")
                empty = db.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
                # Tables are only ever added to an EMPTY database on explicit creation; any existing
                # database must already be ours (meta check below). executescript commits by itself:
                # the schema carries its own explicit transaction.
                if create and empty:
                    # Both values are inlined in the script (executescript takes no parameters):
                    # SCHEMA is a constant and the Store id is checked against its strict pattern.
                    if re.fullmatch(r"s-[0-9a-f]{32}", self.store_id) is None:
                        raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: invalid Store identity")
                    db.executescript("""
                        BEGIN IMMEDIATE;
                        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                        CREATE TABLE IF NOT EXISTS conversations (
                            conversation_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, client_key TEXT NOT NULL,
                            created_at TEXT NOT NULL, turn_count INTEGER NOT NULL DEFAULT 0,
                            last_turn_sha256 TEXT, UNIQUE(client_id, client_key));
                        CREATE TABLE IF NOT EXISTS turns (
                            conversation_id TEXT NOT NULL, sequence INTEGER NOT NULL, turn_id TEXT NOT NULL UNIQUE,
                            client_id TEXT NOT NULL, client_turn_key TEXT NOT NULL, body TEXT NOT NULL,
                            sha256 TEXT NOT NULL, received_at TEXT NOT NULL,
                            PRIMARY KEY(conversation_id, sequence), UNIQUE(client_id, client_turn_key));
                        CREATE TABLE IF NOT EXISTS replies (
                            turn_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, body TEXT NOT NULL,
                            sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL);
                        CREATE TABLE IF NOT EXISTS proposals (
                            proposal_id TEXT NOT NULL, version INTEGER NOT NULL, conversation_id TEXT NOT NULL,
                            body TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(proposal_id, version));
                        CREATE TABLE IF NOT EXISTS submissions (
                            client_id TEXT NOT NULL, command_key TEXT NOT NULL, body TEXT NOT NULL,
                            sha256 TEXT NOT NULL, conversation_id TEXT NOT NULL, status TEXT NOT NULL,
                            reserved_at TEXT NOT NULL, mission_id TEXT, link TEXT, resolution TEXT,
                            PRIMARY KEY(client_id, command_key));
                        %s;
                        %s;
                        %s;
                        %s;
                        %s;
                        INSERT INTO meta VALUES ('schema', '%s');
                        INSERT INTO meta VALUES ('store_id', '%s');
                        PRAGMA user_version=6;
                        COMMIT;
                    """ % (ATTEMPTS_TABLE, ATTACHMENTS_TABLE, MEDIA_LINKS_TABLE, MEDIA_LINK_JOB_ID, MEDIA_PROPOSALS_TABLE,
                           SCHEMA, self.store_id))
                elif migrate and version in MIGRATIONS:
                    self._migrate(db)
            finally:
                db.close()
        except sqlite3.OperationalError as exc:
            code = "CONVERSATION_STORE_BUSY" if is_busy(exc) else "CONVERSATION_STORE_UNAVAILABLE"
            raise ConversationError(code + ": " + str(exc)[:80]) from None
        except sqlite3.DatabaseError as exc:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: " + str(exc)[:80]) from None
        # Read-only check: an existing database is never completed or repaired here (G085-R5).
        with self._db():
            pass

    def _check_directory(self):
        try:
            info = os.lstat(self.directory)
        except FileNotFoundError:
            raise ConversationError("CONVERSATION_STORE_MISSING: create it explicitly") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: directory is a link or not a directory")
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: directory is not private")

    def _check_file(self):
        """Regular private file, never a link, and still the file opened first (device, inode)."""
        try:
            info = os.lstat(self.path)
        except FileNotFoundError:
            raise ConversationError("CONVERSATION_STORE_MISSING: create it explicitly") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: database is a link or not a regular file")
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: database is not private")
        identity = (info.st_dev, info.st_ino)
        if self._identity is not None and identity != self._identity:
            raise ConversationError("STORE_CHANGED: the conversation database was replaced")
        return identity

    def _connect(self):
        # mode=rw: SQLite never creates the file, even for a read of a deleted database.
        return sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True,
                               timeout=BUSY_SECONDS, isolation_level=None)

    def _migrate(self, db):
        """Explicit migration to the current version, one audited step per version."""
        first = True
        while True:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == VERSION:
                return
            if version not in MIGRATIONS:
                raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: no migration from this version")
            db.execute("BEGIN IMMEDIATE")
            try:
                meta = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('schema','store_id')"))
                if meta.get("schema") != SCHEMAS[version]:
                    raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: schema and version disagree")
                if meta.get("store_id") != self.store_id:
                    raise ConversationError("STORE_CHANGED: conversations belong to another mission Store")
                if first and self.before_migration is not None:
                    self.before_migration(db)
                first = False
                self.checkpoint("MIGRATION_STEP_%d" % version)        # fault injection in tests only
                for statement in MIGRATIONS[version]:
                    db.execute(statement)
                db.execute("UPDATE meta SET value=? WHERE key='schema'", (SCHEMAS[version + 1],))
                db.execute("PRAGMA user_version=%d" % (version + 1))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def _check_meta(self, db):
        meta = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('schema','store_id')"))
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version in MIGRATIONS and meta.get("schema") == SCHEMAS[version]:
            raise ConversationError("CONVERSATION_STORE_MIGRATION_REQUIRED: run the explicit migration to v%d" % VERSION)
        if meta.get("schema") != SCHEMA or version != VERSION:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: unknown schema")
        if meta.get("store_id") != self.store_id:
            raise ConversationError("STORE_CHANGED: conversations belong to another mission Store")

    @contextmanager
    def _db(self, *, write=False, check_meta=True):
        self._check_directory()
        self._check_file()
        try:
            db = self._connect()
        except sqlite3.Error as exc:
            code = "CONVERSATION_STORE_BUSY" if is_busy(exc) else "CONVERSATION_STORE_UNAVAILABLE"
            raise ConversationError(code + ": cannot open") from None
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if check_meta:
                self._check_meta(db)       # identity and schema, inside the transaction, every time
            yield db
            db.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            db.rollback() if db.in_transaction else None
            if is_busy(exc):
                raise ConversationError("CONVERSATION_STORE_BUSY: retry later") from None
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: " + str(exc)[:80]) from None
        except sqlite3.DatabaseError as exc:
            db.rollback() if db.in_transaction else None
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: " + str(exc)[:80]) from None
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def _submission_lock(self):
        """Serializes mission creation for submissions; held across the two databases."""
        fd = os.open(self.directory / "submissions.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    @staticmethod
    def _load(raw):
        return json.loads(raw)

    # -- conversations and turns ------------------------------------------------------------

    def open(self, *, client_id, client_key):
        """Idempotent: the same client key returns the same conversation."""
        validate_scope(self.store_id, client_id, client_key)
        with self._db(write=True) as db:
            row = db.execute("SELECT conversation_id FROM conversations WHERE client_id=? AND client_key=?",
                             (client_id, client_key)).fetchone()
            if row:
                return {"conversation_id": row[0], "created": False}
            identity = "c-" + uuid.uuid4().hex
            db.execute("INSERT INTO conversations(conversation_id, client_id, client_key, created_at) VALUES (?,?,?,?)",
                       (identity, client_id, client_key, now()))
            return {"conversation_id": identity, "created": True}

    def append_turn(self, conversation_id, *, client_id, client_turn_key, text):
        """Record one user turn. A retry with the same key returns the recorded turn and reply."""
        validate_scope(self.store_id, client_id, client_turn_key)
        request = {"conversation_id": conversation_id, "text": text}
        with self._db(write=True) as db:
            row = db.execute("SELECT body FROM turns WHERE client_id=? AND client_turn_key=?",
                             (client_id, client_turn_key)).fetchone()
            if row:
                turn = self._load(row[0])
                cv.same_request({"conversation_id": turn["conversation_id"], "text": turn["text"]}, request,
                                "TURN_KEY_REUSED")
                reply = db.execute("SELECT body FROM replies WHERE turn_id=?", (turn["turn_id"],)).fetchone()
                return {"turn": turn, "reply": self._load(reply[0]) if reply else None, "replayed": True}
            conv = db.execute("SELECT turn_count, last_turn_sha256 FROM conversations WHERE conversation_id=?",
                              (conversation_id,)).fetchone()
            if conv is None:
                raise ConversationError("CONVERSATION_UNKNOWN")
            if conv[0] >= MAX_TURNS:
                raise ConversationError("CONVERSATION_FULL: start a new conversation")
            previous = None
            if conv[0]:
                previous = self._load(db.execute("SELECT body FROM turns WHERE conversation_id=? AND sequence=?",
                                                 (conversation_id, conv[0])).fetchone()[0])
            turn = cv.check_turn_order(previous, {
                "protocol": cv.TURN_PROTOCOL, "store_id": self.store_id, "conversation_id": conversation_id,
                "turn_id": "t-" + uuid.uuid4().hex, "sequence": conv[0] + 1, "role": "user", "text": text,
                "client_id": client_id, "client_turn_key": client_turn_key,
                "previous_turn_sha256": conv[1]})
            sha = digest(turn)
            db.execute("INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)",
                       (conversation_id, turn["sequence"], turn["turn_id"], client_id, client_turn_key,
                        encode(turn), sha, now()))
            db.execute("UPDATE conversations SET turn_count=?, last_turn_sha256=? WHERE conversation_id=?",
                       (turn["sequence"], sha, conversation_id))
            return {"turn": turn, "reply": None, "replayed": False}

    def record_reply(self, reply):
        """One reply per turn. Re-recording the same reply is a no-op; a different one is refused."""
        reply = cv.snapshot(reply)
        if not isinstance(reply, dict) or reply.get("protocol") != cv.REPLY_PROTOCOL:
            raise ConversationError("INVALID_CONVERSATION: reply protocol required")
        with self._db(write=True) as db:
            row = db.execute("SELECT body, sha256 FROM turns WHERE turn_id=?", (reply.get("in_reply_to"),)).fetchone()
            if row is None or reply.get("turn_sha256") != row[1] or reply.get("store_id") != self.store_id:
                raise ConversationError("REPLY_INVALID: reply does not answer a recorded turn")
            turn = self._load(row[0])
            if reply.get("conversation_id") != turn["conversation_id"]:
                raise ConversationError("REPLY_INVALID: reply belongs to another conversation")
            existing = db.execute("SELECT body FROM replies WHERE turn_id=?", (turn["turn_id"],)).fetchone()
            if existing:
                cv.same_request(self._load(existing[0]), reply, "REPLY_ALREADY_RECORDED")
                return self._load(existing[0])
            proposal = reply.get("proposal")
            if isinstance(proposal, dict) and proposal.get("protocol") == "eidolon-media-proposal/1":
                self._record_media_proposal(db, turn, reply, proposal)
            elif proposal is not None:
                proposal = cv.validate_proposal(proposal)
                if (reply.get("proposal_sha256") != cv.proposal_sha256(proposal)
                        or proposal["source_turn_id"] != turn["turn_id"]
                        or proposal["conversation_id"] != turn["conversation_id"]):
                    raise ConversationError("REPLY_INVALID: proposal does not come from this turn")
                latest = self._latest_proposal(db, turn["conversation_id"])
                expected = (latest["version"] + 1, cv.proposal_sha256(latest)) if latest else (1, None)
                if (proposal["version"], proposal["supersedes_sha256"]) != expected or (
                        latest and proposal["proposal_id"] != latest["proposal_id"]):
                    raise ContractError("PROPOSAL_STALE: proposal does not supersede the latest version")
                db.execute("INSERT INTO proposals VALUES (?,?,?,?,?)",
                           (proposal["proposal_id"], proposal["version"], proposal["conversation_id"],
                            encode(proposal), cv.proposal_sha256(proposal)))
            db.execute("INSERT INTO replies VALUES (?,?,?,?,?)",
                       (turn["turn_id"], turn["conversation_id"], encode(reply), digest(reply), now()))
            return reply

    def _record_media_proposal(self, db, turn, reply, proposal):
        """G122: a Core-frozen media proposal from THIS turn, extending the conversation's media chain."""
        from .conversation_media import validate_proposal as validate_media
        proposal = validate_media(proposal)
        if (reply.get("proposal_sha256") != digest(proposal) or proposal["source_turn_id"] != turn["turn_id"]
                or proposal["source_turn_sha256"] != digest(turn)
                or proposal["conversation_id"] != turn["conversation_id"] or proposal["store_id"] != self.store_id
                or proposal["owner_client_id"] != turn["client_id"]):
            raise ConversationError("REPLY_INVALID: media proposal does not come from this turn")
        latest = self._latest_media_proposal(db, turn["conversation_id"])
        expected = (latest["version"] + 1, digest(latest)) if latest else (1, None)
        if (proposal["version"], proposal["supersedes_sha256"]) != expected or (
                latest and proposal["proposal_id"] != latest["proposal_id"]):
            raise ContractError("PROPOSAL_STALE: media proposal does not supersede the latest version")
        db.execute("INSERT INTO media_proposals VALUES (?,?,?,?,?,?)",
                   (proposal["proposal_id"], proposal["version"], proposal["conversation_id"], turn["sequence"],
                    encode(proposal), digest(proposal)))

    def _latest_media_proposal(self, db, conversation_id):
        row = db.execute("SELECT body FROM media_proposals WHERE conversation_id=? ORDER BY version DESC LIMIT 1",
                         (conversation_id,)).fetchone()
        return self._load(row[0]) if row else None

    def _current(self, db, conversation_id):
        """The proposal frozen from the LATEST turn that produced one, of either kind (G122)."""
        mission = self._latest_proposal(db, conversation_id)
        media = db.execute("SELECT body, source_sequence FROM media_proposals WHERE conversation_id=? "
                           "ORDER BY version DESC LIMIT 1", (conversation_id,)).fetchone()
        if media is None:
            return mission
        if mission is None:
            return self._load(media[0])
        row = db.execute("SELECT sequence FROM turns WHERE turn_id=?", (mission["source_turn_id"],)).fetchone()
        return mission if row is not None and row[0] > media[1] else self._load(media[0])

    def current_mission_proposal(self, conversation_id):
        """Latest MISSION proposal: the one a new mission proposal must supersede (its own chain)."""
        with self._db() as db:
            return self._latest_proposal(db, conversation_id)

    def current_media_proposal(self, conversation_id):
        with self._db() as db:
            return self._latest_media_proposal(db, conversation_id)

    def media_proposals(self, conversation_id):
        """Every media proposal of this conversation, oldest first (for results and the export)."""
        with self._db() as db:
            rows = db.execute("SELECT body FROM media_proposals WHERE conversation_id=? ORDER BY version",
                              (conversation_id,)).fetchall()
        return [self._load(r[0]) for r in rows]

    def _latest_proposal(self, db, conversation_id):
        row = db.execute("SELECT body FROM proposals WHERE conversation_id=? ORDER BY version DESC LIMIT 1",
                         (conversation_id,)).fetchone()
        return self._load(row[0]) if row else None

    def claim_attempt(self, turn_id, *, seconds):
        """Admit at most ONE model attempt per turn, durably, before any model call (G090-R1).

        Returns "answered" (a reply exists), "claimed" (this caller may call the model once), "busy"
        (another attempt is within its deadline) or "expired" (an attempt started and never recorded a
        reply: interrupted). Expired never grants a second model call; the caller closes the turn.
        """
        import time
        if type(seconds) not in (int, float) or not 0 < seconds <= 3600:
            raise ConversationError("INVALID_CONVERSATION: invalid attempt budget")
        with self._db(write=True) as db:
            row = db.execute("SELECT conversation_id FROM turns WHERE turn_id=?", (turn_id,)).fetchone()
            if row is None:
                raise ConversationError("TURN_UNKNOWN")
            if db.execute("SELECT 1 FROM replies WHERE turn_id=?", (turn_id,)).fetchone():
                return "answered"
            attempt = db.execute("SELECT deadline FROM attempts WHERE turn_id=?", (turn_id,)).fetchone()
            if attempt is None:
                db.execute("INSERT INTO attempts VALUES (?,?,?,?)", (turn_id, row[0], now(), time.time() + seconds))
                return "claimed"
            return "busy" if time.time() < attempt[0] else "expired"

    def current_proposal(self, conversation_id):
        """Latest proposal of either kind: only it may be submitted (missions or media, G122)."""
        with self._db() as db:
            return self._current(db, conversation_id)

    def last_turn(self, conversation_id):
        with self._db() as db:
            row = db.execute("SELECT body FROM turns WHERE conversation_id=? ORDER BY sequence DESC LIMIT 1",
                             (conversation_id,)).fetchone()
            return self._load(row[0]) if row else None

    # -- reading ----------------------------------------------------------------------------

    def owner(self, conversation_id):
        """client_id that opened the conversation, or None (an API never reveals which)."""
        with self._db() as db:
            row = db.execute("SELECT client_id FROM conversations WHERE conversation_id=?",
                             (conversation_id,)).fetchone()
        return row[0] if row else None

    def recent(self, client_id, *, limit=10):
        """This client's non-empty conversations, newest first, to resume after a reload (G092)."""
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ConversationError("INVALID_CONVERSATION: invalid limit")
        with self._db() as db:
            rows = db.execute("""SELECT c.conversation_id, c.created_at, c.turn_count, max(t.received_at)
                                 FROM conversations c JOIN turns t ON t.conversation_id = c.conversation_id
                                 WHERE c.client_id=? GROUP BY c.conversation_id
                                 ORDER BY max(t.received_at) DESC, c.conversation_id LIMIT ?""",
                              (client_id, limit)).fetchall()
        return [{"conversation_id": r[0], "created_at": r[1], "turn_count": r[2], "last_turn_at": r[3]} for r in rows]

    def attach(self, *, owner_client_id, conversation_id, reference, verify):
        """Bind an artifact reference to ITS owner's conversation (operator or authenticated upload, G097).

        verify(reference) must prove the artifact exists unchanged (Codex's ArtifactStore.read); nothing
        is recorded otherwise. The same artifact may be attached again only to the same owner.
        """
        from .conversation_media import attachment
        record = attachment(store_id=self.store_id, owner_client_id=owner_client_id,
                            conversation_id=conversation_id, reference=reference)
        verify(record["reference"])
        with self._db(write=True) as db:
            owner = db.execute("SELECT client_id FROM conversations WHERE conversation_id=?",
                               (conversation_id,)).fetchone()
            if owner is None or owner[0] != owner_client_id:
                raise ConversationError("CONVERSATION_UNKNOWN: no such conversation for this owner")
            existing = db.execute("SELECT owner_client_id, reference FROM attachments WHERE conversation_id=? "
                                  "AND artifact_id=?", (conversation_id, record["reference"]["artifact_id"])).fetchone()
            if existing:
                if existing[0] != owner_client_id or json.loads(existing[1]) != record["reference"]:
                    raise ConversationError("ATTACHMENT_CONFLICT: this artifact is attached differently")
                return record
            db.execute("INSERT INTO attachments VALUES (?,?,?,?,?)",
                       (conversation_id, record["reference"]["artifact_id"], owner_client_id,
                        encode(record["reference"]), now()))
        return record

    def attachments(self, *, owner_client_id, conversation_id):
        """Attachments recorded for this owner AND this conversation only (fresh, for each proposal)."""
        from .conversation_media import attachment
        with self._db() as db:
            rows = db.execute("SELECT reference FROM attachments WHERE conversation_id=? AND owner_client_id=? "
                              "ORDER BY attached_at, artifact_id", (conversation_id, owner_client_id)).fetchall()
        return [attachment(store_id=self.store_id, owner_client_id=owner_client_id, conversation_id=conversation_id,
                           reference=json.loads(r[0])) for r in rows]

    def link_media(self, *, owner_client_id, conversation_id, proposal, job_dir, artifact_root, job_id, collection_dir=None):
        """Pin the job id and private locations of a media proposal; never silently rebind an old link."""
        from .conversation_media import validate_proposal
        proposal = validate_proposal(proposal)
        if (proposal["owner_client_id"] != owner_client_id or proposal["conversation_id"] != conversation_id
                or proposal["store_id"] != self.store_id):
            raise ConversationError("CONVERSATION_UNKNOWN: proposal of another owner or conversation")
        if not isinstance(job_id, str) or re.fullmatch(r"media-[0-9a-f]{32}", job_id) is None:
            raise ConversationError("INVALID_CONVERSATION: an exact media job identity is required")
        paths = [job_dir, artifact_root] + ([collection_dir] if collection_dir is not None else [])
        if any(not isinstance(p, str) or not os.path.isabs(p) or len(p) > 1024 for p in paths):
            raise ConversationError("INVALID_CONVERSATION: absolute server paths required")
        sha = digest(proposal)
        with self._db(write=True) as db:
            owner = db.execute("SELECT client_id FROM conversations WHERE conversation_id=?",
                               (conversation_id,)).fetchone()
            if owner is None or owner[0] != owner_client_id:
                raise ConversationError("CONVERSATION_UNKNOWN: no such conversation for this owner")
            existing = db.execute("SELECT job_dir, collection_dir, artifact_root, job_id FROM media_links "
                                  "WHERE conversation_id=? AND proposal_sha256=?", (conversation_id, sha)).fetchone()
            if existing:
                if tuple(existing) != (job_dir, collection_dir, artifact_root, job_id):
                    raise ConversationError("MEDIA_LINK_CONFLICT: this proposal is already linked to another job")
                return sha
            db.execute("INSERT INTO media_links (conversation_id, proposal_sha256, owner_client_id, proposal, "
                       "job_dir, collection_dir, artifact_root, linked_at, job_id) VALUES (?,?,?,?,?,?,?,?,?)",
                       (conversation_id, sha, owner_client_id, encode(proposal), job_dir, collection_dir,
                        artifact_root, now(), job_id))
        return sha

    def media_links(self, *, owner_client_id, conversation_id):
        """Links of this owner's conversation, oldest first. Server-side use only (they hold paths)."""
        with self._db() as db:
            rows = db.execute("SELECT proposal, job_dir, collection_dir, artifact_root, job_id FROM media_links "
                              "WHERE conversation_id=? AND owner_client_id=? ORDER BY linked_at, proposal_sha256",
                              (conversation_id, owner_client_id)).fetchall()
        return [{"proposal": json.loads(r[0]), "job_dir": r[1], "collection_dir": r[2], "artifact_root": r[3], "job_id": r[4]}
                for r in rows]

    def select_profile(self, name, *, actor):
        """Explicit operator choice of the dialogue profile (G098). Never made by a model or a fallback."""
        if not isinstance(name, str) or not cv.PROFILE_NAME.fullmatch(name):
            raise ConversationError("INVALID_CONVERSATION: invalid profile name")
        if not isinstance(actor, str) or not 1 <= len(actor) <= 200:
            raise ConversationError("INVALID_CONVERSATION: an actor is required")
        value = {"name": name, "actor": actor, "selected_at": now()}
        with self._db(write=True) as db:
            db.execute("INSERT INTO meta VALUES ('dialogue_profile', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (encode(value),))
        return value

    def selected_profile(self):
        """The profile last selected explicitly, or None. Its availability is checked by the caller."""
        with self._db() as db:
            row = db.execute("SELECT value FROM meta WHERE key='dialogue_profile'").fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if not isinstance(value, dict) or set(value) != {"name", "actor", "selected_at"} \
                or not isinstance(value["name"], str) or not cv.PROFILE_NAME.fullmatch(value["name"]):
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: invalid profile selection")
        return value

    def personality_copy(self):
        """The last valid dialogue personality kept by Core (C-070), as stored text, or None.

        Checked by personality.parse_copy: the store keeps it, it does not interpret it.
        """
        with self._db() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (PERSONALITY_KEY,)).fetchone()
        return None if row is None else row[0]

    def keep_personality_copy(self, body):
        """Replace the kept personality copy, in one transaction (saved and restored with the store)."""
        if not isinstance(body, str) or not 1 <= len(body.encode("utf-8")) <= 64 * 1024:
            raise ConversationError("INVALID_CONVERSATION: invalid personality copy")
        with self._db(write=True) as db:
            db.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (PERSONALITY_KEY, body))

    def missions_of(self, client_id, conversation_id):
        """Missions created from THIS client's submissions in THIS conversation: {mission_id: link} (G100)."""
        with self._db() as db:
            rows = db.execute("SELECT mission_id, link FROM submissions WHERE client_id=? AND conversation_id=? "
                              "AND status='MISSION_CREATED' ORDER BY reserved_at, command_key",
                              (client_id, conversation_id)).fetchall()
        return {mission_id: json.loads(link) for mission_id, link in rows}

    def submitted_by(self, client_id, mission_id):
        """True only for a mission created from one of this client's submissions."""
        with self._db() as db:
            return db.execute("SELECT 1 FROM submissions WHERE client_id=? AND mission_id=? "
                              "AND status='MISSION_CREATED'", (client_id, mission_id)).fetchone() is not None

    def page(self, conversation_id, *, after=0, limit=20):
        """Turns with their reply, in order; resume after reconnection with the last sequence."""
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= MAX_PAGE:
            raise ConversationError("INVALID_CONVERSATION: invalid page bounds")
        with self._db() as db:
            if db.execute("SELECT 1 FROM conversations WHERE conversation_id=?", (conversation_id,)).fetchone() is None:
                raise ConversationError("CONVERSATION_UNKNOWN")
            rows = db.execute("""SELECT t.body, t.received_at, r.body FROM turns t
                                 LEFT JOIN replies r ON r.turn_id = t.turn_id
                                 WHERE t.conversation_id=? AND t.sequence>? ORDER BY t.sequence LIMIT ?""",
                              (conversation_id, after, limit + 1)).fetchall()
        items = [{"turn": self._load(t), "received_at": at, "reply": self._load(r) if r else None}
                 for t, at, r in rows[:limit]]
        return {"protocol": "eidolon-conversation-page/1", "store_id": self.store_id,
                "conversation_id": conversation_id, "items": items, "has_more": len(rows) > limit,
                "next_after": items[-1]["turn"]["sequence"] if items else after}

    def context(self, conversation_id, *, max_turns=20, max_chars=16000):
        """Most recent turns and reply texts within a budget, oldest first (for the dialogue)."""
        if (type(max_turns) is not int or not 1 <= max_turns <= MAX_CONTEXT_TURNS
                or type(max_chars) is not int or not 1 <= max_chars <= MAX_CONTEXT_CHARS):
            raise ConversationError("INVALID_CONVERSATION: invalid context bounds")
        with self._db() as db:
            rows = db.execute("""SELECT t.body, r.body FROM turns t LEFT JOIN replies r ON r.turn_id = t.turn_id
                                 WHERE t.conversation_id=? ORDER BY t.sequence DESC LIMIT ?""",
                              (conversation_id, max_turns)).fetchall()
        kept, used = [], 0
        for turn_raw, reply_raw in rows:
            turn, reply = self._load(turn_raw), self._load(reply_raw) if reply_raw else None
            size = len(turn["text"]) + len((reply or {}).get("model_text") or "")
            if used + size > max_chars:
                break
            kept.append({"sequence": turn["sequence"], "user": turn["text"],
                         "reply_kind": reply and reply["kind"], "reply_text": reply and reply["model_text"]})
            used += size
        return {"turns": list(reversed(kept)), "truncated": len(kept) < len(rows) or len(rows) == max_turns,
                "chars": used}

    # -- submissions --------------------------------------------------------------------------

    def _receipt(self, row):
        body, status, mission_id, link, resolution = row
        submission = self._load(body)
        return {"protocol": RECEIPT_PROTOCOL, "store_id": self.store_id, "client_id": submission["client_id"],
                "command_key": submission["command_key"], "submission_sha256": digest(submission),
                "conversation_id": submission["conversation_id"], "proposal_id": submission["proposal_id"],
                "proposal_version": submission["proposal_version"], "status": status, "mission_id": mission_id,
                "link": self._load(link) if link else None, "resolution": self._load(resolution) if resolution else None,
                "execution_evidence": False}

    def _existing_submission(self, db, submission):
        row = db.execute("SELECT body, status, mission_id, link, resolution FROM submissions "
                         "WHERE client_id=? AND command_key=?",
                         (submission["client_id"], submission["command_key"])).fetchone()
        if row and digest(self._load(row[0])) != digest(submission):
            raise ContractError("COMMAND_KEY_REUSED: key already bound to another submission")
        return row

    def _candidates(self, request, since):
        with self.store.connection() as db:
            rows = db.execute("SELECT id FROM missions WHERE json_extract(body,'$.request')=? "
                              "AND json_extract(body,'$.created_at')>=? ORDER BY id LIMIT ?",
                              (request, since, MAX_CANDIDATES)).fetchall()
        return [r[0] for r in rows]

    def submit(self, submission, *, create):
        """Human submission of the latest frozen proposal; create(request, intent) makes the mission once."""
        submission = cv.validate_submission(submission)
        if submission["store_id"] != self.store_id:
            raise ContractError("STORE_CHANGED: resynchronize before submitting")
        with self._submission_lock():
            with self._db(write=True) as db:
                row = self._existing_submission(db, submission)
                fresh = row is None
                if row is None:
                    proposal = self._latest_proposal(db, submission["conversation_id"])
                    current = self._current(db, submission["conversation_id"])
                    if current is not None and current != proposal:
                        raise ContractError("PROPOSAL_STALE: a newer media proposal exists; review it")
                    cv.check_submission(submission, proposal)
                    open_row = db.execute("SELECT command_key FROM submissions WHERE conversation_id=? AND "
                                          "status IN ('RESERVED','MISSION_CREATED','MISSION_CREATION_UNCERTAIN') "
                                          "AND json_extract(body,'$.proposal_sha256')=?",
                                          (submission["conversation_id"], submission["proposal_sha256"])).fetchone()
                    if open_row:
                        raise ContractError("PROPOSAL_ALREADY_SUBMITTED: see the existing receipt " + open_row[0])
                    db.execute("INSERT INTO submissions(client_id, command_key, body, sha256, conversation_id, status,"
                               " reserved_at) VALUES (?,?,?,?,?,?,?)",
                               (submission["client_id"], submission["command_key"], encode(submission),
                                digest(submission), submission["conversation_id"], "RESERVED", now()))
                    row = (encode(submission), "RESERVED", None, None, None)
                elif row[1] != "RESERVED":
                    return self._receipt(row)
                reserved_at = db.execute("SELECT reserved_at FROM submissions WHERE client_id=? AND command_key=?",
                                         (submission["client_id"], submission["command_key"])).fetchone()[0]
                # Always the proposal the human submitted, never a newer one recorded since.
                proposal = cv.validate_proposal(self._load(db.execute(
                    "SELECT body FROM proposals WHERE proposal_id=? AND version=?",
                    (submission["proposal_id"], submission["proposal_version"])).fetchone()[0]))
                latest = self._latest_proposal(db, submission["conversation_id"])
            self.checkpoint("SUBMISSION_RESERVED")
            request, intent = cv.mission_arguments(proposal)
            # Under the submission lock, a reservation not made by this call was left by an attempt
            # that stopped before recording its mission: it may or may not have created one.
            if not fresh:
                candidates = self._candidates(request, reserved_at)
                if candidates:
                    with self._db(write=True) as db:
                        db.execute("UPDATE submissions SET status='MISSION_CREATION_UNCERTAIN', resolution=? "
                                   "WHERE client_id=? AND command_key=?",
                                   (encode({"candidates": candidates}), submission["client_id"],
                                    submission["command_key"]))
                        return self._receipt(self._existing_submission(db, submission))
                if latest["version"] != proposal["version"]:
                    # No mission exists and the conversation moved on: never create a superseded mission.
                    with self._db(write=True) as db:
                        db.execute("UPDATE submissions SET status='SUPERSEDED_NOT_CREATED', resolution=? "
                                   "WHERE client_id=? AND command_key=?",
                                   (encode({"latest_version": latest["version"]}), submission["client_id"],
                                    submission["command_key"]))
                        return self._receipt(self._existing_submission(db, submission))
            mission = create(request, intent)
            self.checkpoint("MISSION_CREATED")
            link = cv.make_link(submission, proposal, mission)
            with self._db(write=True) as db:
                db.execute("UPDATE submissions SET status='MISSION_CREATED', mission_id=?, link=? "
                           "WHERE client_id=? AND command_key=? AND status='RESERVED'",
                           (mission["id"], encode(link), submission["client_id"], submission["command_key"]))
                return self._receipt(self._existing_submission(db, submission))

    def resolve_uncertain(self, *, client_id, command_key, mission_id, actor, reason):
        """A human decides an UNCERTAIN submission: adopt one candidate, or record that none is it."""
        _key(client_id, "client_id"), _key(command_key, "command_key")
        cv._text(actor, 200, "actor"), cv._text(reason, 4000, "reason")
        with self._submission_lock(), self._db(write=True) as db:
            row = db.execute("SELECT body, status, mission_id, link, resolution FROM submissions "
                             "WHERE client_id=? AND command_key=?", (client_id, command_key)).fetchone()
            if row is None or row[1] != "MISSION_CREATION_UNCERTAIN":
                raise ContractError("NOT_UNCERTAIN: nothing to resolve")
            submission, candidates = self._load(row[0]), self._load(row[4])["candidates"]
            decision = {"actor": actor, "reason": reason, "at": now(), "candidates": candidates}
            if mission_id is None:
                status, link = "NO_MISSION_CONFIRMED", None
            else:
                if mission_id not in candidates:
                    raise ContractError("NOT_A_CANDIDATE: choose one of the listed missions")
                proposal = cv.validate_proposal(self._load(db.execute(
                    "SELECT body FROM proposals WHERE proposal_id=? AND version=?",
                    (submission["proposal_id"], submission["proposal_version"])).fetchone()[0]))
                link = encode(cv.make_link(submission, proposal, self.store.get(mission_id)))
                status = "MISSION_CREATED"
            db.execute("UPDATE submissions SET status=?, mission_id=?, link=?, resolution=? "
                       "WHERE client_id=? AND command_key=?",
                       (status, mission_id, link, encode(decision), client_id, command_key))
            return self._receipt(self._existing_submission(db, submission))

    def receipt(self, *, client_id, command_key):
        """Find a submission receipt after a lost response; never a permission to resend."""
        validate_scope(self.store_id, client_id, command_key)
        with self._db() as db:
            row = db.execute("SELECT body, status, mission_id, link, resolution FROM submissions "
                             "WHERE client_id=? AND command_key=?", (client_id, command_key)).fetchone()
        return self._receipt(row) if row else None
