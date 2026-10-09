# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_cancel.py
# Description : Annulation ciblée depuis le chat : deux missions, doublon, résultat simultané, déjà terminée, injoignable (C-TASK-G100)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import conversation as cv
from eidolon_core import conversation_cancel as cc
from eidolon_core import conversation_store as cs
from eidolon_core.commands import CancelCommands, lookup_receipt
from eidolon_core.contracts import ContractError
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store

CLIENT = {"client_id": "pc", "actor": "toytoy"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.runtime = synthetic_runtime(Store(Path(self.tmp.name) / "state"))
        self.store = self.runtime.store
        self.conv = cs.ConversationStore(self.store, create=True)
        self.cid = self.conv.open(client_id="pc", client_key="k")["conversation_id"]
        self.n = 0

    def mission(self, cid=None, client="pc"):
        """One diagnostic mission created from a human submission in this conversation (not run)."""
        cid = cid or self.cid
        self.n += 1
        turn = self.conv.append_turn(cid, client_id=client, client_turn_key=f"t{self.n}", text="Diagnostique le nas.")["turn"]
        output = json.dumps({"version": 1, "kind": "proposal", "text": "Diagnostic.",
                             "proposal": {"template": cv.DIAGNOSTIC, "parameters": {"target_reference": "nas"}}})
        self.conv.record_reply(cv.decide_reply(turn, output, self.runtime.catalog,
                                               previous_proposal=self.conv.current_proposal(cid)))
        p = self.conv.current_proposal(cid)
        receipt = self.conv.submit(
            {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": client,
             "command_key": f"s{self.n}", "conversation_id": cid, "proposal_id": p["proposal_id"],
             "proposal_version": p["version"], "proposal_sha256": cv.proposal_sha256(p), "actor": "toytoy",
             "reason": "validé"},
            create=lambda request, intent: self.store.create(request, self.runtime.configuration(), intent=intent))
        return receipt["mission_id"]

    def propose(self, mission_id=None, **kwargs):
        return cc.propose(self.conv, self.store, client_id="pc", conversation_id=self.cid, mission_id=mission_id, **kwargs)

    def cancel(self, mission_id, key="c1", sha=None):
        sha = sha or self.propose(mission_id)[2]
        return cc.submit(self.conv, self.store, client=CLIENT, conversation_id=self.cid, mission_id=mission_id,
                         proposal_sha256=sha, command_key=key, reason="plus utile")

    def flagged(self, mission_id):
        return self.store.cancel_requested(mission_id)


class TargetingTests(Base):
    def test_two_active_missions_require_naming_one_and_only_that_one_is_flagged(self):
        a, b = self.mission(), self.mission()
        self.assertEqual(self.propose(), ("CLARIFICATION", "MISSION_AMBIGUOUS", [a, b]))
        kind, proposal, sha, status = self.propose(b)
        self.assertEqual((kind, proposal["mission_id"], status), ("PROPOSAL", b, "NEW"))
        receipt = self.cancel(b)
        self.assertEqual((receipt["cancel_outcome"], self.flagged(a), self.flagged(b)), ("REQUESTED", False, True))
        self.assertEqual(self.runtime.run(a)["status"], "SUCCEEDED")                # the other one is untouched
        self.assertEqual(self.runtime.run(b)["status"], "CANCELLED")
        self.assertEqual(cc.view(receipt, self.store.get(b)), "effect_observed")

    def test_the_digest_is_stable_while_the_mission_changes_and_binds_the_exact_mission(self):
        a, b = self.mission(), self.mission()
        sha_a = self.propose(a)[2]
        with self.assertRaisesRegex(ContractError, "PROPOSAL_CHANGED"):
            self.cancel(b, sha=sha_a)                                              # A's digest never cancels B
        self.assertFalse(self.flagged(b))

    def test_other_client_or_other_conversation_cannot_name_the_mission(self):
        mission = self.mission()
        other = self.conv.open(client_id="pc", client_key="k2")["conversation_id"]
        with self.assertRaisesRegex(ContractError, "MISSION_UNKNOWN"):
            cc.propose(self.conv, self.store, client_id="pc", conversation_id=other, mission_id=mission)
        with self.assertRaisesRegex(ContractError, "MISSION_UNKNOWN"):
            cc.submit(self.conv, self.store, client={"client_id": "intrus", "actor": "x"}, conversation_id=self.cid,
                      mission_id=mission, proposal_sha256=self.propose(mission)[2], command_key="c", reason="x")
        self.assertFalse(self.flagged(mission))

    def test_no_active_mission_and_already_finished(self):
        self.assertEqual(self.propose(), ("CLARIFICATION", "NO_ACTIVE_MISSION", []))
        mission = self.mission()
        self.runtime.run(mission)
        self.assertEqual(self.propose(mission), ("REFUSED", "MISSION_ALREADY_FINISHED", "SUCCEEDED"))
        self.assertEqual(self.propose(), ("CLARIFICATION", "NO_ACTIVE_MISSION", []))

    def test_media_jobs_are_not_available_and_no_engine_interrupt_exists_here(self):
        self.assertEqual(self.propose(target="media_job"), ("NOT_AVAILABLE", "MEDIA_CANCEL_NOT_AVAILABLE"))
        source = inspect.getsource(cc)
        self.assertNotIn("import media", source.replace("media_job", ""))
        self.assertNotIn("/interrupt\"", source)
        self.assertNotIn("urlopen", source)


class RaceTests(Base):
    def test_doubled_request_records_one_flag_and_says_requested_twice(self):
        mission = self.mission()
        first = self.cancel(mission, key="c1")
        self.assertEqual(self.cancel(mission, key="c1"), first)                     # same key: same receipt
        second = self.cancel(mission, key="c2")                                     # a second click, new key
        self.assertEqual((first["cancel_outcome"], second["cancel_outcome"]), ("REQUESTED", "ALREADY_REQUESTED"))
        with self.store.connection() as db:
            kinds = [r[0] for r in db.execute("SELECT kind FROM events WHERE mission_id=? AND kind LIKE 'CANCEL%'",
                                              (mission,))]
        self.assertEqual(kinds, ["CANCEL_REQUESTED", "CANCEL_COMMAND_RECORDED"])
        self.assertEqual({cc.view(r, self.store.get(mission)) for r in (first, second)}, {"request_received"})

    def test_result_arriving_with_the_request_is_kept_and_not_called_cancelled(self):
        mission = self.mission()
        sha = self.propose(mission)[2]                                              # reviewed while active
        self.runtime.run(mission)                                                   # the result lands first
        late = self.cancel(mission, key="late", sha=sha)
        self.assertEqual((late["cancel_outcome"], cc.view(late, self.store.get(mission))),
                         ("ALREADY_TERMINAL", "already_finished"))
        self.assertEqual(self.store.get(mission)["status"], "SUCCEEDED")            # the result is kept
        other = self.mission()
        receipt = self.cancel(other, key="race")                                     # request recorded first...
        with self.store.connection() as db:                                          # ...the worker's final save
            body = json.loads(db.execute("SELECT body FROM missions WHERE id=?", (other,)).fetchone()[0])
            body["status"] = "SUCCEEDED"                                             # committed in the same instant
            db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(body), other))
        self.assertEqual(cc.view(receipt, self.store.get(other)), "finished_without_cancellation")

    def test_unreachable_store_leaves_an_uncertain_state_resolved_by_the_receipt(self):
        mission = self.mission()
        sha = self.propose(mission)[2]
        with patch.object(CancelCommands, "submit", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                self.cancel(mission, key="lost", sha=sha)
        self.assertEqual(cc.view(None, self.store.get(mission)), "uncertain")
        found = lookup_receipt(self.store, store_id=self.conv.store_id, client_id="pc", command_key="lost")
        self.assertEqual((found["status"], self.flagged(mission)), ("NOT_FOUND", False))   # nothing was recorded
        original = CancelCommands.submit

        def recorded_then_lost(self_, value):
            original(self_, value)
            raise ConnectionResetError("answer lost")
        with patch.object(CancelCommands, "submit", recorded_then_lost):
            with self.assertRaises(ConnectionResetError):
                self.cancel(mission, key="lost2", sha=sha)
        found = lookup_receipt(self.store, store_id=self.conv.store_id, client_id="pc", command_key="lost2")
        self.assertEqual((found["status"], found["authorizes_resend"]), ("FOUND", False))
        self.assertEqual(cc.view(found["receipt"], self.store.get(mission)), "request_received")

    def test_a_worker_that_never_reacts_never_shows_an_observed_effect(self):
        mission = self.mission()
        receipt = self.cancel(mission)
        with self.store.connection() as db:
            body = json.loads(db.execute("SELECT body FROM missions WHERE id=?", (mission,)).fetchone()[0])
            body["status"] = "RUNNING"
            db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(body), mission))
        self.assertEqual(cc.view(receipt, self.store.get(mission)), "request_received")


if __name__ == "__main__":
    unittest.main()
