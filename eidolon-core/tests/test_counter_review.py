# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_counter_review.py
# Description : Régressions de la contre-revue C-REV-002
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic effects, real process death; no network or personal corpus."""
from dataclasses import replace
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, digest, parse_plan
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.tools import Registry, default_registry, text_stats
from eidolon_core.worker import _child, attempt_receipt_path
from tests.support import FixedModel, marker_tool, plan, recoverable_tool


class CounterReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory)

    def registry(self, function):
        return Registry([replace(default_registry().get("text.stats"), execute=function)])

    def count(self, identity):
        return sum(e["kind"] == "CALL_STARTED" for e in self.store.events(identity))

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("test synchronization timed out")

    def crash(self, boundary):
        runtime = Runtime(self.store)
        identity = runtime.create(DEMO_REQUEST)["id"]
        child = subprocess.run([sys.executable, "-m", "tests.crash_driver", str(self.directory), identity, boundary],
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 77, child.stderr)
        return runtime, identity

    def test_n01_error_receipt_retry_keeps_history(self):
        recovered = self.directory / "recovered"
        runtime = Runtime(self.store, registry=self.registry(recoverable_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch.dict(os.environ, {"EIDOLON_TEST_RECOVERED": str(recovered)}):
            m = runtime.run(identity)
            self.assertEqual((m["status"], m["error"]["code"]), ("REVIEW_REQUIRED", "CALL_ERROR"))
            receipt = m["calls"][0]["error_receipt"]
            self.assertFalse(receipt["ok"])
            self.assertNotIn("late_receipt", m["calls"][0])
            self.assertEqual(runtime.run(identity), m)
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="absence of effect checked")
            prepared = self.store.get(identity)["calls"][0]
            self.assertEqual(prepared["attempt"], 2)
            self.assertNotIn("error_receipt", prepared)
            self.assertEqual(prepared["attempt_history"][0]["error_receipt"], receipt)
            recovered.touch()
            final = runtime.run(identity)
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(self.count(identity), 2)
        self.assertEqual(final["calls"][0]["attempt_history"][0]["error_receipt_sha256"], digest(receipt))

    def test_n01_legacy_error_receipt_can_be_reconciled(self):
        runtime = Runtime(self.store, registry=self.registry(recoverable_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch.dict(os.environ, {"EIDOLON_TEST_RECOVERED": str(self.directory / "absent")}):
            m = runtime.run(identity)
        call = m["calls"][0]
        call["worker_protocol"] = "lease-v1"
        call["late_receipt"] = call.pop("error_receipt")
        call["late_receipt_sha256"] = call.pop("error_receipt_sha256")
        self.store.save(m, "LEGACY_ERROR_FIXTURE")
        revised = runtime.reconcile(identity, decision="no-effect", actor="tester", reason="error inspected")
        self.assertEqual(revised["calls"][0]["attempt"], 2)
        self.assertFalse(revised["calls"][0]["attempt_history"][0]["late_receipt"]["ok"])

    def test_n02_finished_orphan_cannot_duplicate_effect(self):
        runtime = Runtime(self.store, registry=self.registry(marker_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        driver = subprocess.Popen([sys.executable, "-m", "tests.review_driver", str(self.directory), identity],
                                  env={**os.environ, "EIDOLON_TEST_MARKER": str(self.directory)},
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.wait_for(lambda: (self.directory / "entered").exists())
            driver.kill()
            driver.wait(timeout=5)
            m = runtime.run(identity)
            with self.assertRaises(Busy):
                runtime.reconcile(identity, decision="no-effect", actor="tester", reason="worker alive")
            (self.directory / "release").touch()
            def finished():
                if not (self.directory / "effect").exists():
                    return False
                try:
                    with self.store.worker_quiescent(identity, m["calls"][0]):
                        return True
                except Busy:
                    return False
            self.wait_for(finished)
            for confirmation in (False, True):
                with self.assertRaisesRegex(ValueError, "successful receipt"):
                    runtime.reconcile(identity, decision="no-effect", actor="tester", reason="cannot erase receipt",
                                      confirm_no_effect=confirmation)
            self.assertEqual(self.store.get(identity)["status"], "REVIEW_REQUIRED")
            runtime.reconcile(identity, decision="use-receipt", actor="tester", reason="inspect orphan receipt")
            final = runtime.run(identity)
            self.assertEqual(final["status"], "SUCCEEDED")
            self.assertEqual(final["result"]["evidence"][0]["receipt_origin"], "worker_receipt_reconciliation")
            self.assertEqual(self.count(identity), 1)
            self.assertEqual(len((self.directory / "effect").read_text().splitlines()), 1)
        finally:
            (self.directory / "release").touch()
            if driver.poll() is None:
                driver.kill()
            driver.wait(timeout=5)

    def test_n02_authorized_without_receipt_needs_confirmation(self):
        runtime, identity = self.crash("CALL_STARTED")
        m = runtime.run(identity)
        call = m["calls"][0]
        lease = self.store.worker_lease_path(identity, call["id"], call["attempt"])
        lease.write_text("authorized\n")  # Crash after permission, before receipt.
        with self.assertRaisesRegex(ValueError, "confirm_no_effect"):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="unknown")
        result = runtime.reconcile(identity, decision="no-effect", actor="tester",
                                   reason="independent investigation confirms no effect", confirm_no_effect=True)
        self.assertEqual(result["calls"][0]["attempt"], 2)
        self.assertTrue(self.store.events(identity)[-1]["detail"]["confirmed_no_effect"])

    def test_n02_invalid_marker_or_receipt_does_not_enable_retry(self):
        runtime, identity = self.crash("CALL_STARTED")
        call = runtime.run(identity)["calls"][0]
        lease = self.store.worker_lease_path(identity, call["id"], call["attempt"])
        lease.write_text("auth")
        with self.assertRaisesRegex(ValueError, "marker"):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="partial marker", confirm_no_effect=True)
        lease.write_text("authorized\n")
        attempt_receipt_path(lease).write_text('{"ok":')
        with self.assertRaises(ContractError):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="bad receipt", confirm_no_effect=True)
        self.assertEqual(self.store.get(identity)["calls"][0]["attempt"], 1)
        self.assertEqual(runtime.reconcile(identity, decision="abandon", actor="tester", reason="unresolved")["status"], "ABANDONED")

    def test_n03_cancel_before_permission_has_no_unknown_effect(self):
        def cancel(kind):
            if kind == "WORKER_SPAWNED":
                self.store.request_cancel(identity)
        runtime = Runtime(self.store, registry=self.registry(marker_tool), checkpoint=cancel)
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch.dict(os.environ, {"EIDOLON_TEST_MARKER": str(self.directory)}):
            m = runtime.run(identity)
        self.assertEqual(m["status"], "CANCELLED")
        self.assertFalse((self.directory / "entered").exists())
        self.assertEqual(m["calls"][0]["attempt_history"][0]["reconciliation"]["decision"], "not-authorized")
        self.assertEqual(runtime.run(identity), m)

    def test_spawn_record_failure_cannot_authorize_provider(self):
        runtime = Runtime(self.store, registry=self.registry(marker_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        save = self.store.save
        def fail(m, kind, detail=None):
            if kind == "WORKER_SPAWNED":
                raise OSError("synthetic journal outage")
            return save(m, kind, detail)
        with patch.dict(os.environ, {"EIDOLON_TEST_MARKER": str(self.directory)}), patch.object(self.store, "save", fail):
            m = runtime.run(identity)
        self.assertEqual((m["status"], m["error"]["code"]), ("REVIEW_REQUIRED", "INTERNAL_ERROR"))
        self.assertFalse((self.directory / "entered").exists())
        self.assertEqual(runtime.reconcile(identity, decision="no-effect", actor="tester", reason="no permission sent")["status"], "BLOCKED")

    def test_n04_explicit_depth_limit_and_brackets_inside_strings(self):
        raw = ('{"version":1,"steps":[{"id":"s","tool":"text.stats","parameters":{"reference":'
               + '[' * 10_000 + ']' * 10_000 + '}}]}')
        runtime = Runtime(self.store, model=FixedModel(raw))
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        self.assertEqual((m["status"], m["error"]["code"]), ("FAILED", "MODEL_INVALID"))
        self.assertEqual(runtime.run(identity), m)
        self.assertNotIn("INTERNAL_ERROR", [e["kind"] for e in self.store.events(identity)])
        literal = '["\\' * 100
        self.assertEqual(parse_plan(plan(parameters={"reference": literal}))["steps"][0]["parameters"]["reference"], literal)
        for count, accepted in ((28, True), (29, False)):
            nested = plan().replace('"synthetic-note@1"', '[' * count + '0' + ']' * count)
            if accepted:
                parse_plan(nested)
            else:
                with self.assertRaises(ContractError):
                    parse_plan(nested)

    def test_n05_parent_reset_before_ready_has_no_execution(self):
        parent, child = multiprocessing.Pipe(duplex=True)
        outcome, called = [], []
        def function():
            called.append(True)
        def run():
            try:
                _child(child, function, (), str(self.directory / "receipt"), None)
            except BaseException as exc:
                outcome.append(exc)
        thread = threading.Thread(target=run)
        thread.start()
        self.wait_for(parent.poll)
        parent.close()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [])
        self.assertEqual(called, [])

    def test_n06_evidence_origin_and_digest_are_checked(self):
        runtime, identity = self.crash("CALL_STARTED")
        m = runtime.run(identity)
        output = text_stats(m["plan"]["steps"][0]["parameters"], m["context"])
        runtime.reconcile(identity, decision="observed-result", actor="tester", reason="measured independently", output=output)
        final = runtime.run(identity)
        self.assertEqual(final["result"]["evidence"][0]["receipt_origin"], "human_reconciliation")
        runtime, identity = self.crash("RESULT_VERIFIED")
        m = self.store.get(identity)
        m["calls"][0]["output"]["characters"] += 1
        self.store.save(m, "CORRUPTED_OUTPUT_FIXTURE")
        final = runtime.run(identity)
        self.assertEqual((final["status"], final["error"]["code"]), ("FAILED", "EVIDENCE_MISMATCH"))

    def test_n07_conflict_refused_then_cli_uses_exact_stored_receipt(self):
        runtime, identity = self.crash("TOOL_RETURNED")
        runtime.run(identity)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            runtime.reconcile(identity, decision="observed-result", actor="tester", reason="transcription error", output={"ok": True})
        self.assertEqual(self.store.get(identity)["status"], "REVIEW_REQUIRED")
        call = self.store.get(identity)["calls"][0]
        path = attempt_receipt_path(self.store.worker_lease_path(identity, call["id"], call["attempt"]))
        original = path.read_bytes()
        path.write_text('{"ok":false,"message":"conflicting stored error"}')
        with self.assertRaisesRegex(ValueError, "conflicting"):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="cannot replace prior receipt")
        self.assertTrue(self.store.get(identity)["calls"][0]["recovered_receipt"]["ok"])
        path.write_bytes(original)
        command = [sys.executable, "-m", "eidolon_core", "--state", str(self.directory)]
        adopted = subprocess.run(command + ["reconcile", identity, "--decision", "use-receipt", "--actor", "tester",
                                           "--reason", "inspect retained receipt"], capture_output=True, text=True, timeout=10)
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        self.assertEqual(json.loads(adopted.stdout)["status"], "BLOCKED")
        result = runtime.run(identity)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(self.count(identity), 1)
        self.assertEqual(result["context"]["items"][0]["epistemic_status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
