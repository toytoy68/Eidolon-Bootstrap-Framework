# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_receipt_lookup.py
# Description : Reçus historiques, corruption, transaction et frontière HTTP
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import contextmanager
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CancelCommands, DecisionCommands
from eidolon_core.http_api import ReadOnlyStore
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.receipt_lookup import ReceiptLookupError, lookup
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from tests import test_http_api as http_tests


def cancel_request(store, identity, key="cancel-001"):
    return dict(protocol="eidolon-cancel-command/1",
                store_id=ClientSync(store).snapshot(identity)["store_id"], client_id="test-client",
                command_key=key, mission_id=identity, actor="PRIVATE-ACTOR", reason="PRIVATE-REASON")


def query_for(command):
    return {k: command[k] for k in ("store_id", "client_id", "command_key", "mission_id")}


class ReceiptLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.mission = Runtime(self.store).create(DEMO_REQUEST)
        self.command = cancel_request(self.store, self.mission["id"])
        self.query = query_for(self.command)
        self.reader = ReadOnlyStore(self.temp.name)

    def record(self):
        return CancelCommands(self.store).submit(self.command)

    def replace(self, value):
        with self.store.connection() as db:
            db.execute("UPDATE command_receipts SET body=?", (json.dumps(value),))

    def assert_error(self, code, query=None):
        with self.assertRaises(ReceiptLookupError) as caught:
            lookup(self.reader, self.query if query is None else query)
        self.assertEqual(caught.exception.code, code)

    def test_absent_is_uncertain_and_does_not_create_a_receipt(self):
        before = self.store.path.read_bytes()
        result = lookup(self.reader, self.query)
        self.assertEqual((result["status"], result["receipt"]), ("NOT_FOUND", None))
        for field in ("execution_evidence", "effect_absence_evidence", "authorizes_resend", "authorizes_execution"):
            self.assertIs(result[field], False)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_cancellation_found_does_not_mean_stopped_or_executed(self):
        receipt = self.record()
        before = self.store.path.read_bytes()
        with patch("eidolon_core.worker.invoke", side_effect=AssertionError("no tool")):
            result = lookup(self.reader, self.query)
        self.assertEqual(result["receipt"], receipt)
        self.assertEqual(result["status"], "FOUND")
        self.assertEqual(self.store.get(self.mission["id"])["status"], "NEW")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(before, self.store.path.read_bytes())

    def test_historical_decision_does_not_replace_revoked_current_state(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart("nas")["id"])
        command = dict(protocol="eidolon-decision-command/1",
                       store_id=self.query["store_id"], client_id="decision-client", command_key="approve-001",
                       mission_id=mission["id"], expected_revision=mission["revision"],
                       proposal_sha256=mission["proposal"]["sha256"], decision="approve",
                       actor="PRIVATE", reason="PRIVATE")
        receipt = DecisionCommands(runtime).submit(command)
        current = self.store.get(mission["id"])
        revoke = {**command, "command_key": "revoke-001", "expected_revision": current["revision"], "decision": "revoke"}
        revoked = DecisionCommands(runtime).submit(revoke)
        self.assertEqual(lookup(self.reader, query_for(command))["receipt"], receipt)
        self.assertEqual(lookup(self.reader, query_for(revoke))["receipt"], revoked)
        self.assertEqual(self.store.get(mission["id"])["proposal"]["status"], "REVOKED")
        self.assertEqual(runtime.world.observe("sim-nas")["restarts"], 0)

    def test_new_cancellation_receipt_is_hash_bound_to_its_event(self):
        receipt = self.record()
        self.assertEqual(lookup(self.reader, self.query)["receipt_binding"], "EVENT_HASH")
        for update in ({"mission_status_at_recording": "RUNNING"}, {"mission_revision": 5}):
            self.replace({**receipt, **update})
            self.assert_error("RECEIPT_UNAVAILABLE")
        self.replace(receipt)
        self.assertEqual(lookup(self.reader, self.query)["receipt"], receipt)

    def test_terminal_cancellation_history_cannot_be_changed_to_success(self):
        Runtime(self.store).cancel(self.mission["id"])
        receipt = self.record()
        self.assertEqual(receipt["mission_status_at_recording"], "CANCELLED")
        for update in ({"mission_status_at_recording": "SUCCEEDED"},
                       {"cancel_requested_at_recording": not receipt["cancel_requested_at_recording"]}):
            self.replace({**receipt, **update})
            self.assert_error("RECEIPT_UNAVAILABLE")

    def test_legacy_receipt_remains_readable_with_explicit_weaker_binding(self):
        receipt = self.record()
        with self.store.connection() as db:
            raw, = db.execute("SELECT detail FROM events WHERE sequence=?", (receipt["event_sequence"],)).fetchone()
            detail = json.loads(raw)
            detail.pop("receipt_sha256")
            db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), receipt["event_sequence"]))
            # Reproduce a pre-boundary database, not a downgraded new receipt.
            db.execute("DELETE FROM sync_metadata WHERE key='receipt_hash_required_from'")
        before = self.store.path.read_bytes()
        result = lookup(self.reader, self.query)
        self.assertEqual(result["receipt_binding"], "LEGACY_FIELDS")
        self.assertEqual(result["receipt"], receipt)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_new_event_cannot_be_downgraded_by_removing_only_its_hash(self):
        receipt = self.record()
        with self.store.connection() as db:
            detail = json.loads(db.execute("SELECT detail FROM events WHERE sequence=?", (receipt["event_sequence"],)).fetchone()[0])
            del detail["receipt_sha256"]
            db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), receipt["event_sequence"]))
        self.assert_error("RECEIPT_UNAVAILABLE")
        self.replace({**receipt, "mission_status_at_recording": "RUNNING"})
        self.assert_error("RECEIPT_UNAVAILABLE")

    def test_boundary_does_not_retroactively_require_hash_on_legacy_receipt(self):
        first = self.record()
        with self.store.connection() as db:
            detail = json.loads(db.execute("SELECT detail FROM events WHERE sequence=?", (first["event_sequence"],)).fetchone()[0])
            del detail["receipt_sha256"]
            db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), first["event_sequence"]))
            db.execute("DELETE FROM sync_metadata WHERE key='receipt_hash_required_from'")
        second_command = {**self.command, "command_key": "second"}
        second = CancelCommands(self.store).submit(second_command)
        self.assertGreater(second["event_sequence"], first["event_sequence"])
        before = self.store.path.read_bytes()
        self.assertEqual(lookup(self.reader, self.query)["receipt_binding"], "LEGACY_FIELDS")
        self.assertEqual(lookup(self.reader, query_for(second_command))["receipt_binding"], "EVENT_HASH")
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_boundary_includes_hashed_receipts_from_pre_boundary_version(self):
        first = self.record()
        with self.store.connection() as db:
            db.execute("DELETE FROM sync_metadata WHERE key='receipt_hash_required_from'")
        second = CancelCommands(self.store).submit({**self.command, "command_key": "second"})
        with self.store.connection() as db:
            boundary = db.execute("SELECT value FROM sync_metadata WHERE key='receipt_hash_required_from'").fetchone()[0]
            self.assertEqual(int(boundary), first["event_sequence"])
            detail = json.loads(db.execute("SELECT detail FROM events WHERE sequence=?", (first["event_sequence"],)).fetchone()[0])
            del detail["receipt_sha256"]
            db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), first["event_sequence"]))
        self.assert_error("RECEIPT_UNAVAILABLE")

    def test_hashed_receipt_below_raised_boundary_is_refused(self):
        first = self.record()
        second = CancelCommands(self.store).submit({**self.command, "command_key": "second"})
        with self.store.connection() as db:
            db.execute("UPDATE sync_metadata SET value=? WHERE key='receipt_hash_required_from'", (str(second["event_sequence"]),))
        self.assert_error("RECEIPT_UNAVAILABLE")

    def test_invalid_boundary_is_refused_and_failed_receipt_does_not_leave_boundary(self):
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON command_receipts BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        import sqlite3
        with self.assertRaises(sqlite3.Error):
            self.record()
        with self.store.connection() as db:
            self.assertIsNone(db.execute("SELECT value FROM sync_metadata WHERE key='receipt_hash_required_from'").fetchone())
            db.execute("DROP TRIGGER fail")
        self.record()
        for invalid in ("0", "01", "-1", "1.0", "x", "9" * 50, "9007199254740992", "9007199254740991"):
            with self.store.connection() as db:
                db.execute("UPDATE sync_metadata SET value=? WHERE key='receipt_hash_required_from'", (invalid,))
            self.assert_error("RECEIPT_UNAVAILABLE")

    def test_malformed_or_wrong_event_hash_is_not_a_legacy_receipt(self):
        receipt = self.record()
        for value in (None, False, "bad", "0" * 64):
            with self.store.connection() as db:
                raw, = db.execute("SELECT detail FROM events WHERE sequence=?", (receipt["event_sequence"],)).fetchone()
                detail = json.loads(raw)
                detail["receipt_sha256"] = value
                db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), receipt["event_sequence"]))
            self.assert_error("RECEIPT_UNAVAILABLE")

    def test_rejected_decision_is_readable(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart("nas")["id"])
        command = dict(protocol="eidolon-decision-command/1", store_id=self.query["store_id"],
                       client_id="client", command_key="reject-001", mission_id=mission["id"],
                       expected_revision=mission["revision"], proposal_sha256=mission["proposal"]["sha256"],
                       decision="reject", actor="test", reason="test")
        receipt = DecisionCommands(runtime).submit(command)
        self.assertEqual(lookup(self.reader, query_for(command))["receipt"], receipt)

    def test_decision_receipt_cannot_change_its_recorded_meaning(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart("nas")["id"])
        command = dict(protocol="eidolon-decision-command/1", store_id=self.query["store_id"],
                       client_id="client", command_key="approve-001", mission_id=mission["id"],
                       expected_revision=mission["revision"], proposal_sha256=mission["proposal"]["sha256"],
                       decision="approve", actor="test", reason="test")
        receipt = DecisionCommands(runtime).submit(command)
        for update in ({"decision": []}, {"decision": "approve", "approval_status_at_recording": "USED"},
                       {"proposal_sha256": "bad"}, {"mission_revision": 0},
                       {"decision": "reject", "approval_status_at_recording": "REJECTED"}):
            self.replace({**receipt, **update})
            self.assert_error("RECEIPT_UNAVAILABLE", query_for(command))

    def test_already_requested_and_terminal_cancel_receipts(self):
        self.record()
        second = {**self.command, "command_key": "cancel-002"}
        receipt = CancelCommands(self.store).submit(second)
        self.assertEqual(receipt["cancel_outcome"], "ALREADY_REQUESTED")
        self.assertEqual(lookup(self.reader, query_for(second))["receipt"], receipt)
        Runtime(self.store).run(self.mission["id"])
        third = {**self.command, "command_key": "cancel-003"}
        receipt = CancelCommands(self.store).submit(third)
        self.assertEqual(receipt["cancel_outcome"], "ALREADY_TERMINAL")
        self.assertEqual(lookup(self.reader, query_for(third))["receipt"], receipt)
        self.assertEqual(lookup(self.reader, self.query)["receipt"]["cancel_outcome"], "REQUESTED")

    def test_store_change_blocks_even_absent_receipt(self):
        self.assert_error("STORE_CHANGED", {**self.query, "store_id": "s-" + "f" * 32})
        self.record()
        with self.store.connection() as db:
            db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ("s-" + "f" * 32,))
        self.assert_error("STORE_CHANGED")

    def test_mission_mismatch_never_exports_another_receipt(self):
        self.record()
        self.assert_error("RECEIPT_MISSION_MISMATCH", {**self.query, "mission_id": "m-" + "f" * 32})

    def test_invalid_query_rejected_before_database_access(self):
        variants = [None, [], {}, {**self.query, "extra": "secret"}]
        for key in self.query:
            variants.extend({**self.query, key: v} for v in (True, None, 1, "", "../x", "x" * 81))
        with patch.object(self.reader, "connection", side_effect=AssertionError("no DB")):
            for variant in variants:
                with self.subTest(query=repr(variant)):
                    with self.assertRaisesRegex(ReceiptLookupError, "INVALID_RECEIPT_QUERY"):
                        lookup(self.reader, variant)

    def test_client_and_key_namespaces_do_not_alias(self):
        self.record()
        for key in ("client_id", "command_key"):
            result = lookup(self.reader, {**self.query, key: "another"})
            self.assertEqual(result["status"], "NOT_FOUND")

    def test_corrupt_fields_and_new_versions_are_not_exported(self):
        receipt = self.record()
        variants = [None, [], {}, {**receipt, "actor": "PRIVATE"}]
        mutations = {
            "protocol": ["unknown/2", [], None], "status": ["SUCCEEDED", []],
            "store_id": ["s-" + "f" * 32], "client_id": ["other"], "command_key": ["other"],
            "request_sha256": ["bad", None, "f" * 64], "execution_evidence": [True, 0],
            "effect_absence_evidence": [True, 0], "mission_revision": [True, -1, 2**53],
            "event_sequence": [True, 0, 2**53], "recorded_at": [None, "today", "2026-10-06", "2026-10-06T00:00:00"],
            "cancel_outcome": ["UNKNOWN", []], "mission_status_at_recording": ["UNKNOWN", "SUCCEEDED"],
            "cancel_requested_at_recording": [False, 1],
        }
        for key, values in mutations.items():
            variants.extend({**receipt, key: v} for v in values)
        for variant in variants:
            with self.subTest(value=repr(variant)[:120]):
                self.replace(variant)
                self.assert_error("RECEIPT_UNAVAILABLE")

    def test_bad_raw_json_duplicate_and_oversized_receipts(self):
        receipt = self.record()
        raw = json.dumps(receipt)
        cases = (b"\xff", b"{", b"x" * 32769, raw.replace('"RECORDED"', 'NaN').encode(),
                 ('{"status":"OTHER",' + raw[1:]).encode(),
                 ("[" * 4000 + "]" * 4000).encode())
        for body in cases:
            with self.subTest(body=body[:30]):
                with self.store.connection() as db:
                    db.execute("UPDATE command_receipts SET body=?", (body,))
                self.assert_error("RECEIPT_UNAVAILABLE")

    def test_receipt_event_identity_time_and_kind_are_bound(self):
        receipt = self.record()
        event = self.store.events(self.mission["id"])[-1]
        for column, value in (("mission_id", "m-" + "f" * 32), ("at", "bad"), ("kind", "ACTION_DECISION")):
            with self.store.connection() as db:
                db.execute(f"UPDATE events SET {column}=? WHERE sequence=?", (value, receipt["event_sequence"]))
            self.assert_error("RECEIPT_UNAVAILABLE")
            with self.store.connection() as db:
                original = self.mission["id"] if column == "mission_id" else event[column]
                db.execute(f"UPDATE events SET {column}=? WHERE sequence=?", (original, receipt["event_sequence"]))
        with self.store.connection() as db:
            db.execute("DELETE FROM events WHERE sequence=?", (receipt["event_sequence"],))
        self.assert_error("RECEIPT_UNAVAILABLE")

    def test_missing_mission_does_not_promote_orphaned_receipt(self):
        self.record()
        with self.store.connection() as db:
            db.execute("DELETE FROM missions")
        self.assert_error("RECEIPT_UNAVAILABLE")

    def test_local_transaction_cannot_mix_store_identity_and_receipt(self):
        receipt = self.record()
        with self.store.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
        # Test lookup's transaction independently of the HTTP reader, which now
        # deliberately refuses externally enabled WAL before opening SQLite.
        connection = self.store.connection
        @contextmanager
        def interleaved():
            with connection() as db:
                class Proxy:
                    def execute(_, sql, parameters=()):
                        result = db.execute(sql, parameters)
                        if sql == "SELECT value FROM sync_metadata WHERE key='store_id'":
                            row = result.fetchone()
                            with self.store.connection() as writer:
                                writer.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ("s-" + "f" * 32,))
                                writer.execute("DELETE FROM command_receipts")
                            return SimpleNamespace(fetchone=lambda: row)
                        return result
                yield Proxy()
        with patch.object(self.reader, "connection", interleaved):
            self.assertEqual(lookup(self.reader, self.query)["receipt"], receipt)
        with self.assertRaises(ReceiptLookupError) as caught:
            lookup(self.store, self.query)
        self.assertEqual(caught.exception.code, 'STORE_CHANGED')


class HTTPReceiptTests(unittest.TestCase):
    # Reuse only the loopback fixture/helpers, not the previous test methods.
    setUp = http_tests.HTTPReadTests.setUp
    stop = http_tests.HTTPReadTests.stop
    request = http_tests.HTTPReadTests.request
    json = http_tests.HTTPReadTests.json

    def post_receipt(self, value=None, **kwargs):
        command = cancel_request(self.store, self.mission["id"])
        return self.json("/v1/command-receipt", method="POST",
                         data=query_for(command) if value is None else value, **kwargs)

    def test_found_and_absent_with_canonical_database_unchanged(self):
        status, _, absent = self.post_receipt()
        self.assertEqual((status, absent["status"]), (200, "NOT_FOUND"))
        command = cancel_request(self.store, self.mission["id"])
        receipt = CancelCommands(self.store).submit(command)
        before = self.store.path.read_bytes()
        status, _, found = self.post_receipt()
        self.assertEqual((status, found["receipt"]), (200, receipt))
        self.assertEqual(found["protocol"], "eidolon-http-receipt/1")
        self.assertFalse(found["authorizes_resend"])
        self.assertNotIn("PRIVATE", json.dumps(found))
        self.assertEqual(before, self.store.path.read_bytes())

    def test_invalid_queries_have_a_stable_error(self):
        for query in ({}, {"client_id": "x"}, {**query_for(cancel_request(self.store, self.mission["id"])), "extra": 1}):
            status, _, result = self.post_receipt(query)
            self.assertEqual((status, result["error"]), (400, "INVALID_RECEIPT_QUERY"))

    def test_store_or_mission_conflict_retains_uncertainty(self):
        command = cancel_request(self.store, self.mission["id"])
        CancelCommands(self.store).submit(command)
        query = query_for(command)
        for field, replacement, code in (("store_id", "s-" + "f" * 32, "STORE_CHANGED"),
                                          ("mission_id", "m-" + "f" * 32, "RECEIPT_MISSION_MISMATCH")):
            status, _, error = self.post_receipt({**query, field: replacement})
            self.assertEqual((status, error["error"]), (409, code))
            self.assertNotIn("receipt", error)

    def test_authentication_precedes_lookup_and_no_command_submission(self):
        with patch("eidolon_core.http_api.lookup_receipt", side_effect=AssertionError("no lookup")):
            self.assertEqual(self.post_receipt(auth=False)[0], 401)
            self.assertEqual(self.post_receipt(headers={"Origin": "null"})[0], 403)
            self.assertEqual(self.json("/v1/command-submit", method="POST", data={})[0], 404)

    def test_corruption_has_no_payload_in_response(self):
        command = cancel_request(self.store, self.mission["id"])
        receipt = CancelCommands(self.store).submit(command)
        with self.store.connection() as db:
            db.execute("UPDATE command_receipts SET body=?", (json.dumps({**receipt, "actor": "PRIVATE"}),))
        status, _, result = self.post_receipt()
        self.assertEqual((status, result["error"]), (503, "RECEIPT_UNAVAILABLE"))
        self.assertNotIn("PRIVATE", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
