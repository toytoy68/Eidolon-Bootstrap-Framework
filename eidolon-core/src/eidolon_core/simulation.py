# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : simulation.py
# Description : Services fictifs transactionnels pour les essais d'action
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Local synthetic state only. No network, shell or real service controls."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .contracts import ContractError, digest, encode
from .diagnostics import FIXTURES
from .tools import Tool

RESTART_TOOL = "service.restart.simulated"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SimulatedServices:
    path: str
    world_id: str

    @classmethod
    def initialize(cls, path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as connection, connection as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS services (id TEXT PRIMARY KEY, state TEXT NOT NULL, revision INTEGER NOT NULL, restarts INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS receipts (operation_id TEXT PRIMARY KEY, parameters_sha256 TEXT NOT NULL, body TEXT NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO identity VALUES (1, ?)", (str(uuid.uuid4()),))
            world_id = db.execute("SELECT id FROM identity WHERE singleton=1").fetchone()[0]
            for identity, state in FIXTURES:
                db.execute("INSERT OR IGNORE INTO services VALUES (?, ?, 1, 0)", (identity, state))
        return cls(str(path), world_id)

    @contextmanager
    def connection(self):
        # mode=rw prevents silently replacing a missing world with an empty database.
        db = sqlite3.connect(Path(self.path).as_uri() + "?mode=rw", uri=True, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                if db.execute("SELECT id FROM identity WHERE singleton=1").fetchone() != (self.world_id,):
                    raise ContractError("simulation identity changed")
                yield db
        finally:
            db.close()

    def manifest(self):
        return {"provider": "sqlite-synthetic-services/1", "path": self.path, "world_id": self.world_id}

    @staticmethod
    def check_target(target):
        if not isinstance(target, str) or target not in dict(FIXTURES):
            raise ContractError("unknown synthetic target")

    def observe(self, target):
        self.check_target(target)
        with self.connection() as db:
            row = db.execute("SELECT state,revision,restarts FROM services WHERE id=?", (target,)).fetchone()
        if row is None:
            raise ContractError("synthetic target missing")
        return {"target_id": target, "state": row[0], "revision": row[1], "restarts": row[2],
                "world_id": self.world_id, "observed_at": timestamp(), "synthetic": True}

    def verify_observation(self, target, value):
        if not isinstance(value, dict) or set(value) != {
                "target_id", "state", "revision", "restarts", "world_id", "observed_at", "synthetic"}:
            return False
        try:
            observed = datetime.fromisoformat(value["observed_at"])
            age = (datetime.now(timezone.utc) - observed).total_seconds()
        except (TypeError, ValueError):
            return False
        if not (0 <= age <= 60 and value["synthetic"] is True
                and type(value["revision"]) is int and type(value["restarts"]) is int):
            return False
        current = self.observe(target)
        return all(value[k] == current[k] for k in current if k != "observed_at")

    def set_state(self, target, state):
        """Explicit fixture control for demonstrations, never a real service action."""
        self.check_target(target)
        if state not in {"UP", "DOWN", "UNREACHABLE"}:
            raise ContractError("invalid synthetic state")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE services SET state=?,revision=revision+1 WHERE id=?", (state, target))
        return self.observe(target)

    def validate(self, parameters, context):
        if not isinstance(parameters, dict) or set(parameters) != {
                "target", "expected_revision", "world_id", "operation_id"}:
            raise ContractError("restart needs exact synthetic target, revision, world and operation")
        self.check_target(parameters["target"])
        if (type(parameters["expected_revision"]) is not int or parameters["expected_revision"] < 1
                or parameters["world_id"] != self.world_id
                or not isinstance(parameters["operation_id"], str)
                or not re.fullmatch(r"m-[0-9a-f]{32}", parameters["operation_id"])):
            raise ContractError("invalid synthetic restart parameters")

    def restart(self, parameters, context):
        self.validate(parameters, context)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM receipts WHERE operation_id=?", (parameters["operation_id"],)).fetchone():
                raise ContractError("operation already has a receipt; reconcile, never restart again")
            row = db.execute("SELECT state,revision FROM services WHERE id=?", (parameters["target"],)).fetchone()
            if row != ("DOWN", parameters["expected_revision"]):
                raise ContractError("PRECONDITION_CHANGED: synthetic service must still be DOWN at the approved revision")
            result = {"target_id": parameters["target"], "operation_id": parameters["operation_id"],
                      "world_id": self.world_id, "before": {"state": row[0], "revision": row[1]},
                      "after": {"state": "UP", "revision": row[1] + 1},
                      "performed_at": timestamp(), "synthetic": True, "source": "sqlite-synthetic-services/1"}
            db.execute("UPDATE services SET state='UP',revision=revision+1,restarts=restarts+1 WHERE id=?",
                       (parameters["target"],))
            db.execute("INSERT INTO receipts VALUES (?, ?, ?)",
                       (parameters["operation_id"], digest(parameters), encode(result)))
        return result

    def receipt(self, operation_id):
        with self.connection() as db:
            row = db.execute("SELECT parameters_sha256,body FROM receipts WHERE operation_id=?", (operation_id,)).fetchone()
        return None if row is None else {"parameters_sha256": row[0], "result": json.loads(row[1])}

    def verify(self, parameters, context, output):
        self.validate(parameters, context)
        receipt = self.receipt(parameters["operation_id"])
        return (receipt is not None and receipt["parameters_sha256"] == digest(parameters)
                and digest(receipt["result"]) == digest(output)
                and output["before"] == {"state": "DOWN", "revision": parameters["expected_revision"]}
                and output["after"] == {"state": "UP", "revision": parameters["expected_revision"] + 1}
                and output["target_id"] == parameters["target"] and output["world_id"] == self.world_id
                and output["operation_id"] == parameters["operation_id"] and output["synthetic"] is True)

    def tool(self):
        return Tool(RESTART_TOOL, "sqlite-synthetic-restart/1", "mutation", self.validate,
                    self.restart, self.verify, "sqlite-synthetic-receipt/1")
