# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_guard.py
# Description : Garde durable contre la reprise aveugle d'une recherche interrompue
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Optional POSIX/local-filesystem guard around one complete research run.

One journal serializes all its runs. An unfinished intent blocks until explicit
review; no timeout, lease expiry, retry, network operation or pause release.
This is a conservative run-level guard, not G030's per-hop call journal.
"""
from contextlib import contextmanager
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
import uuid

from .contracts import ContractError, digest, encode, snapshot
from .presentation import header, message

PROTOCOL = "eidolon-research-guard/1"
MAX_RUNS = 256
MAX_INTEGER = 2**53 - 1
OUTCOMES = {"READ_TARGET_MET", "PARTIAL", "NO_READABLE_SOURCE", "CANCELLED",
            "DEADLINE", "QUERY_EMPTY_AFTER_CLEANUP"}


class GuardError(ContractError):
    """No fallback to an unguarded research operation is permitted."""


def _match(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _descriptor(value):
    base = {"query_sha256", "policy_id", "providers"}
    if (type(value) is not dict or not base <= set(value)
            or not set(value) <= base | {"query_history_sha256", "operation_id"}
            or not _match(r"[0-9a-f]{64}", value["query_sha256"])
            or not _match(r"[A-Za-z0-9._/-]{1,100}", value["policy_id"])
            or type(value["providers"]) is not list or not 1 <= len(value["providers"]) <= 8
            or any(not _match(r"[A-Za-z0-9._/-]{1,100}", p) for p in value["providers"])
            or len(set(value["providers"])) != len(value["providers"])):
        raise GuardError("INVALID_RESEARCH_DESCRIPTOR")
    if "query_history_sha256" in value and not _match(r"[0-9a-f]{64}", value["query_history_sha256"]):
        raise GuardError("INVALID_RESEARCH_DESCRIPTOR")
    if "operation_id" in value and not _match(r"m-[0-9a-f]{32}", value["operation_id"]):
        raise GuardError("INVALID_RESEARCH_DESCRIPTOR")
    return snapshot(value)


def _label(value, limit):
    if (type(value) is not str or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise GuardError("INVALID_RESEARCH_REVIEW")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise GuardError("INVALID_RESEARCH_REVIEW") from exc


def _json(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate")
            result[k] = v
        return result
    if type(raw) is not str or len(raw) > 16000:
        raise GuardError("INVALID_RESEARCH_RECORD")
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, RecursionError) as exc:
        raise GuardError("INVALID_RESEARCH_RECORD") from exc


class ResearchGuard:
    def __init__(self, directory, *, clock=time.time, create=True, retain_queries=False):
        if not callable(clock):
            raise GuardError("INVALID_RESEARCH_CLOCK")
        self.directory = Path(directory).resolve()
        if type(create) is not bool or type(retain_queries) is not bool:
            raise GuardError("INVALID_RESEARCH_GUARD_MODE")
        if create:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        elif not self.directory.is_dir():
            raise GuardError("RESEARCH_GUARD_NOT_FOUND")
        self.path = self.directory / "research-runs.sqlite3"
        self.lock_path = self.directory / "research-runs.lock"
        self.clock = clock
        with self._exclusive(create=create and not self.path.exists()):
            if create:
                try:
                    fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(fd)
            with self._connection(initializing=True) as db:
                db.execute("BEGIN IMMEDIATE")
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if not tables and version == 0 and create:
                    db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
                    db.execute("CREATE TABLE run_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL)")
                    db.execute("INSERT INTO metadata VALUES ('guard_id', ?)", ("g-" + uuid.uuid4().hex,))
                    db.execute("PRAGMA user_version=1")
                elif ((version == 1 and tables != {"metadata", "runs", "run_events"})
                      or (version == 2 and tables != {"metadata", "runs", "run_events", "cleaned_queries"})
                      or version not in (1, 2)):
                    raise GuardError("UNSUPPORTED_RESEARCH_GUARD")
                if retain_queries and version != 2:
                    if not create:
                        raise GuardError("QUERY_HISTORY_NOT_ENABLED")
                    db.execute("CREATE TABLE cleaned_queries (run_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
                    db.execute("PRAGMA user_version=2")
                    version = 2
                self.retain_queries = version == 2
                self.guard_id = self._identity(db)
                self._records(db)

    @contextmanager
    def _exclusive(self, *, create=False):
        fd = None
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(self.lock_path, flags | (os.O_CREAT if create else 0), 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise GuardError("RESEARCH_LOCK_NOT_PRIVATE")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GuardError("WEB_RESEARCH_IN_FLIGHT") from exc
            yield
        except OSError as exc:
            raise GuardError("RESEARCH_GUARD_UNAVAILABLE") from exc
        finally:
            if fd is not None:
                os.close(fd)  # close releases this file-description's flock

    def _identity(self, db):
        rows = db.execute("SELECT key,value FROM metadata").fetchall()
        if len(rows) != 1 or rows[0][0] != "guard_id" or not _match(r"g-[0-9a-f]{32}", rows[0][1]):
            raise GuardError("INVALID_RESEARCH_IDENTITY")
        return rows[0][1]

    @contextmanager
    def _connection(self, *, initializing=False):
        db = None
        try:
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise GuardError("RESEARCH_DATABASE_NOT_PRIVATE")
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
            db.execute("PRAGMA synchronous=FULL")
            if not initializing:
                if db.execute("PRAGMA user_version").fetchone()[0] != (2 if self.retain_queries else 1):
                    raise GuardError("UNSUPPORTED_RESEARCH_GUARD")
                if self._identity(db) != self.guard_id:
                    raise GuardError("RESEARCH_GUARD_CHANGED")
            with db:
                yield db
        except (sqlite3.Error, OSError) as exc:
            raise GuardError("RESEARCH_GUARD_UNAVAILABLE") from exc
        finally:
            if db is not None:
                db.close()

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= MAX_INTEGER / 1000:
            raise GuardError("INVALID_RESEARCH_CLOCK")
        return math.floor(value * 1000)

    def _decode(self, identity, raw):
        try:
            r = _json(raw)
            keys = {"id", "guard_id", "descriptor", "state", "revision", "started_at_ms", "ended_at_ms", "outcome", "report_sha256", "review"}
            if (type(r) is not dict or set(r) != keys or r["id"] != identity
                    or not _match(r"r-[0-9a-f]{32}", identity) or r["guard_id"] != self.guard_id
                    or type(r["state"]) is not str or r["state"] not in {"INTENT", "COMPLETED", "RESOLVED_UNKNOWN"}
                    or type(r["revision"]) is not int or r["revision"] != (1 if r["state"] == "INTENT" else 2)
                    or type(r["started_at_ms"]) is not int or not 0 <= r["started_at_ms"] <= MAX_INTEGER):
                raise ValueError("record")
            _descriptor(r["descriptor"])
            if r["state"] == "INTENT":
                if any(r[k] is not None for k in ("ended_at_ms", "outcome", "report_sha256", "review")):
                    raise ValueError("intent")
            else:
                if type(r["ended_at_ms"]) is not int or not r["started_at_ms"] <= r["ended_at_ms"] <= MAX_INTEGER:
                    raise ValueError("time")
                if r["state"] == "COMPLETED":
                    if (type(r["outcome"]) is not str or r["outcome"] not in OUTCOMES
                            or not _match(r"[0-9a-f]{64}", r["report_sha256"]) or r["review"] is not None):
                        raise ValueError("completed")
                else:
                    review = r["review"]
                    if r["outcome"] is not None or r["report_sha256"] is not None or type(review) is not dict or set(review) != {"actor", "reason"}:
                        raise ValueError("review")
                    _label(review["actor"], 200); _label(review["reason"], 1000)
            return r
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise GuardError("INVALID_RESEARCH_RECORD") from exc

    def _records(self, db):
        records = []
        for identity, raw in db.execute("SELECT id,substr(body,1,16001) FROM runs ORDER BY id LIMIT ?", (MAX_RUNS + 1,)):
            if len(records) >= MAX_RUNS:
                raise GuardError("RESEARCH_HISTORY_OVER_CAPACITY")
            record = self._decode(identity, raw)
            events = db.execute("SELECT kind,substr(body,1,16001) FROM run_events WHERE run_id=? ORDER BY sequence LIMIT 3", (identity,)).fetchall()
            if (len(events) != record["revision"] or events[0][0] != "INTENT"
                    or events[-1] != (record["state"], raw)):
                raise GuardError("INVALID_RESEARCH_AUDIT")
            initial = self._decode(identity, events[0][1])
            if initial["state"] != "INTENT" or any(initial[k] != record[k] for k in ("guard_id", "descriptor", "started_at_ms")):
                raise GuardError("INVALID_RESEARCH_AUDIT")
            records.append(record)
        if db.execute("SELECT count(*) FROM run_events").fetchone()[0] != sum(r["revision"] for r in records):
            raise GuardError("INVALID_RESEARCH_AUDIT")
        if sum(r["state"] == "INTENT" for r in records) > 1:
            raise GuardError("INVALID_RESEARCH_AUDIT")
        from .query_history import verify_rows
        verify_rows(db, records, enabled=self.retain_queries)
        return records

    def _write(self, db, record, *, insert=False):
        raw = encode(record)
        if insert:
            db.execute("INSERT INTO runs VALUES (?,?)", (record["id"], raw))
        else:
            db.execute("UPDATE runs SET body=? WHERE id=?", (raw, record["id"]))
        db.execute("INSERT INTO run_events (run_id,kind,body) VALUES (?,?,?)", (record["id"], record["state"], raw))

    def execute(self, callback, *, descriptor, cleaned_query=None):
        """Commit intent, run trusted callback once, then record its completed report."""
        descriptor = _descriptor(descriptor)
        from .query_history import payload_for
        payload = None
        if self.retain_queries:
            payload = payload_for(cleaned_query)
            if descriptor["query_sha256"] != payload["cleanup"]["cleaned_sha256"]:
                raise GuardError("QUERY_HISTORY_BINDING_MISMATCH")
            descriptor["query_history_sha256"] = digest(payload)
        elif cleaned_query is not None or "query_history_sha256" in descriptor:
            raise GuardError("QUERY_HISTORY_NOT_ENABLED")
        if not callable(callback):
            raise GuardError("INVALID_RESEARCH_CALLBACK")
        with self._exclusive():
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                records = self._records(db)
                if any(r["state"] == "INTENT" for r in records):
                    raise GuardError("WEB_RESEARCH_UNCERTAIN")
                if len(records) >= MAX_RUNS:
                    raise GuardError("RESEARCH_HISTORY_CAPACITY_REACHED")
                record = {"id": "r-" + uuid.uuid4().hex, "guard_id": self.guard_id,
                          "descriptor": descriptor, "state": "INTENT", "revision": 1,
                          "started_at_ms": self._now(), "ended_at_ms": None,
                          "outcome": None, "report_sha256": None, "review": None}
                self._write(db, record, insert=True)
                if payload is not None:
                    db.execute("INSERT INTO cleaned_queries VALUES (?,?)", (record["id"], encode(payload)))
            # Any exception, process exit or finish failure leaves INTENT durable.
            # No finally block closes it or treats missing evidence as no contact.
            result = snapshot(callback())
            if type(result) is not dict or type(result.get("status")) is not str or result["status"] not in OUTCOMES:
                raise GuardError("INVALID_RESEARCH_RESULT")
            stamp = self._now()
            if stamp < record["started_at_ms"]:
                raise GuardError("RESEARCH_CLOCK_REGRESSION")
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                records = self._records(db)
                if record not in records:
                    raise GuardError("RESEARCH_INTENT_CHANGED")
                record.update(state="COMPLETED", revision=2, ended_at_ms=stamp,
                              outcome=result["status"], report_sha256=digest(result))
                self._write(db, record)
            result["research_guard"] = {"protocol": PROTOCOL, "guard_id": self.guard_id,
                                        "run_id": record["id"], "state": "COMPLETED"}
            return result

    def inspect(self):
        # A sampled liveness hint only. resolve() always acquires the lock again.
        live = False
        try:
            with self._exclusive():
                pass
        except GuardError as exc:
            if str(exc) != "WEB_RESEARCH_IN_FLIGHT":
                raise
            live = True
        with self._connection() as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            records = self._records(db)
        for record in records:
            record["observed_state"] = ("IN_FLIGHT" if live else "UNCERTAIN") if record["state"] == "INTENT" else record["state"]
        return {"protocol": PROTOCOL, "guard_id": self.guard_id, "runs": records,
                "liveness_sampled": True, "automatic_release": False, "request_sent": False}

    def resolve(self, identity, *, expected_revision, actor, reason):
        if not _match(r"r-[0-9a-f]{32}", identity) or type(expected_revision) is not int or expected_revision != 1:
            raise GuardError("INVALID_RESEARCH_REVIEW")
        _label(actor, 200); _label(reason, 1000)
        with self._exclusive():
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                record = next((r for r in self._records(db) if r["id"] == identity), None)
                if record is None:
                    raise GuardError("RESEARCH_RUN_NOT_FOUND")
                if record["revision"] != expected_revision:
                    raise GuardError("STALE_RESEARCH_RUN")
                if record["state"] != "INTENT":
                    raise GuardError("RESEARCH_RUN_NOT_UNCERTAIN")
                stamp = self._now()
                if stamp < record["started_at_ms"]:
                    raise GuardError("RESEARCH_CLOCK_REGRESSION")
                record.update(state="RESOLVED_UNKNOWN", revision=2, ended_at_ms=stamp,
                              review={"actor": actor, "reason": reason})
                self._write(db, record)
        return {"protocol": PROTOCOL, "run_id": identity, "state": "RESOLVED_UNKNOWN",
                "revision": 2, "request_sent": False, "authorizes_execution": False,
                "effect_known": False}


def main(argv=None):
    from .query_history import QueryHistoryError
    parser = argparse.ArgumentParser(description="Inspecter/revoir une recherche interrompue, sans relance.")
    parser.add_argument("--directory", required=True)
    parser.add_argument("--format", choices=("json", "human"), default="json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("run_id")
    resolve.add_argument("--revision", type=int, required=True)
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        guard = ResearchGuard(args.directory, create=False)
        result = (guard.inspect() if args.command == "inspect" else
                  guard.resolve(args.run_id, expected_revision=args.revision, actor=args.actor, reason=args.reason))
    except (GuardError, QueryHistoryError, OSError) as error:
        # Do not echo paths, arguments or a SQLite exception in diagnostics.
        code = str(error) if isinstance(error, (GuardError, QueryHistoryError)) else "RESEARCH_GUARD_UNAVAILABLE"
        print(json.dumps({"protocol": PROTOCOL, "error": code, "request_sent": False}), file=sys.stderr)
        return 2
    if args.format == "json":
        print(encode(result))
    else:
        print(header(title="Recherche — revue locale"))
        if args.command == "inspect":
            for run in result["runs"]:
                print(message("INFO", f"{run['id']} : {run['observed_state']} ; révision {run['revision']}"))
            print(message("INFO", "Lecture seule ; aucun appel ni levée automatique."))
        else:
            print(message("ATTENTION", "Incertitude acceptée et enregistrée ; aucun appel relancé, effet toujours inconnu."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
