# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_objectives.py
# Description : Critères de mission, couverture et preuves partielles
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Independent objectives with real spawned synthetic providers, no network."""
from copy import deepcopy
from dataclasses import replace
import json
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.objectives import assess
from eidolon_core.presentation import render_result
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Policy, Registry, default_registry
from tests.support import EmptyMemory, FixedModel, MultipleMemory, plan


class ObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def execute(self, request=DEMO_REQUEST, **kwargs):
        runtime = Runtime(self.store, **kwargs)
        return runtime, runtime.run(runtime.create(request)["id"])

    def test_unrelated_request_cannot_choose_easier_mission(self):
        runtime = Runtime(self.store, model=FixedModel(plan()))
        m = runtime.create("Vérifier si le service du NAS fonctionne.")
        with patch.object(runtime, "_invoke", side_effect=AssertionError("no provider may be called")):
            result = runtime.run(m["id"])
        self.assertEqual((result["status"], result["outcome"]["status"]), ("BLOCKED", "CLARIFICATION"))
        self.assertEqual(result["error"]["code"], "MISSION_UNSUPPORTED")
        self.assertIsNone(result["plan"])
        self.assertFalse(result["calls"])
        self.assertIn("Clarification nécessaire", render_result(result))

    def test_authorized_tool_still_must_serve_objective(self):
        tool = replace(default_registry().get("text.stats"), name="other.stats")
        _, m = self.execute(model=FixedModel(plan("other.stats")), registry=Registry([tool]),
                            policy=Policy(allowed_tools=("other.stats",)))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertIn("MISSION_PLAN_MISMATCH", m["error"]["message"])
        self.assertFalse(m["calls"])

    def test_partial_plan_never_executes_covered_subset(self):
        _, m = self.execute(memory=MultipleMemory(), model=FixedModel(plan()))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertIn("MISSION_INCOMPLETE_PLAN", m["error"]["message"])
        self.assertEqual(m["outcome"]["status"], "NOT_ACHIEVED")
        self.assertEqual(m["outcome"]["covered_references"], [])
        self.assertEqual(set(m["outcome"]["missing_references"]), {"synthetic-note@1", "synthetic-note-2@1"})
        self.assertFalse(m["calls"])
        self.assertNotIn("CALL_STARTED", [e["kind"] for e in self.store.events(m["id"])])

    def test_repeated_reference_cannot_inflate_progress(self):
        proposal = json.loads(plan())
        proposal["steps"] *= 2
        proposal["steps"][1] = {**proposal["steps"][1], "id": "repeated"}
        _, m = self.execute(model=FixedModel(encode(proposal)))
        self.assertEqual(m["status"], "BLOCKED")
        self.assertIn("MISSION_DUPLICATE_REFERENCE", m["error"]["message"])
        self.assertEqual(m["progress"]["completed"], 0)
        self.assertFalse(m["calls"])

    def test_empty_recall_has_own_diagnostic_and_explicit_retry(self):
        runtime = Runtime(self.store, memory=EmptyMemory(provider_id="synthetic-memory/1"))
        m = runtime.create(DEMO_REQUEST)
        first = runtime.run(m["id"])
        self.assertEqual((first["status"], first["outcome"]["status"]), ("BLOCKED", "NO_EVIDENCE"))
        self.assertEqual(first["error"]["code"], "MEMORY_EMPTY")
        self.assertIsNone(first["model_output"])
        self.assertFalse(first["calls"])
        resumed = Runtime(Store(self.temp.name)).run(m["id"])
        self.assertEqual(resumed["id"], first["id"])
        self.assertEqual(resumed["outcome"]["status"], "ACHIEVED")
        events = self.store.events(m["id"])
        self.assertEqual(sum(e["kind"] == "RECALL_STARTED" for e in events), 2)
        self.assertEqual(sum(e["kind"] == "CALL_STARTED" for e in events), 1)

    def test_complete_recall_coverage_keeps_uncertainty_and_scope(self):
        _, m = self.execute(memory=MultipleMemory())
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["outcome"]["status"], "ACHIEVED")
        self.assertEqual(m["outcome"]["scope"], "recalled_snapshot")
        self.assertEqual(len(m["outcome"]["covered_references"]), 2)
        self.assertEqual(m["outcome"]["missing_references"], [])
        self.assertEqual(Store(self.temp.name).get(m["id"]), m)
        for item in m["result"]["sources"]["items"]:
            self.assertEqual(item["epistemic_status"], "UNVERIFIED")
            self.assertTrue(item["needs_review"])

    def test_cancel_after_one_verified_result_is_partial(self):
        def checkpoint(kind):
            if kind == "RESULT_VERIFIED":
                self.store.request_cancel(identity)
        runtime = Runtime(self.store, memory=MultipleMemory(), checkpoint=checkpoint)
        identity = runtime.create(DEMO_REQUEST)["id"]
        m = runtime.run(identity)
        self.assertEqual((m["status"], m["outcome"]["status"]), ("CANCELLED", "PARTIAL"))
        self.assertEqual(m["outcome"]["covered_references"], ["synthetic-note@1"])
        self.assertEqual(m["outcome"]["missing_references"], ["synthetic-note-2@1"])
        self.assertIsNone(m["result"])
        self.assertEqual(len(m["calls"]), 1)
        self.assertIn("Partiel", render_result(m))

    def test_returned_receipt_alone_does_not_count_as_achieved(self):
        class Crash(BaseException):
            pass
        def checkpoint(kind):
            if kind == "RESULT_SAVED":
                raise Crash()
        runtime = Runtime(self.store, checkpoint=checkpoint)
        identity = runtime.create(DEMO_REQUEST)["id"]
        with self.assertRaises(Crash):
            runtime.run(identity)
        pending = Store(self.temp.name).get(identity)
        self.assertEqual(pending["calls"][0]["status"], "RETURNED")
        self.assertEqual(pending["outcome"]["status"], "NOT_ACHIEVED")
        result = Runtime(Store(self.temp.name)).run(identity)
        self.assertEqual(result["outcome"]["status"], "ACHIEVED")
        self.assertEqual(result["objective"], pending["objective"])
        self.assertEqual(sum(e["kind"] == "CALL_STARTED" for e in self.store.events(identity)), 1)

    def test_persistence_recomputes_outcome_and_refuses_forged_success(self):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        m.update(status="SUCCEEDED", result={"summary": "claimed"}, outcome={"status": "ACHIEVED"})
        with self.assertRaisesRegex(ValueError, "achieved mission criteria"):
            self.store.save(m, "FAKE_SUCCESS")
        self.assertEqual(self.store.get(m["id"])["status"], "NEW")

    def test_changed_objective_or_context_cannot_qualify_old_proof(self):
        _, m = self.execute(memory=MultipleMemory())
        original_revision = m["revision"]
        for change in ("references", "context", "request", "call"):
            with self.subTest(change=change):
                forged = deepcopy(m)
                if change == "references":
                    forged["objective"]["required_references"] = ["synthetic-note@1"]
                elif change == "context":
                    forged["context"]["items"][0]["content"] = "changed"
                elif change == "request":
                    forged["request"] = "Redémarrer le NAS"
                else:
                    forged["calls"][1]["step"] = forged["calls"][0]["step"]
                with self.assertRaises(ValueError):
                    self.store.save(forged, "FAKE_SUCCESS")
                self.assertNotEqual(assess(forged)["status"], "ACHIEVED")
        self.assertEqual(self.store.get(m["id"])["revision"], original_revision)

    def test_legacy_active_mission_requires_contract_but_stays_inspectable(self):
        runtime = Runtime(self.store)
        m = runtime.create(DEMO_REQUEST)
        del m["objective"]
        del m["outcome"]
        # Old snapshot fixture, not a model-visible mutation API.
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", (encode(m), m["id"]))
        with patch.object(runtime, "_invoke", side_effect=AssertionError("no legacy execution")):
            result = runtime.run(m["id"])
        self.assertEqual(result["error"]["code"], "MISSION_CONTRACT_REQUIRED")
        self.assertFalse(result["calls"])
        self.assertEqual(runtime.cancel(m["id"])["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
