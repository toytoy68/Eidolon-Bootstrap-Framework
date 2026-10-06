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

from .contracts import digest, encode
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
                PRAGMA user_version=1;
            """)
            db.execute("INSERT OR IGNORE INTO sync_metadata (key,value) VALUES ('store_id',?)",
                       ("s-" + uuid.uuid4().hex,))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        try:
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

    def save(self, mission, kind, detail=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision,cancel_requested FROM missions WHERE id=?",
                             (mission["id"],)).fetchone()
            if row is None or row[0] != mission["revision"]:
                raise Busy("stale mission revision")
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
            db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                       (mission["id"], now(), kind, encode(event)))

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

    def events(self, identity):
        self.get(identity)
        with self.connection() as db:
            rows = db.execute("SELECT sequence,at,kind,detail FROM events WHERE mission_id=? ORDER BY sequence",
                              (identity,)).fetchall()
        return [{"sequence": r[0], "at": r[1], "kind": r[2], "detail": json.loads(r[3])} for r in rows]
