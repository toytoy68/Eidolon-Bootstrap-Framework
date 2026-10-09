# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_media.py
# Description : Tests contractuels conversation ↔ agents média (C-TASK-G094), avec la validation de Codex
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import unittest

from eidolon_core import conversation as cv
from eidolon_core import conversation_media as cm
from eidolon_core.contracts import ContractError, digest
from eidolon_core.media_agents import prepare

STORE, CONV, OTHER_CONV = "s-" + "1" * 32, "c-" + "2" * 32, "c-" + "3" * 32
REF = {"schema": "media-artifact-ref/1", "store_id": "mas-" + "a" * 32, "artifact_id": "ma-" + "b" * 32,
       "sha256": "c" * 64}


def turn(text="Retouche la photo du phare"):
    return {"protocol": cv.TURN_PROTOCOL, "store_id": STORE, "conversation_id": CONV, "turn_id": "t-" + "4" * 32,
            "sequence": 1, "role": "user", "text": text, "client_id": "pc", "client_turn_key": "k",
            "previous_turn_sha256": None}


def attached(owner="pc", conversation=CONV, reference=REF):
    return cm.attachment(store_id=STORE, owner_client_id=owner, conversation_id=conversation, reference=reference)


def suggest(template, **parameters):
    return {"template": template, "parameters": parameters}


class FreezeTests(unittest.TestCase):
    def test_create_needs_no_artifact_and_yields_a_request_codex_accepts(self):
        kind, p = cm.freeze(turn(), suggest("media.image.create", prompt="Un phare au crépuscule", format="landscape"),
                            [], owner_client_id="pc")
        self.assertEqual(kind, "PROPOSAL")
        self.assertEqual((p["agent"], p["operation"], p["artifact"], p["executor"], p["authorizes_execution"]),
                         ("image", "create", None, "eidolon-media", False))
        request = cm.media_request(p)
        self.assertEqual(prepare(request)["prompt"], "Un phare au crépuscule")     # Codex's own validation
        self.assertNotIn("source", request)

    def test_edit_uses_the_attachment_recorded_by_core_never_the_model_reference(self):
        kind, p = cm.freeze(turn(), suggest("media.image.edit", prompt="Plus chaud", artifact_id=REF["artifact_id"],
                                            format="square"), [attached()], owner_client_id="pc")
        self.assertEqual((kind, p["artifact"]), ("PROPOSAL", REF))
        self.assertEqual(cm.media_request(p)["artifact"], REF)

    def test_unattached_foreign_or_path_like_artifacts_are_never_used(self):
        cases = (("absent", [], {"artifact_id": REF["artifact_id"]}),
                 ("autre propriétaire", [attached(owner="pc-autre")], {"artifact_id": REF["artifact_id"]}),
                 ("autre conversation", [attached(conversation=OTHER_CONV)], {"artifact_id": REF["artifact_id"]}),
                 ("référence complète fournie par le modèle", [attached()], {"artifact_id": REF}),
                 ("chemin", [attached()], {"artifact_id": "/home/toytoy/photo.png"}))
        for name, attachments, extra in cases:
            with self.subTest(name=name):
                kind, code = cm.freeze(turn(), suggest("media.image.analyze", prompt="Décris", **extra), attachments,
                                       owner_client_id="pc")
                self.assertEqual((kind, code), ("CLARIFICATION", "MEDIA_ARTIFACT_NOT_ATTACHED"))

    def test_a_source_path_or_invalid_parameters_ask_again(self):
        for name, suggestion in (
                ("source", suggest("media.image.analyze", prompt="Décris", source="/etc/passwd")),
                ("format invalide", suggest("media.image.create", prompt="x", format="panorama")),
                ("durée invalide", suggest("media.video.create", prompt="x", format="landscape", duration_seconds=60)),
                ("durée pour une image", suggest("media.image.create", prompt="x", format="square", duration_seconds=5)),
                ("artefact pour une création", suggest("media.image.create", prompt="x", format="square",
                                                       artifact_id=REF["artifact_id"])),
                ("sans texte", suggest("media.image.create", format="square"))):
            with self.subTest(name=name):
                self.assertEqual(cm.freeze(turn(), suggestion, [attached()], owner_client_id="pc"),
                                 ("CLARIFICATION", "MEDIA_PARAMETERS_INVALID"))

    def test_unknown_media_templates_are_out_of_scope(self):
        for template in ("media.audio.create", "media.image.delete", "shell.run", None):
            with self.subTest(template=template):
                self.assertEqual(cm.freeze(turn(), suggest(template, prompt="x"), [], owner_client_id="pc"),
                                 ("OUT_OF_SCOPE", "MEDIA_TEMPLATE_UNSUPPORTED"))

    def test_versions_supersede(self):
        _, v1 = cm.freeze(turn(), suggest("media.video.create", prompt="Vague", format="landscape", duration_seconds=5),
                          [], owner_client_id="pc")
        _, v2 = cm.freeze(turn(), suggest("media.video.create", prompt="Vague", format="portrait", duration_seconds=10),
                          [], owner_client_id="pc", previous=v1)
        self.assertEqual((v2["proposal_id"], v2["version"], v2["supersedes_sha256"]), (v1["proposal_id"], 2, digest(v1)))


class ProposalAndSubmissionTests(unittest.TestCase):
    def setUp(self):
        _, self.p = cm.freeze(turn(), suggest("media.image.edit", prompt="Plus chaud", artifact_id=REF["artifact_id"],
                                              format="square"), [attached()], owner_client_id="pc")

    def submission(self, **changes):
        value = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": STORE, "client_id": "pc", "command_key": "m1",
                 "conversation_id": CONV, "proposal_id": self.p["proposal_id"], "proposal_version": 1,
                 "proposal_sha256": digest(self.p), "actor": "toytoy", "reason": "retouche demandée"}
        value.update(changes)
        return value

    def test_tampered_media_proposals_are_refused(self):
        for key, value in (("authorizes_execution", True), ("success_claim", "SUCCEEDED"), ("executor", "shell"),
                           ("artifact", None), ("artifact", {**REF, "path": "/tmp/x"}), ("prompt", "  Plus chaud  "),
                           ("agent", "audio")):
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ContractError, "INVALID_MEDIA"):
                cm.validate_proposal({**self.p, key: value})

    def test_only_the_owner_and_the_latest_unchanged_proposal_can_be_submitted(self):
        self.assertEqual(cm.check_submission(self.submission(), self.p)["command_key"], "m1")
        for changes, code in (({"client_id": "pc-autre"}, "CLIENT_MISMATCH"), ({"proposal_version": 2}, "PROPOSAL_STALE"),
                              ({"proposal_sha256": "0" * 64}, "PROPOSAL_CHANGED"),
                              ({"conversation_id": OTHER_CONV}, "PROPOSAL_UNKNOWN")):
            with self.subTest(code=code), self.assertRaisesRegex(ContractError, code):
                cm.check_submission(self.submission(**changes), self.p)

    def test_attachments_are_exact_and_reference_shaped(self):
        for bad in ({**REF, "path": "/tmp/x"}, {**REF, "sha256": "x"}, {**REF, "schema": "other/1"}, "/tmp/photo.png"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ContractError, "INVALID_MEDIA"):
                attached(reference=bad)


class StageTests(unittest.TestCase):
    def test_no_media_state_is_ever_a_success(self):
        for state in ("LOCAL_DRAFT", "INTENT", "QUEUED", "ENGINE_COMPLETED_UNVERIFIED", "OUTPUTS_IMPORTED_UNVERIFIED",
                      "RESULT_UNVERIFIED", "REVIEW_REQUIRED", "COLLECTION_INCOMPLETE"):
            with self.subTest(state=state):
                self.assertNotIn(cm.stage(state), ("result", "succeeded", "SUCCEEDED"))
        self.assertEqual(cm.stage("OUTPUTS_IMPORTED_UNVERIFIED"), "result_unverified")
        self.assertEqual(cm.stage("REVIEW_REQUIRED"), "unknown_effect")
        self.assertIsNone(cm.stage("SUCCEEDED"))                 # not a media state: shown as received, never mapped

    def test_templates_cover_the_six_operations(self):
        self.assertEqual(len(cm.templates()), 6)


if __name__ == "__main__":
    unittest.main()
