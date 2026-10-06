# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_projection_guards.py
# Description : Refus des projections corrompues sans exposition de données
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import json
import tempfile
import unittest

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync, SyncError, project_mission
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.mission_list import MissionList
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from tests import test_http_api as http_tests


class ProjectionGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.m = Runtime(self.store).create(DEMO_REQUEST)
        self.sync = ClientSync(self.store)

    def persist(self, mission):
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(mission), self.m["id"]))

    def test_body_identity_must_match_selected_row_for_snapshot_and_list(self):
        mission = copy.deepcopy(self.m)
        mission["id"] = "m-" + "f" * 32
        self.persist(mission)
        for read in (lambda: self.sync.snapshot(self.m["id"]), lambda: MissionList(self.store).page()):
            with self.subTest(reader=read):
                with self.assertRaises(SyncError) as caught:
                    read()
                self.assertEqual(caught.exception.code, "INVALID_MISSION_IDENTITY")

    def test_metadata_cannot_be_an_arbitrary_object_or_oversized_text(self):
        for key in ("status", "phase"):
            for value in ({"PRIVATE-MARKER": "corrupt field"}, ["private"], 2, "x" * 41):
                mission = copy.deepcopy(self.m)
                mission[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(SyncError):
                    project_mission(mission)
        for parent, key, value in (("objective", "kind", {"PRIVATE-MARKER": True}),
                                   ("outcome", "status", ["private"]),
                                   ("objective", "kind", "x" * 81)):
            mission = copy.deepcopy(self.m)
            mission[parent][key] = value
            with self.subTest(parent=parent), self.assertRaises(SyncError):
                project_mission(mission)

    def test_progress_has_exact_nonnegative_integer_values(self):
        for key in ("completed", "total"):
            for value in (True, -1, 1.5, 2**53, "1", {"PRIVATE-MARKER": True}):
                mission = copy.deepcopy(self.m)
                mission["progress"][key] = value
                self.persist(mission)
                with self.subTest(key=key, value=value), self.assertRaises(SyncError):
                    self.sync.snapshot(self.m["id"])
        mission = copy.deepcopy(self.m)
        mission["progress"] = {"completed": 2**53 - 1, "total": None}
        self.assertEqual(project_mission(mission)["progress"], mission["progress"])

    def test_sql_cancel_flag_is_not_coerced_from_arbitrary_values(self):
        for value in (2, -1, "not-a-boolean"):
            with self.store.connection() as db:
                db.execute("UPDATE missions SET cancel_requested=? WHERE id=?", (value, self.m["id"]))
            for read in (lambda: self.sync.snapshot(self.m["id"]), lambda: MissionList(self.store).page()):
                with self.subTest(value=value), self.assertRaises(SyncError):
                    read()

    def test_duplicate_json_fields_are_not_silently_selected(self):
        encoded = json.dumps(self.m)
        duplicate = encoded[:-1] + ',"status":"SUCCEEDED"}'
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", (duplicate, self.m["id"]))
        with self.assertRaises(SyncError):
            self.sync.snapshot(self.m["id"])
        with self.assertRaises(SyncError):
            MissionList(self.store).page()

    def test_action_projection_does_not_export_nested_private_metadata(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart("nas")["id"])
        for key, value in (("call_id", {"PRIVATE-MARKER": True}), ("attempt", True), ("attempt", 2**53)):
            changed = copy.deepcopy(mission)
            changed["proposal"]["action"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(SyncError):
                project_mission(changed)
        changed = copy.deepcopy(mission)
        changed["proposal"]["sha256"] = {"PRIVATE-MARKER": True}
        with self.assertRaises(SyncError):
            project_mission(changed)
        valid = project_mission(mission)["action_view"]
        self.assertEqual(valid["decision"]["status"], "PENDING")
        self.assertFalse(valid["authorizes_execution"])
        self.assertEqual(runtime.world.observe("sim-nas")["restarts"], 0)

    def test_poll_rejects_invalid_event_reference_metadata(self):
        cursor = self.sync.snapshot(self.m["id"])["cursor"]
        self.store.save(self.store.get(self.m["id"]), "TEST_EVENT")
        for column, value in (("kind", "x" * 65), ("at", "x" * 65), ("kind", "")):
            with self.store.connection() as db:
                db.execute("UPDATE events SET kind='TEST_EVENT',at='2026-10-06T00:00:00+00:00' WHERE sequence>?", (cursor["sequence"],))
                db.execute(f"UPDATE events SET {column}=? WHERE sequence>?", (value, cursor["sequence"]))
            with self.subTest(column=column), self.assertRaises(SyncError):
                self.sync.poll(self.m["id"], cursor)

    def test_unknown_objective_remains_null_without_inventing_a_catalogue(self):
        mission = Runtime(self.store).create("unknown synthetic objective")
        self.assertIsNone(ClientSync(self.store).snapshot(mission["id"])["snapshot"]["mission"]["objective_kind"])


class HTTPProjectionGuardTests(unittest.TestCase):
    setUp = http_tests.HTTPReadTests.setUp
    stop = http_tests.HTTPReadTests.stop
    request = http_tests.HTTPReadTests.request
    json = http_tests.HTTPReadTests.json

    def test_corrupt_projection_returns_no_payload_on_snapshot_or_list(self):
        mission = self.store.get(self.mission["id"])
        mission["status"] = {"PRIVATE-MARKER": "must not be exported"}
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(mission), self.mission["id"]))
        before = self.store.path.read_bytes()
        for path, kwargs in (("/v1/missions/" + self.mission["id"], {}),
                             ("/v1/missions", {"method": "POST", "data": {}})):
            status, _, report = self.json(path, **kwargs)
            self.assertEqual(status, 503)
            self.assertEqual(report["error"], "STATE_UNAVAILABLE")
            self.assertNotIn("PRIVATE-MARKER", json.dumps(report))
        self.assertEqual(self.store.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
