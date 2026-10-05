# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_review_regressions.py
# Description : Régressions de la revue C-REV-001 et preuves d'interruption
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic regression tests; no VM, network, user data or real model."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, digest, encode, parse_plan
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.tools import Registry, default_registry, text_stats
from tests.support import (FixedModel, RecoverableModel, big_result, marker_tool,
                           plan, receipt_then_wait, slow_tool, verify_big)


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory)

    def registry(self, **changes):
        return Registry([replace(default_registry().get("text.stats"), **changes)])

    def wait_for(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("test synchronization deadline exceeded")

    def started_count(self, identity):
        return sum(e["kind"] == "CALL_STARTED" for e in self.store.events(identity))

    def test_f01_overflow_and_surrogates_fail_durably(self):
        for raw in (plan().replace('"synthetic-note@1"', '1e999'),
                    plan().replace('"test-step"', '"\\ud800"'),
                    plan().replace('"test-step"', '"\ud800"')):
            with self.subTest(raw=ascii(raw)):
                runtime = Runtime(self.store, model=FixedModel(raw))
                identity = runtime.create(DEMO_REQUEST)["id"]
                m = runtime.run(identity)
                self.assertEqual((m["status"], m["error"]["code"]), ("FAILED", "MODEL_INVALID"))
                self.assertEqual(runtime.run(identity), m)
                self.assertEqual(self.started_count(identity), 0)
                self.assertIsNone(m["result"])
                self.assertEqual(self.store.events(identity)[-1]["kind"], "FAILED")

    def test_f01_nested_overflow_rejected_at_parser_boundary(self):
        raw = plan().replace('"synthetic-note@1"', '{"nested":[1e999]}')
        with self.assertRaises(ContractError):
            parse_plan(raw)

    def test_f02_five_large_verified_outputs_survive_restart(self):
        proposal = json.loads(plan())
        proposal["steps"] = [{**proposal["steps"][0], "id": str(i)} for i in range(5)]
        runtime = Runtime(self.store, model=FixedModel(encode(proposal)),
                          registry=self.registry(execute=big_result, verify=verify_big))
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["progress"], {"completed": 5, "total": 5})
        self.assertLess(len(encode(m["result"])), 10_000)
        self.assertEqual(Store(self.directory).get(identity), m)
        for ref, call in zip(m["result"]["evidence"], m["calls"]):
            self.assertEqual(ref["call_id"], call["id"])
            self.assertEqual(ref["output_sha256"], digest(call["output"]))
            self.assertNotIn("output", ref)
        self.assertEqual(runtime.run(identity), m)
        self.assertEqual(self.started_count(identity), 5)

    def test_f03_abandon_keeps_unknown_effect_and_is_terminal(self):
        runtime = Runtime(self.store, registry=self.registry(execute=slow_tool), limits=Limits(2.0))
        identity = runtime.create(DEMO_REQUEST)["id"]
        self.assertEqual(runtime.run(identity)["status"], "REVIEW_REQUIRED")
        m = runtime.reconcile(identity, decision="abandon", actor="tester", reason="effect cannot be determined")
        self.assertEqual(m["status"], "ABANDONED")
        self.assertTrue(m["calls"][0]["effect_unknown"])
        self.assertEqual(m["calls"][0]["status"], "UNKNOWN")
        self.assertIsNone(m["result"])
        self.assertEqual(runtime.run(identity), m)
        self.assertEqual(runtime.cancel(identity), m)
        self.assertEqual(self.started_count(identity), 1)
        self.assertEqual(self.store.events(identity)[-1]["detail"]["actor"], "tester")

    def test_f03_cli_abandon_works_without_original_provider(self):
        runtime = Runtime(self.store, registry=self.registry(execute=slow_tool), limits=Limits(2.0))
        identity = runtime.create(DEMO_REQUEST)["id"]
        runtime.run(identity)
        command = [sys.executable, "-m", "eidolon_core", "--state", str(self.directory)]
        result = subprocess.run(command + ["reconcile", identity, "--decision", "abandon",
                                "--actor", "tester", "--reason", "unknown"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "ABANDONED")
        shown = subprocess.run(command + ["--format", "human", "show", identity],
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("effet inconnu", shown.stdout)
        run = subprocess.run(command + ["run", identity], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 4)

    def test_f04_live_orphan_blocks_reconciliation_even_with_wrong_pid(self):
        runtime = Runtime(self.store, registry=self.registry(execute=marker_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        child = subprocess.Popen([sys.executable, "-m", "tests.review_driver", str(self.directory), identity],
                                 env={**os.environ, "EIDOLON_TEST_MARKER": str(self.directory)},
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.wait_for(lambda: (self.directory / "entered").exists())
            child.kill()
            child.wait(timeout=5)
            m = runtime.run(identity)
            self.assertEqual(m["status"], "REVIEW_REQUIRED")
            worker = m["calls"][0]["worker"]
            self.assertNotEqual(worker["pid"], child.pid)
            self.assertIn("started_at", worker)
            m["calls"][0]["worker"]["pid"] = -1  # Guard relies on lease, not a PID lookup.
            self.store.save(m, "TEST_PID_METADATA")
            for decision in ("no-effect", "observed-result"):
                with self.assertRaises(Busy):
                    runtime.reconcile(identity, decision=decision, actor="tester", reason="test guard", output=None)
            self.assertFalse((self.directory / "effect").exists())
            self.assertEqual(self.started_count(identity), 1)
            (self.directory / "release").touch()
            self.wait_for(lambda: (self.directory / "effect").exists())
            def quiescent():
                try:
                    with self.store.worker_quiescent(identity, m["calls"][0]):
                        return True
                except Busy:
                    return False
            self.wait_for(quiescent)
            output = text_stats(m["plan"]["steps"][0]["parameters"], m["context"])
            runtime.reconcile(identity, decision="observed-result", actor="tester",
                              reason="worker finished; observed synthetic result", output=output)
            self.assertEqual(runtime.run(identity)["status"], "SUCCEEDED")
            self.assertEqual(self.started_count(identity), 1)
        finally:
            (self.directory / "release").touch()
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

    def test_f04_parent_dies_before_execution_permission(self):
        runtime = Runtime(self.store)
        identity = runtime.create(DEMO_REQUEST)["id"]
        process = subprocess.run([sys.executable, "-m", "tests.crash_driver", str(self.directory),
                                  identity, "WORKER_SPAWNED"], capture_output=True, text=True, timeout=8)
        self.assertEqual(process.returncode, 77, process.stderr)
        m = runtime.run(identity)
        self.assertEqual(m["status"], "REVIEW_REQUIRED")
        def quiescent():
            try:
                with self.store.worker_quiescent(identity, m["calls"][0]):
                    return True
            except Busy:
                return False
        self.wait_for(quiescent)
        runtime.reconcile(identity, decision="no-effect", actor="tester", reason="crashed before execute gate")
        self.assertEqual(runtime.run(identity)["status"], "SUCCEEDED")

    def test_f04_legacy_unknown_call_cannot_enable_retry(self):
        runtime = Runtime(self.store, registry=self.registry(execute=slow_tool), limits=Limits(2.0))
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        del m["calls"][0]["worker_protocol"]
        self.store.save(m, "LEGACY_FIXTURE")
        with self.assertRaises(Busy):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="unknown old worker")
        self.assertEqual(runtime.reconcile(identity, decision="abandon", actor="tester", reason="unknown")["status"],
                         "ABANDONED")

    def test_f05_model_timeout_and_outage_resume_same_mission(self):
        for mode in ("timeout", "error"):
            with self.subTest(mode=mode):
                runtime = Runtime(self.store, model=RecoverableModel(mode), limits=Limits(2.0))
                identity = runtime.create(DEMO_REQUEST)["id"]
                m = runtime.run(identity)
                self.assertEqual((m["status"], m["error"]["code"]), ("BLOCKED", "MODEL_UNAVAILABLE"))
                self.assertIsNone(m["model_output"])
                self.assertEqual(self.started_count(identity), 0)
                restored = Runtime(self.store, model=RecoverableModel(), limits=Limits(2.0))
                self.assertEqual(restored.run(identity)["status"], "SUCCEEDED")
                self.assertEqual(self.started_count(identity), 1)

    def test_f06_receipt_kept_at_cancellation(self):
        marker = self.directory / "receipt-ready"
        runtime = Runtime(self.store)
        identity = runtime.create(DEMO_REQUEST)["id"]
        errors = []
        def cancel_after_receipt():
            try:
                self.wait_for(marker.exists)
                self.store.request_cancel(identity)
            except Exception as exc:
                errors.append(exc)
        with patch.dict(os.environ, {"EIDOLON_TEST_RECEIPT_READY": str(marker)}), \
                patch("eidolon_core.worker._child", receipt_then_wait):
            thread = threading.Thread(target=cancel_after_receipt)
            thread.start()
            m = runtime.run(identity)
            thread.join(9)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual((m["status"], m["error"]["code"]), ("REVIEW_REQUIRED", "CANCELLED"))
        self.assertTrue(m["calls"][0]["late_receipt"]["ok"])
        self.assertEqual(m["calls"][0]["late_receipt_sha256"], digest(m["calls"][0]["late_receipt"]))
        self.assertIsNone(m["result"])
        self.assertEqual(runtime.run(identity), m)
        abandoned = runtime.reconcile(identity, decision="abandon", actor="tester", reason="cancelled with unverified receipt")
        self.assertEqual(abandoned["status"], "ABANDONED")
        self.assertEqual(abandoned["calls"][0]["late_receipt"], m["calls"][0]["late_receipt"])
        self.assertEqual(self.started_count(identity), 1)

    def test_f06_receipt_kept_at_deadline_and_reverified_without_retry(self):
        marker = self.directory / "receipt-ready"
        runtime = Runtime(self.store, limits=Limits(2.0))
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch.dict(os.environ, {"EIDOLON_TEST_RECEIPT_READY": str(marker)}), \
                patch("eidolon_core.worker._child", receipt_then_wait):
            m = runtime.run(identity)
        self.assertTrue(marker.exists())
        self.assertEqual((m["status"], m["error"]["code"]), ("REVIEW_REQUIRED", "TIMEOUT"))
        self.assertIsNone(m["result"])
        with self.assertRaises(ValueError):
            runtime.reconcile(identity, decision="no-effect", actor="tester", reason="receipt cannot be discarded")
        output = m["calls"][0]["late_receipt"]["value"]
        runtime.reconcile(identity, decision="observed-result", actor="tester", reason="inspected late output", output=output)
        self.assertEqual(runtime.run(identity)["status"], "SUCCEEDED")
        self.assertEqual(self.started_count(identity), 1)

    def test_internal_error_uses_durable_phase_and_can_resume_before_effect(self):
        def fault(kind):
            if kind == "PLAN_SAVED":
                raise RuntimeError("synthetic fault")
        runtime = Runtime(self.store, checkpoint=fault)
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        self.assertEqual((m["status"], m["error"]["code"]), ("BLOCKED", "INTERNAL_ERROR"))
        self.assertEqual(self.store.events(identity)[-1]["kind"], "INTERNAL_ERROR")
        self.assertEqual(Runtime(self.store).run(identity)["status"], "SUCCEEDED")

    def test_internal_error_after_execution_does_not_replay(self):
        save = self.store.save
        def fail_save(mission, kind, detail=None):
            if kind == "RESULT_SAVED":
                raise OSError("synthetic persistence failure")
            return save(mission, kind, detail)
        runtime = Runtime(self.store)
        identity = runtime.create(DEMO_REQUEST)["id"]
        with patch.object(self.store, "save", fail_save):
            m = runtime.run(identity)
        self.assertEqual((m["status"], m["phase"]), ("REVIEW_REQUIRED", "EXECUTING"))
        self.assertEqual(m["error"]["code"], "INTERNAL_ERROR")
        self.assertEqual(m["calls"][0]["status"], "STARTED")
        self.assertEqual(runtime.run(identity), m)
        self.assertEqual(self.started_count(identity), 1)


if __name__ == "__main__":
    unittest.main()
