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

SCHEMA = "eidolon-conversation-store/1"
RECEIPT_PROTOCOL = "eidolon-proposal-submission-receipt/1"
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
    def __init__(self, store, *, create=False, checkpoint=None):
        """create=True creates a missing store; otherwise an existing one is reopened, never created."""
        self.store = store
        self.directory = Path(store.directory) / "conversations"
        self.path = self.directory / "conversations.sqlite3"
        self.checkpoint = checkpoint or (lambda name: None)   # fault injection in tests only
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
                if version not in (0, 1):
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
                        INSERT INTO meta VALUES ('schema', '%s');
                        INSERT INTO meta VALUES ('store_id', '%s');
                        PRAGMA user_version=1;
                        COMMIT;
                    """ % (SCHEMA, self.store_id))
            finally:
                db.close()
        except sqlite3.OperationalError as exc:
            code = "CONVERSATION_STORE_BUSY" if "locked" in str(exc) else "CONVERSATION_STORE_UNAVAILABLE"
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

    def _check_meta(self, db):
        meta = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('schema','store_id')"))
        if meta.get("schema") != SCHEMA or db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: unknown schema")
        if meta.get("store_id") != self.store_id:
            raise ConversationError("STORE_CHANGED: conversations belong to another mission Store")

    @contextmanager
    def _db(self, *, write=False, check_meta=True):
        self._check_directory()
        self._check_file()
        try:
            db = self._connect()
        except sqlite3.Error:
            raise ConversationError("CONVERSATION_STORE_UNAVAILABLE: cannot open") from None
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if check_meta:
                self._check_meta(db)       # identity and schema, inside the transaction, every time
            yield db
            db.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            db.rollback() if db.in_transaction else None
            if "locked" in str(exc) or "busy" in str(exc):
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
            if proposal is not None:
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

    def _latest_proposal(self, db, conversation_id):
        row = db.execute("SELECT body FROM proposals WHERE conversation_id=? ORDER BY version DESC LIMIT 1",
                         (conversation_id,)).fetchone()
        return self._load(row[0]) if row else None

    def current_proposal(self, conversation_id):
        with self._db() as db:
            return self._latest_proposal(db, conversation_id)

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
