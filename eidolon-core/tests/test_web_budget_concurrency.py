"""Extra isolated regression tests for the durable Web ledger."""
import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from eidolon_core.web_budget import BudgetError, WebBudget


class WebBudgetConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "budget.sqlite3"
        self.key = b"t" * 32

    def ledger(self, limit=3):
        return WebBudget(self.db, self.key, daily_limit=limit, clock=lambda: 100000.0)

    def test_parallel_reservations_never_exceed_limit(self):
        self.ledger()
        def attempt(i):
            try:
                self.ledger().reserve(f"req{i}", "alice", "m1", "web.search", f"query{i}")
                return True
            except BudgetError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(attempt, range(20)))
        self.assertEqual(sum(results), 3)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM calls").fetchone()[0], 3)

    def test_duplicate_request_does_not_consume_another_slot(self):
        b = self.ledger(limit=2)
        for _ in range(4):
            self.assertEqual(b.reserve("req1", "alice", "m1", "web.search", "same"), "RESERVED")
        self.assertEqual(b.reserve("req2", "alice", "m1", "web.search", "other"), "RESERVED")
        with self.assertRaises(BudgetError):
            b.reserve("req3", "alice", "m1", "web.search", "third")

    def test_database_does_not_store_plain_query(self):
        query = "very-private-example-search"
        self.ledger().reserve("req1", "alice", "m1", "web.search", query)
        with sqlite3.connect(self.db) as db:
            rows = db.execute("SELECT query_ref FROM calls").fetchall()
        self.assertNotIn(query, str(rows))

    def test_atomic_created_flag_prevents_replay(self):
        b = self.ledger()
        first = b.reserve("req1", "alice", "m1", "web.search", "q", return_created=True)
        second = b.reserve("req1", "alice", "m1", "web.search", "q", return_created=True)
        self.assertEqual(first, ("RESERVED", True))
        self.assertEqual(second, ("RESERVED", False))
        self.assertEqual(b.inspect("req1")["state"], "UNCERTAIN")
