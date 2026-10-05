# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_actions.py
# Description : Approbation, conditions, effets locaux et reprise simulée
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import ContractError, digest
from eidolon_core.objectives import assess
from eidolon_core.presentation import render_result
from eidolon_core.runtime import Limits
from eidolon_core.simulation import SimulatedServices
from eidolon_core.store import Store
from eidolon_core.tools import Registry, Policy
from tests.support import FixedModel


class Crash(BaseException):
    pass


@dataclass(frozen=True)
class FaultAction:
    world: SimulatedServices
    mode: str

    def execute(self, parameters, context):
        if self.mode == "no-effect":
            raise OSError("synthetic failure before transaction")
        result = self.world.restart(parameters, context)
        if self.mode == "lost":
            os._exit(23)
        if self.mode == "timeout-after-commit":
            time.sleep(10)
        if self.mode == "wrong-output":
            result["after"]["state"] = "DOWN"
        return result


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = ActionRuntime(self.store)

    def propose(self, runtime=None, target="nas"):
        runtime = runtime or self.runtime
        return runtime.run(runtime.create_restart(target)["id"])

    def decide(self, m, decision="approve", runtime=None, **changes):
        options = {"expected_sha256": m["proposal"]["sha256"], "decision": decision,
                   "actor": "synthetic-operator", "reason": "explicit local test decision", **changes}
        return (runtime or self.runtime).decide(m["id"], **options)

    def fault_runtime(self, mode, **kwargs):
        tool = replace(self.runtime.world.tool(), execute=FaultAction(self.runtime.world, mode).execute)
        return ActionRuntime(self.store, registry=Registry([tool]), **kwargs)

    def assertNoEffect(self):
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 0)

    def test_proposal_waits_and_decision_alone_never_executes(self):
        m = self.propose()
        self.assertEqual((m["status"], m["proposal"]["status"]), ("BLOCKED", "PENDING"))
        self.assertEqual(m["error"]["code"], "APPROVAL_REQUIRED")
        self.assertEqual(m["calls"][0]["status"], "PREPARED")
        self.assertIsNone(m["result"])
        self.assertNotIn("CALL_STARTED", [e["kind"] for e in self.store.events(m["id"])])
        approved = self.decide(m)
        self.assertEqual(approved["proposal"]["status"], "APPROVED")
        self.assertNoEffect()
        self.assertIn("pas une identité authentifiée", render_result(approved))

    def test_explicit_resume_mutates_fixture_and_verifies_receipt(self):
        m = self.propose()
        self.decide(m)
        result = ActionRuntime(Store(self.temp.name)).run(m["id"])
        self.assertEqual((result["status"], result["outcome"]["status"]), ("SUCCEEDED", "ACHIEVED"))
        self.assertEqual(result["proposal"]["status"], "USED")
        state = self.runtime.world.observe("sim-nas")
        self.assertEqual((state["state"], state["revision"], state["restarts"]), ("UP", 2, 1))
        self.assertEqual(result["calls"][0]["approval_sha256"], m["proposal"]["sha256"])
        self.assertEqual(self.runtime.world.receipt(m["id"])["result"], result["result"]["simulation"])
        self.assertEqual(result["context"]["items"][0]["epistemic_status"], "UNVERIFIED")
        self.assertEqual(self.runtime.run(m["id"]), result)
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        with self.assertRaises(ContractError):
            self.decide(result)

    def test_proposal_without_decision_does_not_expire(self):
        with patch("eidolon_core.approvals.timestamp", return_value="2000-01-01T00:00:00+00:00"):
            m = self.propose()
        pending = self.runtime.run(m["id"])
        self.assertEqual(pending["proposal"], m["proposal"])
        self.assertNoEffect()
        self.decide(pending)
        self.assertEqual(self.runtime.run(m["id"])["status"], "SUCCEEDED")

    def test_rejection_and_revocation_survive_restart(self):
        rejected = self.propose()
        self.decide(rejected, "reject")
        m = ActionRuntime(Store(self.temp.name)).run(rejected["id"])
        self.assertEqual(m["error"]["code"], "APPROVAL_REJECTED")
        with self.assertRaises(ContractError):
            self.decide(m)
        other = self.propose()
        approved = self.decide(other)
        self.decide(approved, "revoke")
        m = self.runtime.run(other["id"])
        self.assertEqual(m["error"]["code"], "APPROVAL_REVOKED")
        self.assertNoEffect()

    def test_wrong_hash_or_other_mission_approval_rejected(self):
        first, second = self.propose(), self.propose()
        for sha in ("0" * 64, second["proposal"]["sha256"]):
            with self.assertRaises(ContractError):
                self.decide(first, expected_sha256=sha)
        self.assertEqual(self.store.get(first["id"])["proposal"]["status"], "PENDING")
        self.assertNoEffect()

    def test_configuration_change_blocks_decision_and_execution(self):
        m = self.propose()
        changed = ActionRuntime(self.store, allowed_targets=[])
        with self.assertRaises(ContractError):
            self.decide(m, runtime=changed)
        self.assertEqual(changed.run(m["id"])["error"]["code"], "CONFIGURATION_CHANGED")
        self.assertNoEffect()

    def test_parameters_changed_after_approval_cannot_run(self):
        m = self.propose()
        self.decide(m)
        m = self.store.get(m["id"])
        m["plan"]["steps"][0]["parameters"]["target"] = "sim-memory"
        self.store.save(m, "TEST_TAMPER")
        m = self.runtime.run(m["id"])
        self.assertEqual(m["status"], "BLOCKED")
        self.assertNoEffect()

    def test_observation_or_plan_identity_changed_invalidates_approval(self):
        for change in ("observation", "plan_id"):
            m = self.propose()
            self.decide(m)
            m = self.store.get(m["id"])
            if change == "observation":
                m["action_observation"]["observed_at"] = "2000-01-01T00:00:00+00:00"
            else:
                m["plan"]["steps"][0]["id"] = "other-step"
            self.store.save(m, "TEST_TAMPER")
            m = self.runtime.run(m["id"])
            self.assertEqual(m["status"], "BLOCKED")
            self.assertNoEffect()

    def test_changed_state_and_aba_revision_block_without_consuming_approval(self):
        for states in (("UP",), ("UP", "DOWN")):
            m = self.propose()
            self.decide(m)
            for state in states:
                self.runtime.world.set_state("sim-nas", state)
            blocked = self.runtime.run(m["id"])
            self.assertEqual(blocked["error"]["code"], "ACTION_PRECONDITION_CHANGED")
            self.assertEqual(blocked["proposal"]["status"], "APPROVED")
            self.assertNoEffect()
            self.runtime.world.set_state("sim-nas", "DOWN")

    def test_non_down_service_ambiguous_target_and_permission_never_propose_action(self):
        for target in ("sim-memory", "offline", "service", "absent"):
            m = self.propose(target=target)
            self.assertEqual(m["status"], "BLOCKED")
            self.assertNotIn("proposal", m)
            self.assertFalse(m["calls"])
        m = self.propose(runtime=ActionRuntime(self.store, allowed_targets=[]))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertNotIn("proposal", m)
        self.assertNoEffect()
        self.assertFalse(Policy(allowed_tools=(self.runtime.world.tool().name,)).allows(self.runtime.world.tool()))

    def test_model_cannot_supply_approval(self):
        m = self.propose(runtime=ActionRuntime(self.store, model=FixedModel('{"version":1,"steps":[],"approved":true}')))
        self.assertEqual(m["status"], "FAILED")
        self.assertFalse(m["calls"])
        self.assertNoEffect()

    def test_cancellation_before_and_after_decision_never_executes(self):
        for approve in (False, True):
            m = self.propose()
            if approve:
                self.decide(m)
            self.assertEqual(self.runtime.cancel(m["id"])["status"], "CANCELLED")
            self.assertEqual(self.runtime.run(m["id"])["status"], "CANCELLED")
            with self.assertRaises(ContractError):
                self.decide(m)
        self.assertNoEffect()

    def test_saved_return_resumes_verification_without_mutation(self):
        def checkpoint(kind):
            if kind == "RESULT_SAVED":
                raise Crash()
        runtime = ActionRuntime(self.store, checkpoint=checkpoint)
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        with self.assertRaises(Crash):
            runtime.run(m["id"])
        saved = self.store.get(m["id"])
        self.assertEqual(saved["outcome"]["status"], "NOT_ACHIEVED")
        self.assertEqual(saved["calls"][0]["status"], "RETURNED")
        result = self.runtime.run(m["id"])
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        self.assertEqual(sum(e["kind"] == "CALL_STARTED" for e in self.store.events(m["id"])), 1)

    def test_lost_worker_after_committed_effect_requires_reconciliation(self):
        runtime = self.fault_runtime("lost")
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        review = runtime.run(m["id"])
        self.assertEqual(review["status"], "REVIEW_REQUIRED")
        self.assertEqual(runtime.run(m["id"])["status"], "REVIEW_REQUIRED")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        self.assertIsNone(review["result"])
        for confirmed in (False, True):
            with self.assertRaises(ContractError):
                runtime.reconcile(m["id"], decision="no-effect", actor="test", reason="investigate", confirm_no_effect=confirmed)
        receipt = self.runtime.world.receipt(m["id"])["result"]
        runtime.reconcile(m["id"], decision="observed-result", output=receipt, actor="test", reason="recover simulation transaction receipt")
        self.assertEqual(runtime.run(m["id"])["status"], "SUCCEEDED")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)

    def test_safe_retry_needs_new_approval_bound_to_new_attempt(self):
        runtime = self.fault_runtime("no-effect")
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        self.assertEqual(runtime.run(m["id"])["status"], "REVIEW_REQUIRED")
        runtime.reconcile(m["id"], decision="no-effect", actor="test", reason="inspected no transaction receipt", confirm_no_effect=True)
        again = runtime.run(m["id"])
        self.assertEqual(again["error"]["code"], "APPROVAL_REQUIRED")
        self.assertEqual(again["calls"][0]["attempt"], 2)
        self.assertNotEqual(again["proposal"]["sha256"], m["proposal"]["sha256"])
        self.assertEqual(again["proposal_history"][0]["status"], "USED")
        self.assertNotIn("approval_sha256", again["calls"][0])
        with self.assertRaises(ContractError):
            self.decide(again, runtime=runtime, expected_sha256=m["proposal"]["sha256"])
        self.assertNoEffect()

    def test_fake_human_result_cannot_prove_unexecuted_action(self):
        def checkpoint(kind):
            if kind == "CALL_STARTED":
                raise Crash()
        runtime = ActionRuntime(self.store, checkpoint=checkpoint)
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        with self.assertRaises(Crash):
            runtime.run(m["id"])
        self.runtime.run(m["id"])
        self.runtime.reconcile(m["id"], decision="observed-result", output={"claimed": "UP"}, actor="test", reason="unproven human claim")
        failed = self.runtime.run(m["id"])
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["error"]["code"], "VERIFICATION_FAILED")
        self.assertNoEffect()

    def test_incorrect_tool_output_and_forged_success_are_refused(self):
        runtime = self.fault_runtime("wrong-output")
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        m = runtime.run(m["id"])
        self.assertEqual(m["error"]["code"], "VERIFICATION_FAILED")
        self.assertIsNone(m["result"])
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        forged = deepcopy(m)
        forged.update(status="SUCCEEDED", result={"claimed": "success"})
        with self.assertRaises(ValueError):
            self.store.save(forged, "FAKE_SUCCESS")
        self.assertNotEqual(assess(forged)["status"], "ACHIEVED")

    def test_unapproved_launch_is_rejected_at_persistence_boundary(self):
        m = self.propose()
        m.update(status="RUNNING", phase="EXECUTING")
        m["calls"][0]["status"] = "STARTED"
        with self.assertRaises(ValueError):
            self.store.save(m, "CALL_STARTED")
        self.assertNoEffect()

    def test_two_approved_missions_race_on_same_revision_only_one_mutates(self):
        first, second = self.propose(), self.propose()
        self.decide(first)
        self.decide(second)
        barrier = threading.Barrier(2)
        def run(identity):
            def checkpoint(kind):
                if kind == "ACTION_CONDITION_CHECKED":
                    barrier.wait(timeout=15)
            return ActionRuntime(Store(self.temp.name), checkpoint=checkpoint).run(identity)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (first["id"], second["id"])))
        self.assertEqual(sorted(m["status"] for m in results), ["REVIEW_REQUIRED", "SUCCEEDED"])
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        loser = next(m for m in results if m["status"] == "REVIEW_REQUIRED")
        self.assertIsNone(loser["result"])
        self.assertIsNone(self.runtime.world.receipt(loser["id"]))

    def test_timeout_after_transaction_retains_review_and_cannot_retry_blindly(self):
        runtime = self.fault_runtime("timeout-after-commit", limits=Limits(2))
        m = self.propose(runtime)
        self.decide(m, runtime=runtime)
        result = runtime.run(m["id"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["error"]["code"], "TIMEOUT")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)
        with self.assertRaises(ContractError):
            runtime.reconcile(m["id"], decision="no-effect", actor="test", reason="effect exists", confirm_no_effect=True)
        self.assertEqual(runtime.run(m["id"])["status"], "REVIEW_REQUIRED")

    def test_world_replacement_cannot_reuse_approval(self):
        m = self.propose()
        self.decide(m)
        from pathlib import Path
        Path(self.runtime.world.path).unlink()
        replacement = ActionRuntime(self.store)
        self.assertNotEqual(replacement.world.world_id, self.runtime.world.world_id)
        blocked = replacement.run(m["id"])
        self.assertEqual(blocked["error"]["code"], "CONFIGURATION_CHANGED")
        self.assertEqual(replacement.world.observe("sim-nas")["restarts"], 0)

    def test_success_cannot_keep_proof_with_removed_approval(self):
        m = self.propose()
        self.decide(m)
        m = self.runtime.run(m["id"])
        del m["calls"][0]["approval_sha256"]
        with self.assertRaises(ValueError):
            self.store.save(m, "FORGED_SUCCESS")
        self.assertEqual(assess(m)["status"], "NOT_ACHIEVED")

    def test_cli_propose_decide_resume_and_fixture(self):
        base = [sys.executable, "-m", "eidolon_core", "--state", self.temp.name, "--profile", "action-sim"]
        def cli(*args):
            return subprocess.run(base + list(args), text=True, capture_output=True, timeout=25)
        proposed = cli("restart", "nas")
        self.assertEqual(proposed.returncode, 2, proposed.stderr)
        m = json.loads(proposed.stdout)
        decided = cli("decide", m["id"], "--proposal-sha", m["proposal"]["sha256"], "--decision", "approve", "--actor", "test", "--reason", "simulation")
        self.assertEqual(decided.returncode, 0, decided.stderr)
        self.assertNoEffect()
        ran = cli("run", m["id"])
        self.assertEqual(ran.returncode, 0, ran.stderr)
        fixture = cli("fixture", "sim-nas")
        self.assertEqual(json.loads(fixture.stdout)["restarts"], 1)
        self.assertEqual(json.loads(ran.stdout)["result"]["simulation"]["after"]["state"], "UP")


if __name__ == "__main__":
    unittest.main()
