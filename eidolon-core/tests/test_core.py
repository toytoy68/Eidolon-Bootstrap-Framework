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

from eidolon_core.contracts import ContractError, encode, parse_plan, validate_context
from eidolon_core.memory import DEMO_REQUEST, DEMO_TEXT, SyntheticMemory
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.tools import Policy, Registry, default_registry, text_stats
from tests.support import (EmptyMemory, FixedModel, InjectionMemory, SlowMemory,
                           UnavailableMemory, lost_tool, plan, slow_tool, slow_verifier, wrong_result)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def run_mission(self, **kwargs):
        runtime = Runtime(self.store, **kwargs)
        mission = runtime.create(DEMO_REQUEST)
        return runtime, runtime.run(mission["id"])

    def registry(self, **kwargs):
        return Registry([replace(default_registry().get("text.stats"), **kwargs)])

    def test_complete_mission_preserves_sources_and_verified_evidence(self):
        runtime, m = self.run_mission()
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["progress"], {"completed": 1, "total": 1})
        item = m["result"]["sources"]["items"][0]
        self.assertEqual(item["content"], DEMO_TEXT)
        self.assertEqual(item["epistemic_status"], "UNVERIFIED")
        self.assertTrue(item["needs_review"])
        self.assertEqual(m["calls"][0]["output"]["characters"], len(DEMO_TEXT))
        self.assertEqual(runtime.run(m["id"]), m)
        self.assertEqual(len([e for e in self.store.events(m["id"]) if e["kind"] == "CALL_STARTED"]), 1)

    def test_unknown_tool_denied(self):
        _, m = self.run_mission(model=FixedModel(plan("shell")))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertEqual(m["calls"], [])

    def test_allowlist_does_not_permit_external_effects(self):
        _, m = self.run_mission(registry=self.registry(effect="network"))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertFalse(m["calls"])

    def test_policy_denial_independent_of_model(self):
        _, m = self.run_mission(policy=Policy(allowed_tools=()))
        self.assertEqual(m["status"], "BLOCKED")

    def test_invalid_parameters_never_execute(self):
        for parameters in ({"reference": "missing@1"}, {"reference": True},
                           {"reference": "synthetic-note@1", "shell": "do something"}):
            with self.subTest(parameters=parameters):
                _, m = self.run_mission(model=FixedModel(plan(parameters=parameters)))
                self.assertEqual(m["status"], "BLOCKED")
                self.assertFalse(m["calls"])

    def test_entire_plan_preflight_prevents_partial_execution(self):
        proposal = json.loads(plan())
        proposal["steps"].append({"id": "later", "tool": "shell", "parameters": {}})
        _, m = self.run_mission(model=FixedModel(encode(proposal)))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertFalse(m["calls"])

    def test_malformed_or_claimed_success_never_succeeds(self):
        for output in ('not JSON', '{"status":"SUCCEEDED"}', '{"version":1,"steps":[]}',
                       '{"version":1,"version":1,"steps":[]}', {"version": 1},
                       '{"version":true,"steps":[]}', '{"version":NaN,"steps":[]}'):
            with self.subTest(output=output):
                _, m = self.run_mission(model=FixedModel(output))
                self.assertEqual(m["status"], "FAILED")
                self.assertIsNone(m["result"])
                self.assertFalse(m["calls"])

    def test_memory_outage_can_resume_without_changing_identity(self):
        _, m = self.run_mission(memory=UnavailableMemory())
        self.assertEqual(m["status"], "BLOCKED")
        self.assertIsNone(m["plan"])
        resumed = Runtime(Store(self.temp.name)).run(m["id"])
        self.assertEqual(resumed["status"], "SUCCEEDED")
        self.assertEqual(resumed["id"], m["id"])

    def test_empty_memory_does_not_imply_success(self):
        _, m = self.run_mission(memory=EmptyMemory())
        self.assertEqual(m["status"], "FAILED")
        self.assertIsNone(m["result"])

    def test_injection_in_memory_remains_inert_text(self):
        _, m = self.run_mission(memory=InjectionMemory())
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["calls"][0]["step"]["tool"], "text.stats")
        self.assertIn("Ignore policy", m["result"]["sources"]["items"][0]["content"])

    def test_bad_result_is_not_a_success(self):
        _, m = self.run_mission(registry=self.registry(execute=wrong_result))
        self.assertEqual(m["status"], "FAILED")
        self.assertEqual(m["error"]["code"], "VERIFICATION_FAILED")
        self.assertIsNone(m["result"])
        self.assertEqual(m["progress"]["completed"], 0)

    def test_memory_timeout_is_bounded_and_blocks(self):
        start = time.monotonic()
        _, m = self.run_mission(memory=SlowMemory(), limits=Limits(0.3))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertLess(time.monotonic() - start, 3)

    def test_tool_timeout_requires_reconciliation(self):
        runtime, m = self.run_mission(registry=self.registry(execute=slow_tool), limits=Limits(0.5))
        self.assertEqual(m["status"], "REVIEW_REQUIRED")
        self.assertEqual(m["error"]["code"], "TIMEOUT")
        self.assertEqual(runtime.run(m["id"]), m)

    def test_worker_loss_requires_reconciliation(self):
        _, m = self.run_mission(registry=self.registry(execute=lost_tool))
        self.assertEqual(m["status"], "REVIEW_REQUIRED")
        self.assertEqual(m["error"]["code"], "WORKER_LOST")

    def test_verification_timeout_keeps_receipt_without_success(self):
        _, m = self.run_mission(registry=self.registry(verify=slow_verifier), limits=Limits(0.5))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertEqual(m["calls"][0]["status"], "RETURNED")
        self.assertIsNone(m["result"])

    def test_cancel_before_execution(self):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        result = runtime.cancel(m["id"])
        self.assertEqual(result["status"], "CANCELLED")
        self.assertFalse(result["calls"])

    def test_cancel_during_tool_requires_review_and_never_retries(self):
        runtime = Runtime(self.store, registry=self.registry(execute=slow_tool))
        m = runtime.create(DEMO_REQUEST)

        def request():
            for _ in range(500):
                if self.store.get(m["id"])["phase"] == "EXECUTING":
                    self.store.request_cancel(m["id"])
                    return
                time.sleep(0.01)

        thread = threading.Thread(target=request)
        thread.start()
        result = runtime.run(m["id"])
        thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        runtime.reconcile(m["id"], decision="no-effect", actor="tester", reason="synthetic worker stopped")
        result = runtime.run(m["id"])
        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(len([e for e in self.store.events(m["id"]) if e["kind"] == "CALL_STARTED"]), 1)

    def crash(self, boundary):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        process = subprocess.run([sys.executable, "-m", "tests.crash_driver", self.temp.name,
                                  m["id"], boundary], capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 77, process.stderr)
        return runtime, m["id"]

    def test_process_crashes_before_tools_resume_safely(self):
        for boundary in ("RECALL_STARTED", "CONTEXT_SAVED", "MODEL_OUTPUT_SAVED", "PLAN_SAVED"):
            with self.subTest(boundary=boundary):
                runtime, identity = self.crash(boundary)
                result = runtime.run(identity)
                self.assertEqual(result["status"], "SUCCEEDED")
                self.assertEqual(len(result["calls"]), 1)

    def test_crash_with_unknown_effect_never_replays(self):
        for boundary in ("CALL_STARTED", "TOOL_RETURNED"):
            with self.subTest(boundary=boundary):
                runtime, identity = self.crash(boundary)
                result = runtime.run(identity)
                self.assertEqual(result["status"], "REVIEW_REQUIRED")
                self.assertEqual(runtime.run(identity), result)
                self.assertIsNone(result["result"])
                self.assertEqual(result["calls"][0]["attempt"], 1)

    def test_crash_after_receipt_reverifies_without_reexecution(self):
        for boundary in ("RESULT_SAVED", "RESULT_VERIFIED", "SUCCEEDED"):
            with self.subTest(boundary=boundary):
                runtime, identity = self.crash(boundary)
                result = runtime.run(identity)
                self.assertEqual(result["status"], "SUCCEEDED")
                self.assertEqual(len([e for e in self.store.events(identity) if e["kind"] == "CALL_STARTED"]), 1)

    def test_no_effect_reconciliation_is_audited_and_retry_explicit(self):
        runtime, identity = self.crash("CALL_STARTED")
        runtime.run(identity)
        reconciled = runtime.reconcile(identity, decision="no-effect", actor="human", reason="checked no effect")
        self.assertEqual(reconciled["status"], "BLOCKED")
        self.assertEqual(reconciled["calls"][0]["attempt"], 2)
        self.assertEqual(runtime.run(identity)["status"], "SUCCEEDED")
        event = [e for e in self.store.events(identity) if e["kind"] == "RECONCILED"][0]
        self.assertEqual(event["detail"]["actor"], "human")

    def test_human_result_must_still_verify_and_does_not_confirm_source(self):
        for good in (True, False):
            with self.subTest(good=good):
                runtime, identity = self.crash("TOOL_RETURNED")
                m = runtime.run(identity)
                output = text_stats(m["plan"]["steps"][0]["parameters"], m["context"]) if good else {"ok": True}
                runtime.reconcile(identity, decision="observed-result", actor="human", reason="observed output", output=output)
                result = runtime.run(identity)
                self.assertEqual(result["status"], "SUCCEEDED" if good else "FAILED")
                self.assertEqual(result["context"]["items"][0]["epistemic_status"], "UNVERIFIED")
                self.assertEqual(result["calls"][0]["receipt_origin"], "human_reconciliation")

    def test_configuration_change_blocks_execution(self):
        runtime, identity = self.crash("PLAN_SAVED")
        changed = Runtime(self.store, policy=Policy(allowed_tools=()))
        self.assertEqual(changed.run(identity)["error"]["code"], "CONFIGURATION_CHANGED")
        self.assertEqual(runtime.run(identity)["status"], "SUCCEEDED")

    def test_competing_runner_is_rejected_but_cancel_request_persists(self):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        with self.store.lock(m["id"]):
            with self.assertRaises(Busy):
                runtime.run(m["id"])
            runtime.cancel(m["id"])
        self.assertEqual(runtime.run(m["id"])["status"], "CANCELLED")

    def test_store_rejects_stale_snapshot_and_unproved_success(self):
        m = Runtime(self.store).create(DEMO_REQUEST)
        stale = self.store.get(m["id"])
        self.store.save(m, "CHECK")
        with self.assertRaises(Busy):
            self.store.save(stale, "STALE")
        m["status"] = "SUCCEEDED"
        with self.assertRaises(ValueError):
            self.store.save(m, "FORGED")
        self.assertEqual(self.store.get(m["id"])["status"], "NEW")

    def test_cancellation_success_race_is_closed_transactionally(self):
        def cancel(kind):
            if kind == "RESULT_VERIFIED":
                self.store.request_cancel(identity)
        runtime = Runtime(self.store, checkpoint=cancel)
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        self.assertEqual(m["status"], "CANCELLED")
        self.assertIsNone(m["result"])

    def test_multiple_steps_progress(self):
        proposal = json.loads(plan())
        proposal["steps"].append({**proposal["steps"][0], "id": "second"})
        _, m = self.run_mission(model=FixedModel(encode(proposal)))
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["progress"], {"completed": 2, "total": 2})
        self.assertNotEqual(m["calls"][0]["id"], m["calls"][1]["id"])

    def test_no_automatic_expiration_on_show_or_resume(self):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        m["created_at"] = "2000-01-01T00:00:00Z"
        self.store.save(m, "SYNTHETIC_AGE")
        self.assertEqual(self.store.get(m["id"])["status"], "NEW")
        self.assertEqual(runtime.run(m["id"])["status"], "SUCCEEDED")

    def test_cli_demo_and_durable_show(self):
        command = [sys.executable, "-m", "eidolon_core", "--state", self.temp.name]
        demo = subprocess.run(command + ["demo"], capture_output=True, text=True, timeout=15)
        self.assertEqual(demo.returncode, 0, demo.stderr)
        m = json.loads(demo.stdout)
        show = subprocess.run(command + ["show", m["id"], "--events"], capture_output=True, text=True, timeout=5)
        self.assertEqual(show.returncode, 0, show.stderr)
        data = json.loads(show.stdout)
        self.assertEqual(data["status"], "SUCCEEDED")
        self.assertEqual(data["events"][-1]["kind"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
