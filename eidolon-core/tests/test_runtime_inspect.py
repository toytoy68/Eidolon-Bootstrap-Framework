# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_runtime_inspect.py
# Description : Diagnostic sans mutation, observations de verrous et bornes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout, redirect_stderr
import fcntl
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.recovery import prepare_review
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.runtime import Runtime, Limits
from eidolon_core.runtime_inspect import inspect_runtime, InspectionError, render_inspection
from eidolon_core import runtime_inspect
from eidolon_core.store import Store
from eidolon_core.worker import attempt_receipt_path


class Crash(BaseException):
    pass


def stop_after_result(kind):
    if kind == "RESULT_SAVED":
        raise Crash()


def hold_lease(path, ready, finish):
    with open(path, "r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.set()
        finish.wait(10)


class RuntimeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state")
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create(DEMO_REQUEST)

    def inspect(self, mission=None):
        return inspect_runtime(self.store.directory, (mission or self.mission)["id"])

    def files(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_new_mission_does_not_create_lock_or_initialize_store(self):
        before = self.files()
        with patch.object(Store, "__init__", side_effect=AssertionError("initialization")), \
                patch.object(Runtime, "__init__", side_effect=AssertionError("runtime")):
            result = self.inspect()
        self.assertEqual(self.files(), before)
        self.assertEqual(result["execution_lock"]["state"], "MISSING")
        self.assertEqual(result["invocation_budget"], {"state": "AVAILABLE", "limit": 64, "used": 0, "remaining": 64, "audit_checked": True})
        self.assertFalse(result["authorizes_execution"])
        self.assertFalse(result["external_effects_known"])
        self.assertFalse(result["filesystem_samples_atomic"])
        self.assertFalse(result["changed_during_sampling"])

    def test_existing_mission_lock_is_sampled_and_released_without_writing(self):
        with self.store.lock(self.mission["id"]):
            self.assertEqual(self.inspect()["execution_lock"]["state"], "HELD_AT_SAMPLE")
        before = self.files()
        self.assertEqual(self.inspect()["execution_lock"]["state"], "FREE_AT_SAMPLE")
        with self.store.lock(self.mission["id"]):
            pass
        self.assertEqual(self.files(), before)

    def test_completed_mission_and_receipts_are_not_adopted_or_read(self):
        mission = self.runtime.run(self.mission["id"])
        before = self.files()
        with patch("eidolon_core.worker._read_receipt", side_effect=AssertionError("receipt read")):
            result = self.inspect(mission)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertIn("TERMINAL_STATE_RETAIN_EVIDENCE", result["hints"])
        self.assertTrue(result["calls"])
        self.assertTrue(all(c["receipt"]["state"] == "PRESENT_UNVERIFIED" for c in result["calls"]))
        self.assertFalse(result["receipt_content_verified"])
        self.assertEqual(self.files(), before)

    def returned(self):
        runtime = ResearchRuntime(self.store, checkpoint=stop_after_result)
        mission = runtime.create_research("PRIVATE_CANARY jean@example.invalid", required_pages=2)
        with self.assertRaises(Crash):
            runtime.run(mission["id"])
        return self.store.get(mission["id"])

    def test_received_research_result_is_diagnosed_without_exposing_private_data(self):
        mission = self.returned()
        before = self.files()
        result = self.inspect(mission)
        self.assertIn("RETURNED_RESULT_AWAITS_VERIFICATION", result["hints"])
        self.assertEqual(result["calls"][0]["lease"]["authorization"], "MARKED")
        self.assertFalse(result["research_guard_checked"])
        for raw in (encode(result), render_inspection(result)):
            self.assertNotIn("PRIVATE_CANARY", raw)
            self.assertNotIn("jean@example.invalid", raw)
            self.assertNotIn("Première page", raw)
            self.assertNotIn(str(self.root), raw)
        self.assertEqual(self.files(), before)

    def test_worker_lock_held_does_not_claim_orphan_or_permission(self):
        mission = self.returned()
        call = mission["calls"][0]
        lease = self.store.worker_lease_path(mission["id"], call["id"], call["attempt"])
        with lease.open("r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            result = self.inspect(mission)
        self.assertEqual(result["calls"][0]["lease"], {"state": "HELD_AT_SAMPLE", "authorization": "UNKNOWN"})
        self.assertIn("LOCAL_LOCK_HELD", result["hints"])
        self.assertFalse(result["authorizes_execution"])

    def test_independent_process_lease_release_does_not_prove_no_effect(self):
        mission = self.returned()
        call = mission["calls"][0]
        lease = self.store.worker_lease_path(mission["id"], call["id"], call["attempt"])
        ctx = multiprocessing.get_context("spawn")
        ready, finish = ctx.Event(), ctx.Event()
        process = ctx.Process(target=hold_lease, args=(str(lease), ready, finish))
        process.start()
        try:
            self.assertTrue(ready.wait(5))
            held = self.inspect(mission)
            self.assertEqual(held["calls"][0]["lease"]["state"], "HELD_AT_SAMPLE")
        finally:
            finish.set(); process.join(5)
            if process.is_alive():
                process.terminate(); process.join(5)
        self.assertEqual(process.exitcode, 0)
        free = self.inspect(mission)
        self.assertEqual(free["calls"][0]["lease"]["state"], "FREE_AT_SAMPLE")
        self.assertEqual(free["calls"][0]["lease"]["authorization"], "MARKED")
        self.assertFalse(free["external_effects_known"])
        self.assertFalse(free["authorizes_execution"])

    def test_missing_lease_and_missing_receipt_stay_missing(self):
        mission = self.returned()
        call = mission["calls"][0]
        lease = self.store.worker_lease_path(mission["id"], call["id"], call["attempt"])
        receipt = attempt_receipt_path(lease)
        lease.unlink(); receipt.unlink()
        result = self.inspect(mission)
        self.assertEqual(result["calls"][0]["lease"]["state"], "MISSING")
        self.assertEqual(result["calls"][0]["receipt"]["state"], "MISSING")
        self.assertFalse(lease.exists()); self.assertFalse(receipt.exists())

    def test_symlink_fifo_and_invalid_marker_do_not_expose_contents(self):
        mission = self.returned()
        call = mission["calls"][0]
        lease = self.store.worker_lease_path(mission["id"], call["id"], call["attempt"])
        receipt = attempt_receipt_path(lease)
        secret = self.root / "secret"; secret.write_text("PRIVATE_MARKER_CANARY")
        lease.unlink(); lease.symlink_to(secret)
        receipt.unlink(); os.mkfifo(receipt)
        result = self.inspect(mission)
        self.assertEqual(result["calls"][0]["lease"]["state"], "UNAVAILABLE")
        self.assertEqual(result["calls"][0]["receipt"]["state"], "UNTRUSTED_ARTIFACT")
        lease.unlink(); lease.write_text("PRIVATE_MARKER_CANARY")
        result = self.inspect(mission)
        self.assertEqual(result["calls"][0]["lease"]["authorization"], "INVALID_MARKER")
        self.assertNotIn("PRIVATE_MARKER_CANARY", encode(result))

    def test_budget_corruption_is_reported_without_repair(self):
        mission = self.runtime.run(self.mission["id"])
        with self.store.connection() as db:
            db.execute("DELETE FROM events WHERE mission_id=? AND kind='INVOCATION_RESERVED' AND sequence="
                       "(SELECT min(sequence) FROM events WHERE mission_id=? AND kind='INVOCATION_RESERVED')",
                       (mission["id"], mission["id"]))
        before = self.files()
        result = self.inspect(mission)
        self.assertEqual(result["invocation_budget"]["state"], "INVALID")
        self.assertIn("INVOCATION_BUDGET_INVALID", result["hints"])
        self.assertEqual(self.files(), before)

    def test_budget_exhaustion_and_legacy_are_distinct(self):
        runtime = Runtime(self.store, limits=Limits(max_invocations=1))
        mission = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        self.assertEqual(self.inspect(mission)["invocation_budget"]["state"], "EXHAUSTED")
        legacy = Runtime(self.store, limits=Limits(max_invocations=None)).create(DEMO_REQUEST)
        self.assertEqual(self.inspect(legacy)["invocation_budget"], {"state": "LEGACY_UNBOUNDED", "audit_checked": False})

    def test_intervening_cancellation_detected_even_without_revision_change(self):
        artifact = runtime_inspect._artifact
        done = False
        def change(*args, **kwargs):
            nonlocal done
            if not done:
                done = True
                self.store.request_cancel(self.mission["id"])
            return artifact(*args, **kwargs)
        with patch.object(runtime_inspect, "_artifact", side_effect=change):
            result = self.inspect()
        self.assertTrue(result["changed_during_sampling"])
        self.assertFalse(result["cancel_requested"])  # first SQLite snapshot retained
        self.assertIn("SNAPSHOT_CHANGED_RESAMPLE", result["hints"])

    def test_unknown_effect_and_cancel_are_not_reinterpreted_as_safe(self):
        mission = self.returned()
        mission.update(phase="EXECUTING", status="REVIEW_REQUIRED")
        mission["calls"][0]["status"] = "STARTED"
        self.store.save(mission, "TEST_UNKNOWN")
        self.store.request_cancel(mission["id"])
        result = self.inspect(mission)
        self.assertIn("EFFECT_UNKNOWN_REVIEW_REQUIRED", result["hints"])
        self.assertIn("CANCELLATION_REQUESTED_NOT_PROOF_OF_STOP", result["hints"])
        self.assertFalse(result["external_effects_known"])

    def test_malformed_and_oversized_mission_are_refused_before_projection(self):
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", ('{"secret":"CANARY","id":1,"id":2}', self.mission["id"]))
        with self.assertRaisesRegex(InspectionError, "INVALID_INSPECTION_RECORD"):
            self.inspect()
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", ('x' * 1025, self.mission["id"]))
        with patch.object(runtime_inspect, "MAX_MISSION_BYTES", 1024), self.assertRaisesRegex(InspectionError, "INSPECTION_SIZE_LIMIT"):
            self.inspect()

    def test_cli_absent_state_and_recovery_copy_never_initialize(self):
        missing = self.root / "missing"
        for directory in (missing,):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = main(["--state", str(directory), "runtime-inspect", self.mission["id"]])
            self.assertEqual(rc, 2); self.assertEqual(out.getvalue(), "")
            self.assertNotIn(str(directory), err.getvalue())
            self.assertFalse(directory.exists())
        review = self.root / "review"
        prepare_review(self.store.path, review, actor="synthetic", reason="test")
        before = self.files()
        with self.assertRaisesRegex(InspectionError, "RECOVERY_REVIEW_ONLY"):
            inspect_runtime(review, self.mission["id"])
        self.assertEqual(self.files(), before)

    def test_cli_json_and_human_are_read_only_even_with_research_profile(self):
        before = self.files()
        for output_format in ("json", "human"):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(["--state", str(self.store.directory), "--profile", "research-sim",
                           "--format", output_format, "runtime-inspect", self.mission["id"]])
            self.assertEqual(rc, 0)
            if output_format == "json":
                self.assertEqual(json.loads(out.getvalue())["protocol"], runtime_inspect.PROTOCOL)
            else:
                self.assertIn("Eidolon Core Technologies", out.getvalue())
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
