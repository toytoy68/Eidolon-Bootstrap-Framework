"""Durable Web budget reservation prototype. NOT an authorization engine."""
import hashlib
import hmac
import re
import sqlite3
import time

class BudgetError(ValueError):
    pass

class WebBudget:
    def __init__(self, path, secret, daily_limit=100, clock=time.time):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise BudgetError("secret too short")
        if type(daily_limit) is not int or not 1 <= daily_limit <= 100000:
            raise BudgetError("invalid limit")
        self.path, self.secret, self.limit, self.clock = str(path), secret, daily_limit, clock
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (request_id TEXT PRIMARY KEY, actor TEXT NOT NULL, mission TEXT NOT NULL, operation TEXT NOT NULL, query_ref TEXT NOT NULL, day INTEGER NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, finished REAL, receipt TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS calls_day_actor ON calls(day,actor)")

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _id(value):
        return type(value) is str and re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", value) is not None

    def reserve(self, request_id, actor, mission, operation, query, *, return_created=False):
        if (not all(self._id(v) for v in (request_id, actor, mission))
                or operation not in ("web.search", "web.fetch")
                or type(query) is not str or not 1 <= len(query) <= 2000):
            raise BudgetError("invalid reservation")
        ref = hmac.new(self.secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        now = float(self.clock())
        day = int(now // 86400)
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT actor,mission,operation,query_ref,state FROM calls WHERE request_id=?", (request_id,)).fetchone()
                if row:
                    if row[:4] != (actor,mission,operation,ref):
                        raise BudgetError("request id collision")
                    db.execute("COMMIT")
                    return (row[4], False) if return_created else row[4]
                used = db.execute("SELECT count(*) FROM calls WHERE actor=? AND day=?", (actor,day)).fetchone()[0]
                if used >= self.limit:
                    raise BudgetError("daily budget exhausted")
                db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?)", (request_id,actor,mission,operation,ref,day,"RESERVED",now,None,None))
                db.execute("COMMIT")
                return ("RESERVED", True) if return_created else "RESERVED"
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def finish(self, request_id, state, receipt_ref=None):
        if state not in ("SUCCEEDED","EMPTY","BLOCKED","FAILED") or not self._id(request_id):
            raise BudgetError("invalid completion")
        if receipt_ref is not None and not self._id(receipt_ref):
            raise BudgetError("invalid receipt")
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT state,receipt FROM calls WHERE request_id=?", (request_id,)).fetchone()
                if row is None:
                    raise BudgetError("unknown request")
                if row[0] != "RESERVED":
                    if row == (state,receipt_ref):
                        db.execute("COMMIT")
                        return state
                    raise BudgetError("terminal state immutable")
                db.execute("UPDATE calls SET state=?, finished=?, receipt=? WHERE request_id=?", (state,float(self.clock()),receipt_ref,request_id))
                db.execute("COMMIT")
                return state
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def inspect(self, request_id):
        if not self._id(request_id):
            raise BudgetError("invalid request id")
        with self._db() as db:
            row = db.execute("SELECT state,receipt FROM calls WHERE request_id=?", (request_id,)).fetchone()
        return None if row is None else {"state":"UNCERTAIN" if row[0]=="RESERVED" else row[0], "receipt_ref":row[1]}
