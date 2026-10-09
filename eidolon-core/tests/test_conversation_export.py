# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_export.py
# Description : Export historique d'une conversation et inspection hors ligne (C-TASK-G093)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import copy
import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import conversation as cv
from eidolon_core import conversation_api
from eidolon_core import conversation_export as ce
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.contracts import ContractError, digest
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import Dialogue, SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.runtime = synthetic_runtime(Store(self.state))
        self.conversations = ConversationStore(self.runtime.store, create=True)
        self.token = ClientCredentials(self.runtime.store, create=True).pair(client_id="pc", actor="toytoy")["token"]
        d = Dialogue(self.conversations, SimulatedDialogueModel(self.runtime.catalog), self.runtime.catalog)
        self.cid = self.conversations.open(client_id="pc", client_key="k")["conversation_id"]
        for n, text in enumerate(("Bonjour", "Diagnostique le nas.", "Diagnostique plutôt la mémoire.")):
            d.respond(self.cid, client_id="pc", client_turn_key=f"t{n}", text=text)
        p = self.conversations.current_proposal(self.cid)
        self.receipt = self.conversations.submit(
            {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conversations.store_id, "client_id": "pc",
             "command_key": "s1", "conversation_id": self.cid, "proposal_id": p["proposal_id"],
             "proposal_version": p["version"], "proposal_sha256": cv.proposal_sha256(p), "actor": "toytoy",
             "reason": "export"},
            create=lambda request, intent: self.runtime.store.create(request, self.runtime.configuration(), intent=intent))

    def tearDown(self):
        self.tmp.cleanup()

    def export(self):
        return ce.export_conversation(self.conversations, client_id="pc", conversation_id=self.cid)

    def test_a_real_conversation_exports_consistently_and_says_it_is_only_history(self):
        e = self.export()
        self.assertEqual((len(e["turns"]), len(e["proposals"]), len(e["submissions"])), (3, 2, 1))
        self.assertEqual((e["historical"], e["authorizes_execution"], e["import_supported"]), (True, False, False))
        self.assertEqual(e["submissions"][0]["mission_id"], self.receipt["mission_id"])
        self.assertEqual(set(e["submissions"][0]), ce.SUBMISSION_FIELDS)            # summary, not the body
        report = ce.inspect(e)
        self.assertEqual((report["status"], report["authenticity"], report["authorizes_execution"]),
                         ("CONSISTENT", "NOT_ESTABLISHED", False))

    def test_tampering_is_detected(self):
        base = self.export()
        cases = {
            "texte d'un tour": lambda e: e["turns"][0]["turn"].__setitem__("text", "Autre chose"),
            "réponse détachée": lambda e: e["turns"][1]["reply"].__setitem__("turn_sha256", "0" * 64),
            "autorisation ajoutée": lambda e: e["turns"][1]["reply"].__setitem__("authorizes_execution", True),
            "proposition modifiée": lambda e: e["proposals"][0].__setitem__("target_id", "sim-offline"),
            "lien vers une autre mission": lambda e: e["submissions"][0]["link"].__setitem__("mission_id", "m-" + "0" * 32),
            "tour retiré": lambda e: e["turns"].pop(1),
            "champ en plus (chemin)": lambda e: e.__setitem__("attachment_path", "/etc/passwd"),
            "import déclaré possible": lambda e: e.__setitem__("import_supported", True),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                e = copy.deepcopy(base)
                change(e)
                self.assertEqual(ce.inspect(e)["status"], "INCONSISTENT")

    def test_no_credential_or_token_ever_reaches_the_export(self):
        raw = json.dumps(self.export(), ensure_ascii=False)
        self.assertNotIn(self.token, raw)
        self.assertNotIn("ecc_", raw)
        self.assertNotIn(hashlib.sha256(self.token.encode()).hexdigest(), raw)
        self.assertNotIn('"reason"', raw)                                            # no resendable body

    def test_files_are_new_private_and_never_written_through_a_link(self):
        out = self.root / "export.json"
        written = ce.write_export(self.export(), out)
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o600)
        self.assertEqual(written["sha256"], hashlib.sha256(out.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ContractError, "EXPORT_PATH_REFUSED"):
            ce.write_export(self.export(), out)                                       # never overwrite
        target = self.root / "ailleurs.json"
        (self.root / "lien.json").symlink_to(target)
        with self.assertRaisesRegex(ContractError, "EXPORT_PATH_REFUSED"):
            ce.write_export(self.export(), self.root / "lien.json")
        self.assertFalse(target.exists())
        self.assertEqual(ce.inspect(ce.read_export(out))["status"], "CONSISTENT")

    def test_other_clients_and_size_bounds(self):
        with self.assertRaisesRegex(ContractError, "CONVERSATION_UNKNOWN"):
            ce.export_conversation(self.conversations, client_id="autre", conversation_id=self.cid)
        with patch.object(ce, "MAX_EXPORT_BYTES", 2000), self.assertRaisesRegex(ContractError, "EXPORT_TOO_LARGE"):
            self.export()

    def test_exporting_changes_no_database(self):
        def prints():
            return [hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (self.state / "missions.sqlite3", self.conversations.path)]
        before = prints()
        self.export()
        self.assertEqual(prints(), before)

    def test_there_is_no_import_anywhere(self):
        self.assertFalse([n for n in dir(ce) if "import" in n.lower() and callable(getattr(ce, n)) and n != "__import__"])
        self.assertNotIn("import", conversation_api.ROUTES)

    def test_cli_export_then_offline_inspection(self):
        out = self.root / "cli.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ce.main(["export", "--state", str(self.state), "--client-id", "pc",
                                      "--conversation-id", self.cid, "--output", str(out)]), 0)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(ce.main(["inspect", str(out)]), 0)
        self.assertEqual(json.loads(buffer.getvalue())["status"], "CONSISTENT")
        with redirect_stdout(io.StringIO()) as missing:
            self.assertEqual(ce.main(["export", "--state", str(self.root / "absent"), "--client-id", "pc",
                                      "--conversation-id", self.cid, "--output", str(self.root / "x.json")]), 2)
        self.assertIn("STATE_MISSING", missing.getvalue())
        self.assertFalse((self.root / "absent").exists())                            # nothing created


if __name__ == "__main__":
    unittest.main()
