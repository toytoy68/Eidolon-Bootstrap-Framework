# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_media_flow.py
# Description : Dialogue → proposition média persistée → soumission authentifiée vers la file Codex (C-TASK-G122/G123)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from eidolon_core import conversation as cv
from eidolon_core import conversation_media as cm
from eidolon_core import conversation_storage as st
from eidolon_core import conversation_store as cs
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.contracts import digest
from eidolon_core.conversation_api import ConversationAPI
from eidolon_core.conversation_media_results import link_job, views_for
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.http_api import open_media_workspace
from eidolon_core.media_agents import prepare, write_record
from eidolon_core.media_workspace import initialize as workspace_init
from eidolon_core.store import Store

PNG = b"\x89PNG\r\n\x1a\nsynthetic flow source"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.runtime = synthetic_runtime(Store(base / "state"))
        self.conv = cs.ConversationStore(self.runtime.store, create=True)
        credentials = ClientCredentials(self.runtime.store, create=True)
        self.key = credentials.pair(client_id="pc", actor="toytoy")["token"]
        self.other = credentials.pair(client_id="intrus", actor="autre")["token"]
        made = workspace_init(base / "media", state=str(base / "state"))
        self.worker, self.artifacts = open_media_workspace(str(base / "media"), made["workspace_id"])
        self.api = self.make_api(self.worker, self.artifacts)
        self.cid = self.post("open", {"client_key": "k"})[1]["conversation_id"]
        self.n = 0

    def make_api(self, worker=None, artifacts=None):
        return ConversationAPI(self.runtime, dialogue_model=SimulatedDialogueModel(self.runtime.catalog),
                               media_worker=worker, media_artifacts=artifacts)

    def post(self, route, body, key=None, api=None):
        headers = {"Authorization": ["Bearer " + (key or self.key)], "Content-Type": ["application/json"]}
        return (api or self.api).handle("POST", "/v1/conversations/" + route, headers, json.dumps(body).encode())

    def say(self, text, api=None):
        self.n += 1
        status, body = self.post("turn", {"conversation_id": self.cid, "client_turn_key": f"t{self.n}", "text": text},
                                 api=api)
        self.assertEqual(status, 200, body)
        return body["reply"]

    def attach(self):
        ref = self.artifacts.import_bytes(PNG, display_name="phare.png")["reference"]
        self.conv.attach(owner_client_id="pc", conversation_id=self.cid, reference=ref,
                         verify=lambda r: cm.check_artifact(self.artifacts, r))
        return ref

    def submission(self, reply, key="m1", **changes):
        p = reply["proposal"]
        value = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": "pc",
                 "command_key": key, "conversation_id": self.cid, "proposal_id": p["proposal_id"],
                 "proposal_version": p["version"], "proposal_sha256": reply["proposal_sha256"], "actor": "toytoy",
                 "reason": "Je veux cette image."}
        value.update(changes)
        return value


class DialogueTests(Base):
    def test_media_proposal_is_frozen_by_core_persisted_and_current(self):
        ref = self.attach()
        reply = self.say("Retouche la photo : ajoute un ciel étoilé")
        p = reply["proposal"]
        self.assertEqual((reply["kind"], p["protocol"], p["operation"], p["artifact"]),
                         ("PROPOSAL", "eidolon-media-proposal/1", "edit", ref))
        self.assertEqual(reply["proposal_sha256"], digest(p))
        self.assertEqual(self.conv.current_proposal(self.cid), p)
        self.assertEqual(self.conv.media_proposals(self.cid), [p])
        again = self.say("Crée une image : un phare au crépuscule")["proposal"]
        self.assertEqual((again["version"], again["supersedes_sha256"], again["proposal_id"]),
                         (2, digest(p), p["proposal_id"]))

    def test_edit_without_attachment_is_a_clarification(self):
        reply = self.say("Retouche la photo : plus chaud")
        self.assertEqual((reply["kind"], reply["proposal"]), ("CLARIFICATION", None))

    def test_a_model_supplying_a_path_or_a_full_reference_gets_nothing_frozen(self):
        ref = self.attach()
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key="x", text="retouche")["turn"]
        freeze = lambda t, s: cm.propose(self.conv, t, s, owner_client_id="pc")
        for parameters, note in (({"prompt": "x", "format": "square", "source": "/etc/passwd"}, "MEDIA_PARAMETERS_INVALID"),
                                 ({"prompt": "x", "format": "square", "artifact_id": ref}, "MEDIA_ARTIFACT_NOT_ATTACHED"),
                                 ({"prompt": "x", "format": "square", "artifact_id": "/home/x/photo.png"},
                                  "MEDIA_ARTIFACT_NOT_ATTACHED")):
            output = json.dumps({"version": 1, "kind": "proposal", "text": "ok",
                                 "proposal": {"template": "media.image.edit", "parameters": parameters}})
            reply = cv.decide_reply(turn, output, self.runtime.catalog, media=freeze)
            self.assertEqual((reply["kind"], reply["core_note"], reply["proposal"]), ("CLARIFICATION", note, None))
        self.assertEqual(self.conv.media_proposals(self.cid), [])

    def test_without_a_worker_no_media_is_offered(self):
        plain = self.make_api()
        reply = self.say("Crée une image : un phare", api=plain)
        self.assertNotEqual(reply["kind"], "PROPOSAL")
        self.assertEqual(self.conv.media_proposals(self.cid), [])


class SubmissionTests(Base):
    def test_submission_gives_a_durable_ticket_and_launches_nothing(self):
        reply = self.say("Crée une image : un phare")
        status, ticket = self.post("submit", self.submission(reply))
        self.assertEqual((status, ticket["state"], ticket["execution"], ticket["kind"]),
                         (200, "ACCEPTED", "NOT_STARTED_BY_SUBMISSION", "media"))
        self.assertEqual(list((Path(self.tmp.name) / "media" / "worker").glob(ticket["ticket_id"])), [])   # no job
        self.assertNotIn(self.tmp.name, json.dumps(ticket))
        self.assertNotIn("phare", json.dumps(ticket))                                   # no prompt in the receipt
        self.assertEqual(self.post("submit", self.submission(reply))[1]["ticket_id"], ticket["ticket_id"])   # replay
        status, refused = self.post("submit", self.submission(reply, key="m2"))
        self.assertEqual((status, refused["error"]), (409, "MEDIA_PROPOSAL_ALREADY_SUBMITTED"))
        status, reused = self.post("submit", self.submission(reply, reason="Autre motif"))
        self.assertEqual((status, reused["error"]), (409, "MEDIA_COMMAND_KEY_REUSED"))
        found = self.post("receipt", {"command_key": "m1"})[1]
        self.assertEqual((found["status"], found["receipt"]["ticket_id"], found["authorizes_resend"]),
                         ("FOUND", ticket["ticket_id"], False))

    def test_concurrent_double_click_gives_one_ticket(self):
        reply = self.say("Crée une image : un phare")
        answers = []
        threads = [threading.Thread(target=lambda: answers.append(self.post("submit", self.submission(reply))))
                   for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        ok = [a for s, a in answers if s == 200]
        self.assertTrue(ok)
        self.assertEqual({a["ticket_id"] for a in ok}, {ok[0]["ticket_id"]})
        self.assertEqual(len(self.worker.tickets(client_id="pc")), 1)
        self.assertTrue(all(a.get("error") in (None, "MEDIA_WORKER_BUSY") for s, a in answers))

    def test_older_version_other_owner_and_mixed_chains_are_refused(self):
        first = self.say("Crée une image : un phare")
        second = self.say("Crée une image : un phare au crépuscule")
        status, stale = self.post("submit", self.submission(first))
        self.assertEqual((status, stale["error"]), (409, "PROPOSAL_STALE"))
        status, foreign = self.post("submit", self.submission(second, client_id="intrus", actor="autre"), key=self.other)
        self.assertEqual((status, foreign["error"]), (404, "CONVERSATION_UNKNOWN"))
        mission = self.say("Diagnostique le nas.")                                    # a later mission proposal
        status, media_now_stale = self.post("submit", self.submission(second, key="m3"))
        self.assertEqual((status, media_now_stale["error"]), (409, "PROPOSAL_STALE"))
        later = self.say("Crée une image : encore un phare")                         # then media again
        status, mission_stale = self.post("submit", self.submission(mission, key="d1"))
        self.assertEqual((status, mission_stale["error"]), (409, "PROPOSAL_STALE"))
        self.assertEqual(self.post("submit", self.submission(later, key="m4"))[0], 200)
        self.assertEqual(len(self.worker.tickets(client_id="pc")), 1)

    def test_without_a_worker_a_media_submission_records_nothing(self):
        reply = self.say("Crée une image : un phare")
        status, body = self.post("submit", self.submission(reply), api=self.make_api())
        self.assertEqual((status, body["error"]), (503, "MEDIA_WORKER_NOT_CONFIGURED"))
        self.assertEqual(self.worker.tickets(client_id="pc"), [])


class ResultTests(Base):
    def test_queue_results_are_listed_for_this_conversation_only(self):
        reply = self.say("Crée une image : un phare")
        ticket = self.post("submit", self.submission(reply))[1]
        body = self.post("media_results", {"conversation_id": self.cid})[1]
        self.assertEqual([(t["receipt"]["ticket_id"], t["observation"], t["result"]) for t in body["tickets"]],
                         [(ticket["ticket_id"], "NOT_STARTED", None)])
        other = self.post("open", {"client_key": "autre-conversation"})[1]["conversation_id"]
        self.assertEqual(self.post("media_results", {"conversation_id": other})[1]["tickets"], [])
        self.assertEqual(self.post("media_results", {"conversation_id": self.cid}, key=self.other)[0], 404)
        self.assertNotIn(self.tmp.name, json.dumps(body))

    def test_g123_r1_operator_link_refuses_another_job_with_the_same_request(self):
        ref = self.attach()
        p = self.say("Retouche la photo : ajoute un ciel étoilé")["proposal"]
        job = {"schema": "media-job/1", "id": "media-" + "1" * 32, "state": "QUEUED",
               "request": prepare(cm.media_request(p)), "automatic_retry": False}
        folder = Path(self.tmp.name) / "job"; folder.mkdir(mode=0o700); write_record(folder, job)
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(folder),
                 artifact_root=str(Path(self.tmp.name) / "media" / "artifacts"))
        self.assertEqual(views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]["binding"], "MATCHED")
        write_record(folder, {**job, "id": "media-" + "2" * 32, "state": "ENGINE_COMPLETED_UNVERIFIED"})
        swapped = views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertEqual((swapped["binding"], swapped["outputs"], swapped["state_received"]), ("WRONG_JOB", [], None))
        self.assertTrue(ref)


class StorageTests(Base):
    def test_g099_r1_new_tables_are_part_of_the_logical_digest(self):
        path = self.conv.path
        with sqlite3.connect(path) as db:
            before = st.logical_digest(db)
        self.say("Crée une image : un phare")
        with sqlite3.connect(path) as db:
            after = st.logical_digest(db)
        self.assertNotEqual(before[0], after[0])
        self.assertEqual(after[1]["media_proposals"], 1)

    def test_v4_to_v5_migration_keeps_links_and_marks_them_to_redo(self):
        ref = self.attach()
        p = self.say("Retouche la photo : ajoute un ciel étoilé")["proposal"]
        folder = Path(self.tmp.name) / "job"; folder.mkdir(mode=0o700)
        write_record(folder, {"schema": "media-job/1", "id": "media-" + "1" * 32, "state": "QUEUED",
                              "request": prepare(cm.media_request(p)), "automatic_retry": False})
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(folder),
                 artifact_root=str(Path(self.tmp.name) / "media" / "artifacts"))
        with sqlite3.connect(self.conv.path) as db:              # rewrite as an exact v4 store
            db.executescript("""
                CREATE TABLE old_links AS SELECT conversation_id, proposal_sha256, owner_client_id, proposal, job_dir,
                    collection_dir, artifact_root, linked_at FROM media_links;
                DROP TABLE media_links; DROP TABLE media_proposals;
                %s;
                INSERT INTO media_links SELECT * FROM old_links; DROP TABLE old_links;
                UPDATE meta SET value='eidolon-conversation-store/4' WHERE key='schema'; PRAGMA user_version=4;
            """ % cs.MEDIA_LINKS_TABLE)
        result = st.migrate_with_backup(self.runtime.store, Path(self.tmp.name) / "backup-v4.sqlite3")
        self.assertEqual((result["from_version"], result["version"]), (4, cs.VERSION))
        conv = cs.ConversationStore(self.runtime.store)
        self.assertEqual([v["binding"] for v in views_for(conv, owner_client_id="pc", conversation_id=self.cid)],
                         ["LEGACY_UNVERIFIABLE"])
        self.assertTrue(ref)


if __name__ == "__main__":
    unittest.main()
