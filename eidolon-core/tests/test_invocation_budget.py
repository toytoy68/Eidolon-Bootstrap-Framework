# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_invocation_budget.py
# Description : Budget durable des appels et conservation des preuves aux limites
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Registry, default_registry
from tests.support import EmptyMemory, RecoverableModel, UnavailableMemory, lost_tool


def unavailable_verifier(parameters, context, output):
    raise OSError("synthetic verifier unavailable")


class InvocationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def runtime(self, limit=4, **options):
        return Runtime(self.store, limits=Limits(max_invocations=limit), **options)

    def reservations(self, identity):
        return [e["detail"] for e in self.store.events(identity) if e["kind"] == "INVOCATION_RESERVED"]

    def test_complete_mission_spends_four_and_terminal_read_spends_nothing(self):
        runtime = self.runtime()
        result = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["invocation_budget"], {"limit": 4, "used": 4})
        events = self.reservations(result["id"])
        self.assertEqual([e["ordinal"] for e in events], [1, 2, 3, 4])
        self.assertEqual([e["phase"] for e in events], ["RECALL", "PLAN", "EXECUTING", "VERIFY"])
        self.assertEqual(runtime.run(result["id"]), result)

    def test_tool_is_not_started_without_capacity_for_its_first_verifier(self):
        runtime = self.runtime(limit=3)
        result = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        self.assertEqual((result["status"], result["error"]["code"]), ("BLOCKED", "INVOCATION_BUDGET_EXHAUSTED"))
        self.assertEqual(result["invocation_budget"]["used"], 2)
        self.assertFalse(result["calls"])
        self.assertNotIn("CALL_STARTED", [e["kind"] for e in self.store.events(result["id"])])
        with patch("eidolon_core.runtime.invoke", side_effect=AssertionError("must not start")):
            self.assertEqual(runtime.run(result["id"])["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")

    def test_memory_failures_and_empty_recalls_count_across_restarts(self):
        for memory in (UnavailableMemory(), EmptyMemory()):
            with self.subTest(memory=type(memory).__name__):
                runtime = self.runtime(limit=2, memory=memory)
                identity = runtime.create(DEMO_REQUEST)["id"]
                runtime.run(identity)
                reopened = Runtime(Store(self.temp.name), memory=memory, limits=Limits(max_invocations=2))
                reopened.run(identity)
                with patch("eidolon_core.runtime.invoke", side_effect=AssertionError("budget exhausted")):
                    result = reopened.run(identity)
                self.assertEqual(result["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
                self.assertEqual(result["invocation_budget"]["used"], 2)
                self.assertEqual(len(self.reservations(identity)), 2)

    def test_model_failures_do_not_reset_budget_or_repeat_successful_recall(self):
        runtime = self.runtime(limit=3, model=RecoverableModel(mode="error"))
        identity = runtime.create(DEMO_REQUEST)["id"]
        runtime.run(identity); runtime.run(identity)
        result = runtime.run(identity)
        self.assertEqual(result["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
        self.assertEqual([e["phase"] for e in self.reservations(identity)], ["RECALL", "PLAN", "PLAN"])

    def test_crash_after_reservation_before_spawn_is_conservatively_charged(self):
        def crash(kind):
            if kind == "INVOCATION_RESERVED":
                raise SystemExit("synthetic crash before worker")
        runtime = self.runtime(limit=1, checkpoint=crash)
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch("eidolon_core.runtime.invoke", side_effect=AssertionError("worker not reached")):
            with self.assertRaises(SystemExit):
                runtime.run(identity)
        reopened = self.runtime(limit=1)
        result = reopened.run(identity)
        self.assertEqual(result["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
        self.assertEqual(result["invocation_budget"]["used"], 1)
        self.assertIsNone(result["context"])

    def test_reservation_and_counter_roll_back_together_if_audit_write_fails(self):
        runtime = self.runtime()
        identity = runtime.create(DEMO_REQUEST)["id"]
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON events WHEN NEW.kind='INVOCATION_RESERVED' BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with patch("eidolon_core.runtime.invoke", side_effect=AssertionError("uncommitted reservation")):
            result = runtime.run(identity)
        self.assertEqual(result["error"]["code"], "INTERNAL_ERROR")
        self.assertEqual(result["invocation_budget"]["used"], 0)
        self.assertEqual(self.reservations(identity), [])

    def test_no_effect_reconciliation_does_not_refund_the_attempt(self):
        tool = replace(default_registry().get("text.stats"), execute=lost_tool)
        runtime = self.runtime(limit=4, registry=Registry([tool]))
        identity = runtime.create(DEMO_REQUEST)["id"]
        first = runtime.run(identity)
        self.assertEqual(first["status"], "REVIEW_REQUIRED")
        self.assertEqual(first["invocation_budget"]["used"], 3)
        reconciled = runtime.reconcile(identity, decision="no-effect", actor="fixture", reason="synthetic child exited before effect", confirm_no_effect=True)
        self.assertEqual(reconciled["invocation_budget"]["used"], 3)
        self.assertEqual(reconciled["calls"][0]["attempt"], 2)
        result = runtime.run(identity)
        self.assertEqual(result["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
        self.assertEqual(len([e for e in self.store.events(identity) if e["kind"] == "CALL_STARTED"]), 1)

    def test_verifier_failure_keeps_returned_evidence_when_budget_runs_out(self):
        tool = replace(default_registry().get("text.stats"), verify=unavailable_verifier)
        runtime = self.runtime(limit=4, registry=Registry([tool]))
        identity = runtime.create(DEMO_REQUEST)["id"]
        first = runtime.run(identity)
        self.assertEqual(first["error"]["code"], "VERIFICATION_UNAVAILABLE")
        output = first["calls"][0]["output"]
        self.store.request_cancel(identity)
        second = runtime.run(identity)
        self.assertEqual((second["status"], second["phase"], second["error"]["code"]),
                         ("BLOCKED", "VERIFY", "INVOCATION_BUDGET_EXHAUSTED"))
        self.assertEqual(second["calls"][0]["output"], output)
        self.assertEqual(second["calls"][0]["status"], "RETURNED")
        abandoned = runtime.reconcile(identity, decision="abandon", actor="fixture", reason="close with unverified evidence")
        self.assertEqual(abandoned["status"], "ABANDONED")
        self.assertEqual(abandoned["invocation_budget"]["used"], 4)

    def test_action_condition_checks_are_charged_without_consuming_approval_at_exhaustion(self):
        runtime = ActionRuntime(self.store, limits=Limits(max_invocations=7))
        runtime.world.set_state("sim-nas", "DOWN")
        first = runtime.run(runtime.create_restart("nas")["id"])
        self.assertEqual(first["error"]["code"], "APPROVAL_REQUIRED")
        self.assertEqual(first["invocation_budget"]["used"], 4)
        runtime.decide(first["id"], expected_sha256=first["proposal"]["sha256"], decision="approve", actor="fixture", reason="synthetic")
        second = runtime.run(first["id"])
        self.assertEqual(second["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
        self.assertEqual(second["invocation_budget"]["used"], 6)
        self.assertEqual(second["proposal"]["status"], "APPROVED")
        self.assertIsNone(second["proposal"]["consumed_at"])
        self.assertEqual(second["calls"][0]["status"], "PREPARED")
        self.assertIsNone(runtime.world.receipt(first["id"]))

    def test_cannot_increase_or_disable_budget_on_existing_mission(self):
        runtime = self.runtime(limit=2)
        identity = runtime.create(DEMO_REQUEST)["id"]
        runtime.run(identity)
        for changed in (3, None):
            result = self.runtime(limit=changed).run(identity)
            self.assertEqual(result["error"]["code"], "CONFIGURATION_CHANGED")
            self.assertEqual(result["invocation_budget"], {"limit": 2, "used": 2})

    def test_counter_only_rollback_or_missing_budget_is_rejected(self):
        runtime = self.runtime(limit=2, memory=EmptyMemory())
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        m["invocation_budget"]["used"] = 0
        self.store.save(m, "SYNTHETIC_TAMPER")
        with patch("eidolon_core.runtime.invoke", side_effect=AssertionError("counter rollback")):
            result = runtime.run(identity)
        self.assertEqual(result["error"]["code"], "INVOCATION_BUDGET_INVALID")
        m = runtime.create(DEMO_REQUEST)
        del m["invocation_budget"]
        self.store.save(m, "SYNTHETIC_TAMPER")
        self.assertEqual(runtime.run(m["id"])["error"]["code"], "INVOCATION_BUDGET_INVALID")

    def test_legacy_mode_is_explicit_and_not_claimed_as_bounded(self):
        runtime = self.runtime(limit=None)
        m = runtime.create(DEMO_REQUEST)
        self.assertNotIn("max_invocations", m["configuration"])
        self.assertNotIn("invocation_budget", m)
        self.assertEqual(Runtime(self.store).run(m["id"])["error"]["code"], "CONFIGURATION_CHANGED")
        result = runtime.run(m["id"])
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(self.reservations(m["id"]), [])

    def test_limit_types_and_cli_preserve_frozen_configuration(self):
        for value in (True, False, 0, -1, 4097, 2.5, "4"):
            with self.assertRaises(ValueError):
                Limits(max_invocations=value)
        state = Path(self.temp.name) / "cli"
        result = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(state),
                                 "--max-invocations", "2", "demo"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["error"]["code"], "INVOCATION_BUDGET_EXHAUSTED")
        self.assertEqual(report["invocation_budget"], {"limit": 2, "used": 2})


if __name__ == "__main__":
    unittest.main()
