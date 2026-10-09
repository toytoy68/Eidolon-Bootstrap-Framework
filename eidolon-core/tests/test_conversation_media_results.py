# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_media_results.py
# Description : Résultats Image/Vidéo dans la conversation : collecte partielle, mauvais travail, référence copiée, HTML (C-TASK-G101)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from eidolon_core import conversation_media as cm
from eidolon_core import conversation_store as cs
from eidolon_core.contracts import ContractError, digest
from eidolon_core.conversation_media_results import result_view
from eidolon_core.media_agents import prepare
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.store import Store

PNG = b"\x89PNG\r\n\x1a\nsynthetic source"
HOSTILE = '<img src=x onerror="alert(1)"> Le phare est <b>rouge</b>.'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.conv = cs.ConversationStore(Store(base / "state"), create=True)
        self.root = base / "artifacts"; initialize(self.root)
        self.artifacts = ArtifactStore(self.root)
        self.cid = self.conv.open(client_id="pc", client_key="k")["conversation_id"]
        self.source = self.artifacts.import_bytes(PNG, display_name="phare.png")["reference"]
        self.conv.attach(owner_client_id="pc", conversation_id=self.cid, reference=self.source,
                         verify=lambda r: cm.check_artifact(self.artifacts, r))

    def proposal(self, operation="edit", prompt="Ajoute un ciel étoilé"):
        self.turns = getattr(self, "turns", 0) + 1
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key=f"t{self.turns}",
                                     text="Retouche la photo")["turn"]
        parameters = {"prompt": prompt} if operation == "analyze" else {"prompt": prompt, "format": "square"}
        if operation != "create":
            parameters["artifact_id"] = self.source["artifact_id"]
        kind, value = cm.propose(self.conv, turn, {"template": "media.image." + operation, "parameters": parameters},
                                 owner_client_id="pc")
        self.assertEqual(kind, "PROPOSAL")
        return value

    def job(self, proposal, state="OUTPUTS_IMPORTED_UNVERIFIED", **extra):
        return {"schema": "media-job/1", "id": "media-" + "1" * 32, "state": state,
                "request": prepare(cm.media_request(proposal)), "automatic_retry": False, **extra}

    def output(self, job_id, collection_id, index=0, name="sortie.png"):
        return self.artifacts.import_bytes(PNG + bytes([index]), display_name=name, provenance={
            "kind": "comfy-output", "job_id": job_id, "prompt_id": "p1", "node_id": "9", "output_index": index,
            "collection_id": collection_id})

    def collection(self, job, manifests, state="OUTPUTS_IMPORTED_UNVERIFIED", expected=None):
        return {"schema": "media-collection/1", "id": "mc-" + "2" * 32, "job_id": job["id"], "state": state,
                "store_id": self.artifacts.store_id, "artifacts": manifests,
                "expected_outputs": expected if expected is not None else [{}] * len(manifests)}

    def view(self, proposal, job, viewer="pc", **kwargs):
        return result_view(proposal, job, conversations=self.conv, artifact_store=self.artifacts,
                           viewer_client_id=viewer, **kwargs)


class ResultViewTests(Base):
    def test_complete_collection_lists_verified_outputs_with_provenance_and_no_success(self):
        p = self.proposal(); job = self.job(p)
        outputs = [self.output(job["id"], "mc-" + "2" * 32, i) for i in range(2)]
        view = self.view(p, job, collection=self.collection(job, outputs))
        self.assertEqual((view["binding"], view["stage"], view["success_claim"], view["open_action"]),
                         ("MATCHED", "result_unverified", False, "NOT_AVAILABLE"))
        self.assertEqual([o["verification"] for o in view["outputs"]], ["hash_verified"] * 2)
        self.assertEqual(view["outputs"][1]["provenance"], {"job_id": job["id"], "node_id": "9", "output_index": 1,
                                                             "collection_id": "mc-" + "2" * 32})
        self.assertEqual(view["source"], {"artifact_id": self.source["artifact_id"], "verification": "hash_verified"})
        self.assertFalse(any(o["content_verified"] for o in view["outputs"]))
        self.assertNotIn(str(self.root), json.dumps(view))

    def test_partial_collection_is_said_partial_and_keeps_what_was_imported(self):
        p = self.proposal(); job = self.job(p, state="QUEUED")
        first = self.output(job["id"], "mc-" + "2" * 32)
        view = self.view(p, job, collection=self.collection(job, [first], state="COLLECTION_INCOMPLETE",
                                                             expected=[{}, {}, {}]))
        self.assertEqual(view["collection"], {"state": "COLLECTION_INCOMPLETE", "expected": 3, "imported": 1,
                                              "partial": True})
        self.assertEqual((view["stage"], len(view["outputs"])), ("unknown_effect", 1))

    def test_inaccessible_source_attachment_and_modified_output_are_shown_honestly(self):
        p = self.proposal(); job = self.job(p)
        out = self.output(job["id"], "mc-" + "2" * 32)
        shutil.rmtree(self.root / self.source["artifact_id"])
        payload = self.root / out["reference"]["artifact_id"] / "payload"
        body = bytearray(payload.read_bytes()); body[-1] ^= 1; payload.write_bytes(bytes(body))
        view = self.view(p, job, collection=self.collection(job, [out]))
        self.assertEqual(view["source"]["verification"], "unavailable")
        self.assertEqual(view["outputs"][0]["verification"], "modified")

    def test_result_of_another_job_is_never_shown(self):
        p = self.proposal(); other = self.proposal("edit", "Rends-le en noir et blanc")
        job = self.job(other)                                                        # another proposal's job
        self.assertEqual((self.view(p, job)["binding"], self.view(p, job)["outputs"]), ("WRONG_JOB", []))
        mine = self.job(p)
        foreign = {**self.collection(mine, []), "job_id": "media-" + "9" * 32}
        self.assertEqual(self.view(p, mine, collection=foreign)["collection"]["state"], "WRONG_JOB")

    def test_copied_reference_without_rights_is_excluded_and_another_client_sees_nothing(self):
        p = self.proposal(); job = self.job(p)
        good = self.output(job["id"], "mc-" + "2" * 32)
        copied = dict(self.artifacts.read(self.source)[1])                          # the source, no job provenance
        alien = self.output("media-" + "8" * 32, "mc-" + "2" * 32, 1)                # another job's output
        view = self.view(p, job, collection=self.collection(job, [good, copied, alien]))
        self.assertEqual(([o["artifact_id"] for o in view["outputs"]], view["excluded_outputs"]),
                         ([good["reference"]["artifact_id"]], 2))
        intruder = self.conv.open(client_id="intrus", client_key="k")
        with self.assertRaisesRegex(ContractError, "MEDIA_RESULT_UNKNOWN"):
            self.view(p, job, viewer="intrus")
        self.assertTrue(intruder)

    def test_analysis_text_with_html_stays_an_unverified_observation(self):
        p = self.proposal("analyze", "Décris la photo")
        job = self.job(p, state="RESULT_UNVERIFIED", result={"state": "RESULT_UNVERIFIED", "text": HOSTILE})
        view = self.view(p, job)
        self.assertEqual(view["observation"], {"text": HOSTILE, "verified": False})
        self.assertEqual((view["stage"], view["success_claim"]), ("result_unverified", False))

    def test_old_history_without_structured_request_shows_its_state_only(self):
        p = self.proposal()
        legacy = {"schema": "media-job/1", "id": "media-" + "3" * 32, "state": "ENGINE_COMPLETED_UNVERIFIED"}
        view = self.view(p, legacy)
        self.assertEqual((view["binding"], view["stage"], view["outputs"]), ("LEGACY_UNVERIFIABLE", "result_unverified", []))
        unknown = {"schema": "media-job/1", "id": "media-" + "4" * 32, "state": "ETAT_FUTUR", "request": {}}
        self.assertEqual(self.view(p, unknown)["stage"], "received_as_is")
        self.assertEqual(self.view(p, {"schema": "autre"})["binding"], "UNREADABLE")



class LinkAndRouteTests(Base):
    """The page path: operator links a job, the route reads it fresh, never returns a path."""

    def write_job(self, job, name="job"):
        from eidolon_core.media_agents import write_record
        folder = Path(self.tmp.name) / name
        folder.mkdir(mode=0o700)
        write_record(folder, job)
        return folder

    def write_collection(self, collection, name="collecte"):
        from eidolon_core.media_agents import write_record
        folder = Path(self.tmp.name) / name
        folder.mkdir(mode=0o700)
        write_record(folder, collection)
        return folder

    def test_link_then_route_shows_fresh_views_without_paths(self):
        from eidolon_core.conversation_media_results import link_job, views_for
        p = self.proposal(); job = self.job(p)
        out = self.output(job["id"], "mc-" + "2" * 32)
        job_dir = self.write_job(job)
        coll_dir = self.write_collection(self.collection(job, [out]))
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(job_dir),
                 artifact_root=str(self.root), collection_dir=str(coll_dir))
        self.assertEqual(link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                                  job_dir=str(job_dir), artifact_root=str(self.root), collection_dir=str(coll_dir)),
                         digest(p))                                                      # idempotent
        views = views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)
        self.assertEqual([(v["binding"], v["outputs"][0]["verification"]) for v in views], [("MATCHED", "hash_verified")])
        text = json.dumps(views)
        for private in (str(job_dir), str(coll_dir), str(self.root), self.tmp.name):
            self.assertNotIn(private, text)
        # Read fresh: the output modified afterwards is seen as modified on the next call.
        payload = self.root / out["reference"]["artifact_id"] / "payload"
        body = bytearray(payload.read_bytes()); body[-1] ^= 1; payload.write_bytes(bytes(body))
        self.assertEqual(views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]["outputs"][0]
                         ["verification"], "modified")
        # Job record gone: still listed, honestly unreadable.
        (job_dir / "job.json").unlink()
        self.assertEqual(views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]["binding"], "UNREADABLE")
        self.assertEqual(views_for(self.conv, owner_client_id="intrus", conversation_id=self.cid), [])

    def test_link_refuses_another_job_another_owner_and_relinking(self):
        from eidolon_core.conversation_media_results import link_job
        p = self.proposal(); other = self.proposal("edit", "Rends-le en noir et blanc")
        wrong = self.write_job(self.job(other), "autre")
        with self.assertRaisesRegex(ContractError, "MEDIA_JOB_MISMATCH"):
            link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(wrong),
                     artifact_root=str(self.root))
        right = self.write_job(self.job(p))
        with self.assertRaisesRegex(ContractError, "MEDIA_RESULT_UNKNOWN|CONVERSATION_UNKNOWN"):
            link_job(self.conv, owner_client_id="intrus", conversation_id=self.cid, proposal=p, job_dir=str(right),
                     artifact_root=str(self.root))
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(right),
                 artifact_root=str(self.root))
        with self.assertRaisesRegex(ContractError, "MEDIA_LINK_CONFLICT"):
            self.conv.link_media(owner_client_id="pc", conversation_id=self.cid, proposal=p, job_dir=str(wrong),
                                 artifact_root=str(self.root), job_id=self.job(p)["id"])
        with self.assertRaisesRegex(ContractError, "MEDIA_JOB_UNAVAILABLE"):
            link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                     job_dir=str(Path(self.tmp.name) / "absent"), artifact_root=str(self.root))

    def test_api_route_and_operator_command(self):
        import os, subprocess, sys
        from eidolon_core.client_credentials import ClientCredentials
        from eidolon_core.conversation_api import ConversationAPI
        from eidolon_core.diagnostics import synthetic_runtime
        from eidolon_core.dialogue import SimulatedDialogueModel
        runtime = synthetic_runtime(self.conv.store)
        key = ClientCredentials(self.conv.store, create=True).pair(client_id="pc", actor="toytoy")["token"]
        api = ConversationAPI(runtime, dialogue_model=SimulatedDialogueModel(runtime.catalog))
        headers = {"Authorization": ["Bearer " + key], "Content-Type": ["application/json"]}
        post = lambda body: api.handle("POST", "/v1/conversations/media_results", headers, json.dumps(body).encode())
        self.assertEqual(post({"conversation_id": self.cid})[1]["results"], [])
        p = self.proposal(); job_dir = self.write_job(self.job(p))
        proposal_file = Path(self.tmp.name) / "proposition.json"; proposal_file.write_text(json.dumps(p))
        src = str(Path(__file__).resolve().parents[1] / "src")
        done = subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state",
                               str(self.conv.store.directory), "media-link", "--client-id", "pc", "--conversation-id",
                               self.cid, "--proposal", str(proposal_file), "--job", str(job_dir),
                               "--artifact-root", str(self.root)], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(json.loads(done.stdout)["status"], "LINKED", done.stdout + done.stderr)
        status, body = post({"conversation_id": self.cid})
        self.assertEqual((status, [r["binding"] for r in body["results"]]), (200, ["MATCHED"]))
        self.assertNotIn(self.tmp.name, json.dumps(body))
        other = ClientCredentials(self.conv.store).pair(client_id="intrus", actor="x")["token"]
        status, refused = api.handle("POST", "/v1/conversations/media_results",
                                     {**headers, "Authorization": ["Bearer " + other]},
                                     json.dumps({"conversation_id": self.cid}).encode())
        self.assertEqual((status, refused["error"]), (404, "CONVERSATION_UNKNOWN"))


    def test_equal_request_with_replaced_job_id_never_shows_foreign_observation(self):
        from eidolon_core.conversation_media_results import link_job, views_for
        from eidolon_core.media_agents import write_record
        p = self.proposal("analyze")
        job = self.job(p, state="RESULT_UNVERIFIED", result={"state": "RESULT_UNVERIFIED", "text": "original"})
        folder = self.write_job(job)
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                 job_dir=str(folder), artifact_root=str(self.root))
        original = views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertEqual((original["binding"], original["observation"]["text"]), ("MATCHED", "original"))
        other = {**job, "id": "media-" + "9" * 32,
                 "result": {"state": "RESULT_UNVERIFIED", "text": "foreign observation"}}
        write_record(folder, other)
        reopened = cs.ConversationStore(self.conv.store)
        view = views_for(reopened, owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertEqual((view["binding"], view["job_id"]), ("WRONG_JOB", job["id"]))
        self.assertEqual((view["outputs"], view["observation"], view["state_received"], view["source"]),
                         ([], None, None, None))
        with self.assertRaisesRegex(ContractError, "MEDIA_LINK_CONFLICT"):
            link_job(reopened, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                     job_dir=str(folder), artifact_root=str(self.root))
        write_record(folder, job)
        self.assertEqual(views_for(reopened, owner_client_id="pc", conversation_id=self.cid)[0]["binding"],
                         "MATCHED")

    def test_equal_request_and_matching_foreign_collection_are_both_excluded(self):
        from eidolon_core.conversation_media_results import link_job, views_for
        from eidolon_core.media_agents import write_record
        p = self.proposal()
        job = self.job(p); collection_id = "mc-" + "2" * 32
        output = self.output(job["id"], collection_id)
        folder = self.write_job(job)
        coll = self.write_collection(self.collection(job, [output]))
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                 job_dir=str(folder), artifact_root=str(self.root), collection_dir=str(coll))
        other = {**job, "id": "media-" + "9" * 32}
        foreign = self.output(other["id"], collection_id, index=1, name="foreign.png")
        write_record(folder, other); write_record(coll, self.collection(other, [foreign]))
        view = views_for(self.conv, owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertEqual((view["binding"], view["outputs"], view["collection"]), ("WRONG_JOB", [], None))
        self.assertNotIn("foreign.png", json.dumps(view))

    def test_v4_link_migration_preserves_data_without_adopting_the_current_job(self):
        import sqlite3
        from eidolon_core import conversation_storage as storage
        from eidolon_core.conversation_media_results import link_job, views_for
        p = self.proposal(); job = self.job(p); folder = self.write_job(job)
        link_job(self.conv, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                 job_dir=str(folder), artifact_root=str(self.root))
        with sqlite3.connect(self.conv.path) as db:
            row = db.execute("SELECT conversation_id, proposal_sha256, owner_client_id, proposal, "
                             "job_dir, collection_dir, artifact_root, linked_at FROM media_links").fetchone()
            db.execute("DROP TABLE media_links")
            db.execute(cs.MEDIA_LINKS_TABLE)                # exact v4 layout, no pinned id
            db.execute("INSERT INTO media_links VALUES (?,?,?,?,?,?,?,?)", row)
            db.execute("UPDATE meta SET value=? WHERE key='schema'", (cs.SCHEMAS[4],))
            db.execute("PRAGMA user_version=4")
        with self.assertRaisesRegex(ContractError, "MIGRATION_REQUIRED"):
            cs.ConversationStore(self.conv.store)
        saved = Path(self.tmp.name) / "v4-backup.sqlite3"
        migrated = storage.migrate_with_backup(self.conv.store, saved)
        self.assertEqual((migrated["from_version"], migrated["version"]), (4, cs.VERSION))
        self.assertEqual(storage.inspect(saved)["rows"]["media_links"], 1)
        reopened = cs.ConversationStore(self.conv.store)
        link = reopened.media_links(owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertIsNone(link["job_id"])
        self.assertEqual(link["proposal"], p)
        view = views_for(reopened, owner_client_id="pc", conversation_id=self.cid)[0]
        self.assertEqual((view["binding"], view["job_id"], view["outputs"], view["observation"]),
                         ("LEGACY_UNVERIFIABLE", None, [], None))
        with self.assertRaisesRegex(ContractError, "MEDIA_LINK_CONFLICT"):
            link_job(reopened, owner_client_id="pc", conversation_id=self.cid, proposal=p,
                     job_dir=str(folder), artifact_root=str(self.root))


if __name__ == "__main__":
    unittest.main()
