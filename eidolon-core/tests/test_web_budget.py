"""Tests of isolated Web budget prototype; no Web or VM access."""
import tempfile
import unittest
from pathlib import Path
from eidolon_core.web_budget import WebBudget, BudgetError

class WebBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "web.sqlite3"
        self.key = b"k" * 32
        self.budget = WebBudget(self.path, self.key, daily_limit=2, clock=lambda:100000.0)

    def test_persistence_and_limit(self):
        self.assertEqual(self.budget.reserve("r1","alice","m1","web.search","q1"),"RESERVED")
        restarted = WebBudget(self.path,self.key,daily_limit=2,clock=lambda:100000.0)
        self.assertEqual(restarted.reserve("r1","alice","m1","web.search","q1"),"RESERVED")
        restarted.reserve("r2","alice","m1","web.search","q2")
        with self.assertRaises(BudgetError):
            restarted.reserve("r3","alice","m1","web.search","q3")

    def test_idempotence_and_collision(self):
        self.budget.reserve("r1","alice","m1","web.search","q1")
        with self.assertRaises(BudgetError):
            self.budget.reserve("r1","alice","m1","web.search","other")
        with self.assertRaises(BudgetError):
            self.budget.reserve("r1","bob","m1","web.search","q1")

    def test_uncertain_and_terminal(self):
        self.budget.reserve("r1","alice","m1","web.search","q1")
        self.assertEqual(self.budget.inspect("r1")["state"],"UNCERTAIN")
        self.budget.finish("r1","SUCCEEDED","receipt1")
        self.assertEqual(self.budget.inspect("r1"),{"state":"SUCCEEDED","receipt_ref":"receipt1"})
        self.budget.finish("r1","SUCCEEDED","receipt1")
        with self.assertRaises(BudgetError):
            self.budget.finish("r1","FAILED")

    def test_actor_isolation(self):
        self.budget.reserve("r1","alice","m1","web.search","q1")
        self.budget.reserve("r2","alice","m1","web.search","q2")
        self.budget.reserve("r3","bob","m1","web.search","q3")

    def test_invalid_inputs(self):
        with self.assertRaises(BudgetError):
            WebBudget(self.path,b"short")
        with self.assertRaises(BudgetError):
            self.budget.reserve("r1","alice","m1","web.search","")
        with self.assertRaises(BudgetError):
            self.budget.finish("unknown","SUCCEEDED")

    def test_invalid_clock_rejected_without_reservation(self):
        for invalid in (float("nan"), float("inf"), -1.0):
            budget = WebBudget(self.path, self.key, clock=lambda value=invalid: value)
            with self.assertRaises(BudgetError):
                budget.reserve("clockbad", "alice", "m1", "web.search", "q")
        self.assertIsNone(self.budget.inspect("clockbad"))

    def test_invalid_finish_clock_preserves_reservation(self):
        self.budget.reserve("finishbad", "alice", "m1", "web.search", "q")
        for invalid in (float("nan"), float("inf"), -1.0):
            budget = WebBudget(self.path, self.key, clock=lambda value=invalid: value)
            with self.assertRaises(BudgetError):
                budget.finish("finishbad", "SUCCEEDED", "receipt1")
            self.assertEqual(self.budget.inspect("finishbad")["state"], "UNCERTAIN")
        self.assertEqual(self.budget.finish("finishbad", "SUCCEEDED", "receipt1"), "SUCCEEDED")
