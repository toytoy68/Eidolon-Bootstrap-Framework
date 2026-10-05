# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_action_view.py
# Description : Décisions, applicabilité et effets dérivés sans mutation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from copy import deepcopy
from dataclasses import replace
import json
import subprocess
import sys
import tempfile
import unittest

from eidolon_core.action_view import action_view, presented_mission
from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import digest
from eidolon_core.presentation import render_result
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Registry
from tests.test_actions import Crash, FaultAction


class ActionViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = ActionRuntime(self.store)

    def proposal(self, runtime=None):
        runtime = runtime or self.runtime
        return runtime.run(runtime.create_restart("nas")["id"])

    def approve(self, m, runtime=None):
        return (runtime or self.runtime).decide(m["id"], expected_sha256=m["proposal"]["sha256"],
                            decision="approve", actor="test", reason="synthetic view test")

    def test_pending_age_does_not_expire_or_change_evidence(self):
        m = self.proposal()
        m["proposal"]["created_at"] = "1990-01-01T00:00:00+00:00"
        before = deepcopy(m)
        view = action_view(m)
        self.assertEqual(view["applicability"]["code"], "AWAITING_DECISION")
        self.assertEqual(view["effect"]["code"], "NOT_STARTED")
        self.assertFalse(view["authorizes_execution"])
        self.assertEqual(m, before)
        self.assertEqual(m["context"]["items"][0]["epistemic_status"], "UNVERIFIED")

    def test_approved_requires_recheck_and_is_not_effect(self):
        m = self.approve(self.proposal())
        view = action_view(m)
        self.assertEqual(view["decision"]["status"], "APPROVED")
        self.assertEqual(view["applicability"]["code"], "RECHECK_REQUIRED")
        self.assertEqual(view["effect"]["code"], "NOT_STARTED")
        self.assertIn("contrôles", render_result(m))
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 0)

    def test_changed_condition_remains_visible_after_decision_changes_error(self):
        m = self.approve(self.proposal())
        self.runtime.world.set_state("sim-nas", "UP")
        stale = self.runtime.run(m["id"])
        self.assertEqual(action_view(stale)["applicability"]["code"], "STALE_CONDITION")
        self.assertEqual(stale["proposal"]["status"], "APPROVED")
        revoked = self.runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"],
                                     decision="revoke", actor="test", reason="condition changed")
        self.assertEqual(action_view(revoked)["applicability"]["code"], "STALE_CONDITION")
        self.assertEqual(action_view(revoked)["decision"]["status"], "REVOKED")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 0)

    def test_configuration_mismatch_is_not_irrevocable_expiry(self):
        m = self.approve(self.proposal())
        other = ActionRuntime(self.store, limits=Limits(9))
        blocked = other.run(m["id"])
        self.assertEqual(action_view(blocked)["applicability"]["code"], "CONFIGURATION_MISMATCH")
        final = self.runtime.run(m["id"])
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(action_view(final)["effect"]["code"], "VERIFIED_PAST_EFFECT")

    def test_consumed_then_cancelled_before_tool_authorization(self):
        m = self.approve(self.proposal())
        def checkpoint(kind):
            if kind == "CALL_STARTED":
                self.store.request_cancel(m["id"])
        final = ActionRuntime(self.store, checkpoint=checkpoint).run(m["id"])
        view = action_view(final)
        self.assertEqual(final["proposal"]["status"], "USED")
        self.assertEqual(view["applicability"]["code"], "MISSION_CLOSED")
        self.assertEqual(view["effect"]["code"], "NOT_AUTHORIZED")
        self.assertEqual(view["attempt"], 1)
        self.assertEqual(final["calls"][0]["attempt"], 2)
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 0)
        self.assertIn("ne prouve pas un effet", render_result(final))

    def test_interruption_without_receipt_remains_unknown(self):
        m = self.approve(self.proposal())
        def checkpoint(kind):
            if kind == "CALL_STARTED":
                raise Crash()
        with self.assertRaises(Crash):
            ActionRuntime(self.store, checkpoint=checkpoint).run(m["id"])
        review = self.runtime.run(m["id"])
        view = action_view(review)
        self.assertEqual(view["decision"]["status"], "USED")
        self.assertEqual(view["effect"]["code"], "UNKNOWN")
        self.assertEqual(review["status"], "REVIEW_REQUIRED")

    def test_human_no_effect_remains_reported_then_new_proposal_is_separate(self):
        tool = replace(self.runtime.world.tool(), execute=FaultAction(self.runtime.world, "no-effect").execute)
        runtime = ActionRuntime(self.store, registry=Registry([tool]))
        m = self.approve(self.proposal(runtime), runtime)
        review = runtime.run(m["id"])
        self.assertEqual(action_view(review)["effect"]["code"], "UNKNOWN")
        reconciled = runtime.reconcile(m["id"], decision="no-effect", confirm_no_effect=True,
                                       actor="test", reason="checked synthetic world")
        self.assertEqual(action_view(reconciled)["effect"]["code"], "NO_EFFECT_REPORTED")
        again = runtime.run(m["id"])
        view = action_view(again)
        self.assertEqual(view["effect"]["code"], "NOT_STARTED")
        self.assertEqual(view["attempt"], 2)
        self.assertNotEqual(view["proposal_sha256"], m["proposal"]["sha256"])
        self.assertEqual(len(again["proposal_history"]), 1)

    def test_saved_result_is_not_verified_yet(self):
        m = self.approve(self.proposal())
        def checkpoint(kind):
            if kind == "RESULT_SAVED":
                raise Crash()
        with self.assertRaises(Crash):
            ActionRuntime(self.store, checkpoint=checkpoint).run(m["id"])
        pending = self.store.get(m["id"])
        self.assertEqual(action_view(pending)["effect"]["code"], "RESULT_UNVERIFIED")
        self.assertNotEqual(pending["status"], "SUCCEEDED")
        final = self.runtime.run(m["id"])
        self.assertEqual(action_view(final)["effect"]["code"], "VERIFIED_PAST_EFFECT")
        self.assertEqual(self.runtime.world.observe("sim-nas")["restarts"], 1)

    def test_proven_effect_is_historical_and_bad_hash_not_promoted(self):
        m = self.approve(self.proposal())
        final = self.runtime.run(m["id"])
        self.runtime.world.set_state("sim-nas", "DOWN")
        view = action_view(final)
        self.assertEqual(view["effect"]["code"], "VERIFIED_PAST_EFFECT")
        self.assertIn("santé actuelle", view["effect"]["message"])
        tampered = deepcopy(final)
        tampered["calls"][0]["output_sha256"] = "0" * 64
        self.assertEqual(action_view(tampered)["effect"]["code"], "INCONSISTENT_EVIDENCE")
        missing = deepcopy(final); missing["calls"] = []
        self.assertEqual(action_view(missing)["effect"]["code"], "UNKNOWN")

    def test_late_receipt_and_inconsistent_binding_never_promoted(self):
        m = self.approve(self.proposal())
        # Boundary snapshot: receipt observed, verification not run.
        m["proposal"]["status"] = "USED"
        call = m["calls"][0]
        call.update(status="STARTED", approval_sha256=m["proposal"]["sha256"])
        receipt = {"ok": True, "value": {"synthetic": True}}
        call.update(late_receipt=receipt, late_receipt_sha256=digest(receipt))
        self.assertEqual(action_view(m)["effect"]["code"], "RESULT_UNVERIFIED")
        call["late_receipt_sha256"] = "bad"
        self.assertEqual(action_view(m)["effect"]["code"], "INCONSISTENT_EVIDENCE")
        m["proposal"]["sha256"] = "bad"
        self.assertEqual(action_view(m)["applicability"]["code"], "BINDING_INVALID")

    def test_cli_view_is_ephemeral_and_human_does_not_trust_supplied_view(self):
        m = self.approve(self.proposal())
        before = self.store.get(m["id"])
        events = self.store.events(m["id"])
        proc = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", self.temp.name,
                               "show", m["id"], "--events"], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)
        self.assertEqual(out["action_view"]["effect"]["code"], "NOT_STARTED")
        self.assertNotIn("action_view", self.store.get(m["id"]))
        self.assertEqual(self.store.get(m["id"]), before)
        self.assertEqual(self.store.events(m["id"]), events)
        m["action_view"] = {"effect": {"code": "FORGED_SUCCESS"}}
        self.assertNotIn("FORGED_SUCCESS", render_result(m))
        self.assertEqual(presented_mission(m)["action_view"]["effect"]["code"], "NOT_STARTED")

    def test_non_action_mission_does_not_gain_action_view(self):
        m = Runtime(self.store).create("unrecognized synthetic request")
        self.assertIsNone(action_view(m))
        self.assertEqual(presented_mission(m), m)

    def test_cancel_request_visible_before_runtime_observes_it(self):
        m = self.approve(self.proposal())
        pending = self.store.request_cancel(m["id"])
        self.assertEqual(action_view(pending)["applicability"]["code"], "CANCEL_REQUESTED")
        self.assertEqual(action_view(pending)["effect"]["code"], "NOT_STARTED")

    def test_rejected_and_revoked_proposals_have_no_permission(self):
        for initial, decision in [("PENDING", "reject"), ("APPROVED", "revoke")]:
            m = self.proposal()
            if initial == "APPROVED":
                m = self.approve(m)
            m = self.runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"],
                                    decision=decision, actor="test", reason="synthetic")
            view = action_view(m)
            self.assertEqual(view["applicability"]["code"], m["proposal"]["status"])
            self.assertEqual(view["effect"]["code"], "NOT_STARTED")
            self.assertFalse(view["authorizes_execution"])


if __name__ == "__main__":
    unittest.main()
