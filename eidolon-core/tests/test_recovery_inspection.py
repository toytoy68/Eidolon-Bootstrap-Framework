# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_recovery_inspection.py
# Description : Contrats et bornes des captures historiques en lecture seule
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import recovery
from eidolon_core.actions import ActionRuntime
from eidolon_core.cli import main
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class RecoveryInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "source")
        self.mission = Runtime(self.store).create(DEMO_REQUEST)
        self.review = self.root / "review"
        recovery.prepare_review(self.store.path, self.review, actor="synthetic", reason="test")
        self.path = self.review / "missions.sqlite3"
        with closing(sqlite3.connect(self.path)) as db:
            self.report = json.loads(db.execute("SELECT value FROM sync_metadata WHERE key='recovery_report'").fetchone()[0])

    def mutate(self, sql, args):
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute(sql, args)

    def report_value(self, value):
        self.mutate("UPDATE sync_metadata SET value=? WHERE key='recovery_report'", (json.dumps(value),))

    def test_authority_and_historical_flags_cannot_be_reinterpreted(self):
        for changes in ({"execution_authority": True}, {"historical_only": False},
                        {"external_effects_reconciled": True}, {"mode": "ACTIVE"},
                        {"artifacts_restored": ["all"]}, {"execution_authority": 0}):
            with self.subTest(changes=changes):
                self.report_value(dict(self.report, **changes))
                before = self.path.read_bytes()
                with self.assertRaisesRegex(ContractError, "RECOVERY_REPORT_MISMATCH"):
                    recovery.inspect_review(self.review)
                self.assertEqual(self.path.read_bytes(), before)
                with self.assertRaisesRegex(ContractError, "RECOVERY_REVIEW_ONLY"):
                    Store(self.review)

    def test_bad_types_extra_fields_and_identity_shapes_are_refused(self):
        for value in ([], None, "CANARY", dict(self.report, secret="CANARY"),
                      dict(self.report, store_id="not-an-id"), dict(self.report, source_snapshot_sha256="invalid"),
                      dict(self.report, prepared_at="without a date"), dict(self.report, actor="\ud800"),
                      dict(self.report, reason="x" * 4001)):
            with self.subTest(value_type=type(value).__name__):
                self.report_value(value)
                with self.assertRaisesRegex(ContractError, "RECOVERY_REPORT_MISMATCH"):
                    recovery.inspect_review(self.review)

    def test_duplicate_nonfinite_and_oversized_report_have_constant_errors(self):
        for raw, code in ((json.dumps(self.report)[:-1]+',"execution_authority":false}', "INVALID_RECOVERY_RECORD"),
                          ('{"number":NaN}', "INVALID_RECOVERY_RECORD"),
                          ('x' * (recovery.MAX_INSPECTION_REPORT + 1), "RECOVERY_INSPECTION_LIMIT")):
            self.mutate("UPDATE sync_metadata SET value=? WHERE key='recovery_report'", (raw,))
            with self.assertRaisesRegex(ContractError, code):
                recovery.inspect_review(self.review)

    def test_legacy_report_without_capture_semantics_remains_readable(self):
        old = dict(self.report); old.pop("capture_semantics")
        self.report_value(old)
        result = recovery.inspect_review(self.review, mission_id=self.mission["id"])
        self.assertNotIn("capture_semantics", result)
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["mission"]["status_at_snapshot"], "NEW")

    def test_mission_identity_cancel_and_known_states_are_validated(self):
        for changes in ({"id": "m-" + "f" * 32}, {"status": "PRIVATE_CANARY"},
                        {"phase": []}, {"calls": "wrong"}, {"proposal": {"status": "CANARY"}}):
            with self.subTest(changes=changes):
                body = dict(self.mission, **changes)
                self.mutate("UPDATE missions SET body=?", (json.dumps(body),))
                with self.assertRaisesRegex(ContractError, "INVALID_RECOVERY_MISSION"):
                    recovery.inspect_review(self.review)
        self.mutate("UPDATE missions SET body=?,cancel_requested=2", (json.dumps(self.mission),))
        with self.assertRaisesRegex(ContractError, "INVALID_RECOVERY_MISSION"):
            recovery.inspect_review(self.review)

    def test_duplicate_mission_key_is_not_silently_accepted(self):
        raw = json.dumps(self.mission)[:-1] + ',"status":"NEW"}'
        self.mutate("UPDATE missions SET body=?", (raw,))
        with self.assertRaisesRegex(ContractError, "INVALID_RECOVERY_RECORD"):
            recovery.inspect_review(self.review)

    def test_bounds_refuse_without_partial_or_mutated_report(self):
        before = self.path.read_bytes()
        for name, value in (("MAX_INSPECTION_MISSIONS", 0), ("MAX_INSPECTION_BODY", 10),
                            ("MAX_DATABASE_BYTES", 1), ("INSPECTION_SECONDS", 0)):
            with self.subTest(bound=name), patch.object(recovery, name, value):
                with self.assertRaisesRegex(ContractError, "RECOVERY_INSPECTION_LIMIT"):
                    recovery.inspect_review(self.review)
            self.assertEqual(self.path.read_bytes(), before)

    def test_used_action_remains_historical_and_never_becomes_an_approval(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart("nas")["id"])
        runtime.decide(mission["id"], expected_sha256=mission["proposal"]["sha256"],
                       decision="approve", actor="synthetic", reason="test")
        completed = runtime.run(mission["id"])
        self.assertEqual(completed["proposal"]["status"], "USED")
        target = self.root / "used-review"
        recovery.prepare_review(self.store.path, target, actor="synthetic", reason="used approval")
        result = recovery.inspect_review(target, mission_id=mission["id"])
        self.assertEqual(result["mission"]["proposal_status_at_snapshot"], "USED")
        self.assertFalse(result["execution_authority"])

    def test_sql_progress_deadline_interrupts_expensive_count(self):
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("CREATE TABLE effort(n INTEGER)")
                db.executemany("INSERT INTO effort VALUES (?)", [(i,) for i in range(200)])
                db.execute("DROP TABLE events")
                db.execute("CREATE VIEW events AS SELECT a.n FROM effort a, effort b, effort c, effort d")
        before = self.path.read_bytes()
        with patch.object(recovery, "INSPECTION_SECONDS", 0.005), self.assertRaisesRegex(ContractError, "RECOVERY_INSPECTION_LIMIT"):
            recovery.inspect_review(self.review)
        self.assertEqual(self.path.read_bytes(), before)

    def test_cli_bad_report_has_constant_error_without_traceback_or_state_change(self):
        self.report_value(["PRIVATE_CANARY"])
        before = self.path.read_bytes()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--state", str(self.review), "recovery-inspect"])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn("PRIVATE_CANARY", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual(json.loads(err.getvalue())["message"], "RECOVERY_REPORT_MISMATCH")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
