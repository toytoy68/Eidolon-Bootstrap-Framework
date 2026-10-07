# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : store.py
# Description : Persistance transactionnelle des missions et événements
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""SQLite snapshots and audit events committed together; POSIX execution locks."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .contracts import ContractError, digest, encode
from .objectives import assess, define

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "ABANDONED"}


class Busy(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "missions.sqlite3"
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported mission database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL,
                    at TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_mission_sequence ON events(mission_id, sequence);
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS command_receipts (
                    client_id TEXT NOT NULL, command_key TEXT NOT NULL,
                    body TEXT NOT NULL, PRIMARY KEY(client_id, command_key));
                PRAGMA user_version=1;
            """)
            db.execute("INSERT OR IGNORE INTO sync_metadata (key,value) VALUES ('store_id',?)",
                       ("s-" + uuid.uuid4().hex,))

    @contextmanager
    def connection(self):
        if any((self.directory / name).exists() for name in
               ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3")):
            raise ContractError("RECOVERY_REVIEW_ONLY: use recovery-inspect; runtime access is blocked")
        db = sqlite3.connect(self.path, timeout=5)
        try:
            # Prepared recovery copies are historical evidence, never a runtime
            # store. Check on EVERY connection, also for an already-open Store.
            meta = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_metadata'").fetchone()
            if meta is not None:
                mode = db.execute("SELECT value FROM sync_metadata WHERE key='recovery_mode'").fetchone()
                if mode is not None:
                    raise ContractError("RECOVERY_REVIEW_ONLY: use recovery-inspect; runtime access is blocked")
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def check_id(identity):
        if not isinstance(identity, str) or not re.fullmatch(r"m-[0-9a-f]{32}", identity):
            raise ValueError("invalid mission id")

    @contextmanager
    def lock(self, identity):
        self.check_id(identity)
        with (self.directory / f"{identity}.lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Busy("mission already running/reconciling") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def create(self, request, configuration, *, intent=None):
        if not isinstance(request, str) or not request.strip() or len(request) > 8000:
            raise ValueError("request must contain 1–8000 characters")
        identity = "m-" + uuid.uuid4().hex
        mission = {"id": identity, "request": request, "configuration": configuration,
                   "created_at": now(), "status": "NEW", "phase": "RECALL",
                   "objective": define(request, intent, configuration),
                   "context": None, "model_output": None, "plan": None, "calls": [],
                   "progress": {"completed": 0, "total": None}, "result": None,
                   "error": None, "revision": 0, "cancel_requested": False}
        if intent is not None:
            mission["intent"] = json.loads(encode(intent))
        mission["outcome"] = assess(mission)
        with self.connection() as db:
            db.execute("INSERT INTO missions (id,revision,body) VALUES (?,0,?)",
                       (identity, encode(mission)))
            db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                       (identity, now(), "CREATED", encode({"configuration": configuration, "objective": mission["objective"]})))
        return mission

    def worker_lease_path(self, identity, call_id, attempt):
        self.check_id(identity)
        return self.directory / f"{identity}-{digest([call_id, attempt])}.worker.lock"

    @contextmanager
    def worker_quiescent(self, identity, call):
        # A PID can be reused. The child holds this lease from BEFORE its ready
        # handshake until AFTER execution. Reconciliation holds it until saved.
        if call.get("worker_protocol") not in {"lease-v1", "lease-v2"}:
            raise Busy("legacy call has no worker lease; abandon with unknown effect")
        path = self.worker_lease_path(identity, call["id"], call["attempt"])
        try:
            # Once SPAWNED is durable the child already created this inode.
            # Recreating it could hide a live orphan holding the removed inode.
            handle = path.open("r+" if call.get("worker") is not None else "a+")
        except FileNotFoundError as exc:
            raise Busy("worker lease missing after spawn; retain review or abandon") from exc
        with handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Busy("worker still active; reconciliation cannot enable a retry") from exc
            try:
                handle.seek(0)
                marker = handle.read(128)
                # v1 did not mark authorization; absence there proves nothing.
                authorized = None
                if call.get("worker_protocol") == "lease-v2":
                    if marker not in {"", "authorized\n"}:
                        raise ValueError("invalid worker authorization marker; review or abandon")
                    authorized = bool(marker)
                yield authorized
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def cancel_requested(self, identity):
        self.check_id(identity)
        with self.connection() as db:
            row = db.execute("SELECT cancel_requested FROM missions WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise KeyError("mission not found")
        return bool(row[0])

    def get(self, identity):
        self.check_id(identity)
        with self.connection() as db:
            row = db.execute("SELECT revision,cancel_requested,body FROM missions WHERE id=?",
                             (identity,)).fetchone()
        if row is None:
            raise KeyError("mission not found")
        data = json.loads(row[2])
        data.update(revision=row[0], cancel_requested=bool(row[1]))
        return data

    def save(self, mission, kind, detail=None, *, command=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision,cancel_requested FROM missions WHERE id=?",
                             (mission["id"],)).fetchone()
            if row is None or row[0] != mission["revision"]:
                raise Busy("stale mission revision")
            if kind == "ACTION_DECISION" and row[1]:
                raise ContractError("CANCEL_REQUESTED: decision cannot follow cancellation")
            if command is not None:
                self._check_command_store(db, command["store_id"])
                if (kind != "ACTION_DECISION" or command["mission_id"] != mission["id"]
                        or command["expected_revision"] != row[0]
                        or command["proposal_sha256"] != mission["proposal"]["sha256"]
                        or detail != mission["proposal"]["decisions"][-1]
                        or any(detail.get(k) != command[k] for k in
                               ("decision", "actor", "reason", "proposal_sha256"))):
                    raise ContractError("COMMAND_BINDING: receipt must match decision")
            mission["cancel_requested"] = bool(row[1])
            # Close cancellation/success race inside the same transaction.
            if row[1] and mission["status"] == "SUCCEEDED":
                mission.update(status="CANCELLED", result=None,
                               error={"code": "CANCELLED", "message": "cancellation requested before success commit"})
                kind = "CANCELLED"
            mission["outcome"] = assess(mission)
            if kind == "CALL_STARTED" and mission["objective"]["kind"] == "service_restart.simulated":
                from .approvals import consumed
                if not mission["calls"] or not consumed(mission, mission["calls"][-1]):
                    raise ValueError("simulated action launch requires its consumed approval in the same commit")
            if mission["status"] == "SUCCEEDED" and (
                mission["outcome"]["status"] != "ACHIEVED" or
                not mission["calls"] or any(c["status"] != "VERIFIED" for c in mission["calls"])
                or len(mission["calls"]) != len(mission["plan"]["steps"])
                or any(c.get("output_sha256") != digest(c.get("output")) for c in mission["calls"])
                or not mission["result"]
            ):
                raise ValueError("success requires all verified results and achieved mission criteria")
            mission["revision"] += 1
            db.execute("UPDATE missions SET revision=?,body=? WHERE id=?",
                       (mission["revision"], encode(mission), mission["id"]))
            event = {"status": mission["status"], "phase": mission["phase"],
                     "progress": mission["progress"], "outcome": mission["outcome"], **(detail or {})}
            recorded_at = now()
            inserted = db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                                  (mission["id"], recorded_at, kind, encode(event)))
            receipt = None
            if command is not None:
                if max(mission["revision"], inserted.lastrowid) > 2**53 - 1:
                    raise ContractError("COMMAND_BINDING: receipt exceeds JSON safe integer range")
                receipt = {"protocol": "eidolon-command-receipt/1", "status": "RECORDED",
                           "store_id": command["store_id"], "client_id": command["client_id"],
                           "command_key": command["command_key"], "mission_id": mission["id"],
                           "request_sha256": digest(command), "decision": command["decision"],
                           "proposal_sha256": command["proposal_sha256"],
                           "approval_status_at_recording": mission["proposal"]["status"],
                           "mission_revision": mission["revision"],
                           "event_sequence": inserted.lastrowid, "recorded_at": recorded_at,
                           "execution_evidence": False}
                event["receipt_sha256"] = digest(receipt)
                db.execute("UPDATE events SET detail=? WHERE sequence=?",
                           (encode(event), inserted.lastrowid))
                db.execute("INSERT INTO command_receipts (client_id,command_key,body) VALUES (?,?,?)",
                           (command["client_id"], command["command_key"], encode(receipt)))
        return receipt

    @staticmethod
    def _check_command_store(db, expected):
        row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
        if row is None or row[0] != expected:
            raise ContractError("STORE_CHANGED: resynchronize before any decision")

    def command_receipt(self, client_id, command_key, *, store_id):
        """One read transaction, no mission/runtime initialization or execution."""
        with self.connection() as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self._check_command_store(db, store_id)
            row = db.execute("SELECT body FROM command_receipts WHERE client_id=? AND command_key=?",
                             (client_id, command_key)).fetchone()
            return json.loads(row[0]) if row is not None else None

    def request_cancel(self, identity):
        self.check_id(identity)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body,cancel_requested FROM missions WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise KeyError("mission not found")
            if json.loads(row[0])["status"] not in TERMINAL and not row[1]:
                db.execute("UPDATE missions SET cancel_requested=1 WHERE id=?", (identity,))
                db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                           (identity, now(), "CANCEL_REQUESTED", "{}"))
        return self.get(identity)

    def record_cancellation(self, command):
        """Flag, audit event and command receipt share a single transaction.

        This does not take the execution lock, call run, kill a worker or
        reconcile an effect. Only CancelCommands supplies validated requests.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_command_store(db, command["store_id"])
            prior = db.execute("SELECT body FROM command_receipts WHERE client_id=? AND command_key=?",
                               (command["client_id"], command["command_key"])).fetchone()
            if prior is not None:
                receipt = json.loads(prior[0])
                if receipt["request_sha256"] != digest(command):
                    raise ContractError("COMMAND_KEY_REUSED: key already bound to another request")
                return receipt
            row = db.execute("SELECT revision,cancel_requested,body FROM missions WHERE id=?",
                             (command["mission_id"],)).fetchone()
            if row is None:
                raise KeyError("mission not found")
            status = json.loads(row[2])["status"]
            requested = bool(row[1])
            outcome = ("ALREADY_TERMINAL" if status in TERMINAL else
                       "ALREADY_REQUESTED" if requested else "REQUESTED")
            kind = "CANCEL_COMMAND_RECORDED"
            if outcome == "REQUESTED":
                db.execute("UPDATE missions SET cancel_requested=1 WHERE id=?", (command["mission_id"],))
                requested = True
                kind = "CANCEL_REQUESTED"
            recorded_at = now()
            detail = {"client_id": command["client_id"], "command_key": command["command_key"],
                      "actor": command["actor"], "reason": command["reason"], "cancel_outcome": outcome}
            event = db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                               (command["mission_id"], recorded_at, kind, encode(detail)))
            if not 0 <= row[0] <= 2**53 - 1 or not 1 <= event.lastrowid <= 2**53 - 1:
                raise ContractError("COMMAND_BINDING: receipt exceeds JSON safe integer range")
            receipt = {"protocol": "eidolon-cancel-receipt/1", "status": "RECORDED",
                       "store_id": command["store_id"], "client_id": command["client_id"],
                       "command_key": command["command_key"], "mission_id": command["mission_id"],
                       "request_sha256": digest(command), "cancel_outcome": outcome,
                       "mission_status_at_recording": status, "mission_revision": row[0],
                       "cancel_requested_at_recording": requested, "event_sequence": event.lastrowid,
                       "recorded_at": recorded_at, "execution_evidence": False,
                       "effect_absence_evidence": False}
            detail["receipt_sha256"] = digest(receipt)
            db.execute("UPDATE events SET detail=? WHERE sequence=?",
                       (encode(detail), event.lastrowid))
            db.execute("INSERT INTO command_receipts (client_id,command_key,body) VALUES (?,?,?)",
                       (command["client_id"], command["command_key"], encode(receipt)))
        return receipt

    def events(self, identity):
        self.get(identity)
        with self.connection() as db:
            rows = db.execute("SELECT sequence,at,kind,detail FROM events WHERE mission_id=? ORDER BY sequence",
                              (identity,)).fetchall()
        return [{"sequence": r[0], "at": r[1], "kind": r[2], "detail": json.loads(r[3])} for r in rows]
