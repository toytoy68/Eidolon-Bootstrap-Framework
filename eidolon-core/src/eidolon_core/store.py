"""SQLite snapshots and audit events committed together; POSIX execution locks."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .contracts import encode

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


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
                PRAGMA user_version=1;
            """)

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

    def create(self, request, configuration):
        if not isinstance(request, str) or not request.strip() or len(request) > 8000:
            raise ValueError("request must contain 1–8000 characters")
        identity = "m-" + uuid.uuid4().hex
        mission = {"id": identity, "request": request, "configuration": configuration,
                   "created_at": now(), "status": "NEW", "phase": "RECALL",
                   "context": None, "model_output": None, "plan": None, "calls": [],
                   "progress": {"completed": 0, "total": None}, "result": None,
                   "error": None, "revision": 0, "cancel_requested": False}
        with self.connection() as db:
            db.execute("INSERT INTO missions (id,revision,body) VALUES (?,0,?)",
                       (identity, encode(mission)))
            db.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                       (identity, now(), "CREATED", encode({"configuration": configuration})))
        return mission

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
                mission.update(status="CANCELLED", result=None)
                kind = "CANCELLED"
            if mission["status"] == "SUCCEEDED" and (
                not mission["calls"] or any(c["status"] != "VERIFIED" for c in mission["calls"])
                or len(mission["calls"]) != len(mission["plan"]["steps"])
                or not mission["result"]
            ):
                raise ValueError("success requires all verified results")
            mission["revision"] += 1
            db.execute("UPDATE missions SET revision=?,body=? WHERE id=?",
                       (mission["revision"], encode(mission), mission["id"]))
            event = {"status": mission["status"], "phase": mission["phase"],
                     "progress": mission["progress"], **(detail or {})}
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
