# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_beta_fixture.py
# Description : Recette synthétique, isolation, publication et consultation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core import beta_fixture, preflight
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.contracts import ContractError
from eidolon_core.http_api import ReadOnlyStore, ReadServer, read_token
from eidolon_core.receipt_lookup import lookup
from eidolon_core.store import Store


class BetaFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "fixture"

    def prepare(self):
        report = beta_fixture.create(self.root)
        self.assertEqual(report["status"], "READY", report)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        return report

    def test_scenarios_receipts_and_runtime_bindings_are_real(self):
        report = self.prepare()
        self.assertEqual(report["mission_count"], 6)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        token = read_token(self.root / "read-token")
        self.assertNotIn(token, json.dumps(report) + json.dumps(self.manifest))
        store = ReadOnlyStore(self.root / "state")
        rows = {item["role"]: item for item in self.manifest["scenarios"]}
        for row in rows.values():
            mission = ClientSync(store).snapshot(row["mission_id"])["snapshot"]["mission"]
            self.assertEqual(mission["status"], row["expected_status"])
            self.assertEqual(mission["cancel_requested"], row["cancel_requested"])
            if row["proposal_status"]:
                self.assertEqual(mission["action_view"]["decision"]["status"], row["proposal_status"])
        receipts = [lookup(store, query)["receipt"] for query in self.manifest["receipt_queries"]]
        self.assertEqual(receipts[0]["cancel_outcome"], "REQUESTED")
        self.assertEqual([r["decision"] for r in receipts[1:]], ["approve", "revoke"])
        writable = Store(self.root / "state")
        actions = ActionRuntime(writable)
        self.assertEqual(actions.world.observe("sim-nas")["restarts"], 0)
        self.assertEqual(writable.get(rows["approval_pending"]["mission_id"])["configuration"], actions.configuration())

    def test_existing_destinations_never_touched(self):
        self.root.mkdir()
        sentinel = self.root / "sentinel"
        sentinel.write_bytes(b"preserve")
        for destination in (self.root, sentinel):
            self.assertEqual(beta_fixture.create(destination)["code"], "DESTINATION_EXISTS")
        link = self.root.parent / "link"
        link.symlink_to(self.root)
        self.assertEqual(beta_fixture.create(link)["code"], "DESTINATION_EXISTS")
        dangling = self.root.parent / "dangling"
        dangling.symlink_to(self.root.parent / "absent")
        self.assertEqual(beta_fixture.create(dangling)["code"], "DESTINATION_EXISTS")
        self.assertEqual(list(self.root.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_missing_parent_is_not_created(self):
        result = beta_fixture.create(self.root / "nested")
        self.assertEqual(result["status"], "NOT_CREATED")
        self.assertFalse(self.root.exists())

    def test_failure_is_sanitized_and_incomplete_state_is_refused(self):
        def fail(directory):
            Store(directory)
            raise RuntimeError("PRIVATE-PATH-SECRET")
        with patch.object(beta_fixture, "_populate", side_effect=fail):
            report = beta_fixture.create(self.root)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertNotIn("PRIVATE", json.dumps(report))
        with self.assertRaisesRegex(ContractError, "BETA_PREPARATION_INCOMPLETE"):
            ReadOnlyStore(self.root / "state")
        check = preflight.inspect(self.root / "state", self.root / "read-token")
        self.assertIn("BETA_PREPARATION_INCOMPLETE", [c["code"] for c in check["checks"]])
        self.assertEqual(beta_fixture.create(self.root)["code"], "DESTINATION_EXISTS")

    def test_token_failure_and_publication_failure_keep_guard(self):
        # Population already has independent end-to-end coverage; inject only
        # its boundary here to isolate failures after population.
        def populate(directory):
            Store(directory)
            return {"synthetic": True}
        with patch.object(beta_fixture, "_populate", side_effect=populate):
            with patch.object(beta_fixture, "create_token", return_value={"status": "NOT_CREATED"}):
                self.assertEqual(beta_fixture.create(self.root)["status"], "INCOMPLETE")
            other = self.root.parent / "second"
            original = Path.unlink
            def refuse_marker(path, *args, **kwargs):
                if path.name == "BETA-PREPARATION-INCOMPLETE":
                    raise OSError("PRIVATE")
                return original(path, *args, **kwargs)
            with patch.object(Path, "unlink", refuse_marker):
                self.assertEqual(beta_fixture.create(other)["status"], "INCOMPLETE")
        for directory in (self.root, other):
            with self.assertRaisesRegex(ContractError, "BETA_PREPARATION_INCOMPLETE"):
                ReadOnlyStore(directory / "state")

    def test_guard_is_rechecked_on_existing_reader(self):
        self.prepare()
        reader = ReadOnlyStore(self.root / "state")
        (self.root / "state" / "BETA-PREPARATION-INCOMPLETE").touch()
        with self.assertRaisesRegex(ContractError, "BETA_PREPARATION_INCOMPLETE"):
            reader.health()

    def test_real_cli_json_human_exit_codes_and_distinct_store_identity(self):
        env = {**os.environ, "PYTHONPATH": "src"}
        command = [sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(self.root)]
        first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=25)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertEqual(json.loads(first.stdout)["status"], "READY")
        self.assertEqual(first.stderr, "")
        before = (self.root / "state" / "missions.sqlite3").read_bytes()
        second = subprocess.run(command + ["--format", "human"], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(second.returncode, 2)
        self.assertIn("[ERREUR]", second.stdout)
        self.assertEqual(before, (self.root / "state" / "missions.sqlite3").read_bytes())
        other = self.root.parent / "other"
        self.assertEqual(beta_fixture.create(other)["status"], "READY")
        first_id = json.loads((self.root / "manifest.json").read_text())["store_id"]
        other_id = json.loads((other / "manifest.json").read_text())["store_id"]
        self.assertNotEqual(first_id, other_id)

    def test_preflight_and_http_receipt_read_leave_state_unchanged(self):
        self.prepare()
        state, token_file = self.root / "state", self.root / "read-token"
        self.assertEqual(preflight.inspect(state, token_file, web_root="desktop/connected")["status"], "PASS")
        before = {p.name: p.read_bytes() for p in state.glob("*.sqlite3")}
        server = ReadServer(state, read_token(token_file), port=0)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("POST", "/v1/command-receipt", json.dumps(self.manifest["receipt_queries"][1]),
                                   {"Authorization": "Bearer " + read_token(token_file), "Content-Type": "application/json"})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["receipt"]["decision"], "approve")
            finally:
                connection.close()
        finally:
            server.shutdown()
            thread.join(5)
            server.server_close()
        self.assertEqual(before, {p.name: p.read_bytes() for p in state.glob("*.sqlite3")})


if __name__ == "__main__":
    unittest.main()
