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
from eidolon_core.contracts import ContractError
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


if __name__ == "__main__":
    unittest.main()
