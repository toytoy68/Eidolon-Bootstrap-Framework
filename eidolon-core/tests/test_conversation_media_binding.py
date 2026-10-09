# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_media_binding.py
# Description : Pièces jointes liées au propriétaire et à la conversation, revérifiées à la proposition et à l'exécution (C-TASK-G097)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from eidolon_core import conversation as cv
from eidolon_core import conversation_media as cm
from eidolon_core import conversation_store as cs
from eidolon_core.contracts import ContractError, digest
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.store import Store

SRC = str(Path(__file__).resolve().parents[1] / "src")
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
PNG = b"\x89PNG\r\n\x1a\nsynthetic attachment body"
EDIT = {"template": "media.image.edit", "parameters": {"prompt": "Ajoute un ciel étoilé", "format": "square"}}


class Crash(BaseException):
    pass


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.store = Store(base / "state")
        self.conv = cs.ConversationStore(self.store, create=True)
        self.root = base / "artifacts-private-folder"
        initialize(self.root)
        self.artifacts = ArtifactStore(self.root)
        self.ref = self.artifacts.import_bytes(PNG, display_name="phare.png")["reference"]
        self.a = self.conv.open(client_id="pc", client_key="ka")["conversation_id"]
        self.b = self.conv.open(client_id="pc", client_key="kb")["conversation_id"]
        self.foreign = self.conv.open(client_id="intrus", client_key="kc")["conversation_id"]

    def verify(self, ref):
        cm.check_artifact(self.artifacts, ref)

    def attach(self, conversation=None, owner="pc", ref=None):
        return self.conv.attach(owner_client_id=owner, conversation_id=conversation or self.a,
                                reference=ref or self.ref, verify=self.verify)

    def turn(self, conversation=None, owner="pc", key="t1"):
        return self.conv.append_turn(conversation or self.a, client_id=owner, client_turn_key=key,
                                     text="Retouche la photo du phare")["turn"]

    def edit(self, artifact_id=None):
        return {"template": EDIT["template"],
                "parameters": dict(EDIT["parameters"], artifact_id=artifact_id or self.ref["artifact_id"])}

    def proposal(self):
        self.attach()
        kind, value = cm.propose(self.conv, self.turn(), self.edit(), owner_client_id="pc")
        self.assertEqual(kind, "PROPOSAL")
        return value

    def assertNoLeak(self, text):
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("artifacts-private-folder", text)
        self.assertNotIn("synthetic attachment body", text)


class BindingTests(Base):
    def test_attachment_is_visible_only_in_its_conversation(self):
        self.attach()
        self.assertEqual([a["reference"] for a in self.conv.attachments(owner_client_id="pc", conversation_id=self.a)],
                         [self.ref])
        self.assertEqual(self.conv.attachments(owner_client_id="pc", conversation_id=self.b), [])
        self.assertEqual(self.conv.attachments(owner_client_id="intrus", conversation_id=self.a), [])
        self.assertEqual(self.attach(), self.attach())                    # idempotent for the same owner

    def test_copied_reference_in_another_conversation_is_not_an_authorization(self):
        self.attach()
        kind, code = cm.propose(self.conv, self.turn(self.b, key="tb"), self.edit(), owner_client_id="pc")
        self.assertEqual((kind, code), ("CLARIFICATION", "MEDIA_ARTIFACT_NOT_ATTACHED"))
        # A proposal frozen in A and rewritten to name B is refused at execution.
        moved = dict(self.proposal(), conversation_id=self.b)
        with self.assertRaisesRegex(ContractError, "ATTACHMENT_MISSING"):
            cm.verify_for_execution(moved, self.conv, self.artifacts)

    def test_other_owner_can_neither_attach_nor_propose_nor_execute(self):
        with self.assertRaisesRegex(ContractError, "CONVERSATION_UNKNOWN"):
            self.attach(owner="intrus")                                  # A belongs to pc
        self.attach()
        with self.assertRaisesRegex(ContractError, "CONVERSATION_UNKNOWN"):
            cm.propose(self.conv, self.turn(), self.edit(), owner_client_id="intrus")
        kind, code = cm.propose(self.conv, self.turn(self.foreign, owner="intrus", key="tf"), self.edit(),
                                owner_client_id="intrus")
        self.assertEqual(code, "MEDIA_ARTIFACT_NOT_ATTACHED")
        stolen = dict(self.proposal(), owner_client_id="intrus")
        with self.assertRaisesRegex(ContractError, "CONVERSATION_UNKNOWN"):
            cm.verify_for_execution(stolen, self.conv, self.artifacts)
        self.assertEqual(self.conv.attachments(owner_client_id="intrus", conversation_id=self.foreign), [])

    def test_reference_differing_from_the_recorded_one_is_refused(self):
        self.attach()
        forged = dict(self.ref, sha256="0" * 64)
        with self.assertRaisesRegex(ContractError, "ARTIFACT_MODIFIED"):
            self.attach(ref=forged)                                      # the store refuses before recording
        with self.assertRaisesRegex(ContractError, "ATTACHMENT_CONFLICT"):
            self.conv.attach(owner_client_id="pc", conversation_id=self.a, reference=forged, verify=lambda r: None)

    def test_unknown_artifact_is_never_recorded(self):
        ghost = dict(self.ref, artifact_id="ma-" + "f" * 32)
        with self.assertRaises(ContractError) as caught:
            self.attach(ref=ghost)
        self.assertRegex(str(caught.exception), "^ARTIFACT_UNAVAILABLE")
        self.assertNoLeak(str(caught.exception))
        self.assertEqual(self.conv.attachments(owner_client_id="pc", conversation_id=self.a), [])

    def test_proposal_reads_attachments_fresh_each_time(self):
        kind, code = cm.propose(self.conv, self.turn(), self.edit(), owner_client_id="pc")
        self.assertEqual(code, "MEDIA_ARTIFACT_NOT_ATTACHED")            # not attached yet
        self.attach()
        kind, value = cm.propose(self.conv, self.turn(), self.edit(), owner_client_id="pc")
        self.assertEqual((kind, value["artifact"]), ("PROPOSAL", self.ref))


class ExecutionTests(Base):
    def test_unchanged_artifact_gives_the_request_without_path_or_content(self):
        request = cm.verify_for_execution(self.proposal(), self.conv, self.artifacts)
        self.assertEqual(request["artifact"], self.ref)
        self.assertNotIn("source", request)
        self.assertNoLeak(json.dumps(request))

    def test_stale_proposal_is_refused_at_submission(self):
        first = self.proposal()
        kind, second = cm.propose(self.conv, self.turn(key="t2"), self.edit(), owner_client_id="pc", previous=first)
        self.assertEqual(second["version"], 2)
        sub = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": "pc",
               "command_key": "media-1", "conversation_id": self.a, "proposal_id": first["proposal_id"],
               "proposal_version": 1, "proposal_sha256": digest(first), "actor": "toytoy", "reason": "Retouche"}
        with self.assertRaisesRegex(ContractError, "PROPOSAL_STALE"):
            cm.check_submission(sub, second)

    def test_deleted_artifact_is_refused_at_execution(self):
        proposal = self.proposal()
        shutil.rmtree(self.root / self.ref["artifact_id"])
        with self.assertRaises(ContractError) as caught:
            cm.verify_for_execution(proposal, self.conv, self.artifacts)
        self.assertRegex(str(caught.exception), "^ARTIFACT_UNAVAILABLE")
        self.assertNoLeak(str(caught.exception))

    def test_modified_artifact_is_refused_at_execution(self):
        proposal = self.proposal()
        payload = self.root / self.ref["artifact_id"] / "payload"
        body = bytearray(payload.read_bytes()); body[-1] ^= 1           # same size, other content
        payload.write_bytes(bytes(body))
        with self.assertRaises(ContractError) as caught:
            cm.verify_for_execution(proposal, self.conv, self.artifacts)
        self.assertRegex(str(caught.exception), "^ARTIFACT_MODIFIED")
        self.assertNoLeak(str(caught.exception))

    def test_artifact_store_replaced_is_refused(self):
        proposal = self.proposal()
        other = Path(self.tmp.name) / "other"; initialize(other)
        with self.assertRaisesRegex(ContractError, "ARTIFACT_UNAVAILABLE"):
            cm.verify_for_execution(proposal, self.conv, ArtifactStore(other))

    def test_create_needs_no_attachment(self):
        kind, value = cm.propose(self.conv, self.turn(), {"template": "media.image.create",
                                                          "parameters": {"prompt": "Un phare", "format": "square"}}, owner_client_id="pc")
        self.assertEqual(cm.verify_for_execution(value, self.conv, self.artifacts)["operation"], "create")


class MigrationTests(Base):
    def downgrade(self):
        with sqlite3.connect(self.conv.path) as db:
            db.executescript("DROP TABLE media_proposals; DROP TABLE media_links; DROP TABLE attachments; UPDATE meta SET value='eidolon-conversation-store/2' "
                             "WHERE key='schema'; PRAGMA user_version=2;")

    def test_v2_requires_explicit_migration_and_an_interrupted_one_resumes(self):
        self.downgrade()
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_MIGRATION_REQUIRED"):
            cs.ConversationStore(self.store)

        def crash(name):
            if name == "MIGRATION_STEP_2":
                raise Crash()
        with self.assertRaises(Crash):
            cs.ConversationStore(self.store, migrate=True, checkpoint=crash)
        with sqlite3.connect(self.conv.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)      # rolled back, intact
        migrated = cs.ConversationStore(self.store, migrate=True)
        self.assertEqual(migrated.owner(self.a), "pc")
        migrated.attach(owner_client_id="pc", conversation_id=self.a, reference=self.ref, verify=self.verify)

    def test_future_version_is_refused(self):
        with sqlite3.connect(self.conv.path) as db:
            db.execute("PRAGMA user_version=9")
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            cs.ConversationStore(self.store, migrate=True)


class CommandTests(Base):
    def run_attach(self, reference_file, root=None, conversation=None, client="pc"):
        return subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", str(self.store.directory),
                               "attach", "--client-id", client, "--conversation-id", conversation or self.a,
                               "--artifact-root", str(root or self.root), "--reference", str(reference_file)],
                              env=ENV, capture_output=True, text=True, timeout=60)

    def test_operator_attach_command(self):
        ref_file = Path(self.tmp.name) / "ref.json"
        ref_file.write_text(json.dumps(self.ref))
        done = self.run_attach(ref_file)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout), {"status": "ATTACHED", "conversation_id": self.a,
                                                   "artifact_id": self.ref["artifact_id"]})
        refused = self.run_attach(ref_file, conversation=self.foreign)
        self.assertEqual((refused.returncode, json.loads(refused.stdout)), (2, {"error": "CONVERSATION_UNKNOWN"}))
        missing = self.run_attach(ref_file, root=Path(self.tmp.name) / "nowhere")
        self.assertEqual(json.loads(missing.stdout), {"error": "ARTIFACT_UNAVAILABLE"})
        for out in (done, refused, missing):
            self.assertNoLeak(out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
