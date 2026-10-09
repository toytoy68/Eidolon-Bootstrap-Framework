# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_dialogue_profiles.py
# Description : Changement explicite de profil de dialogue, identité du modèle par réponse, réponses tardives (C-TASK-G098)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from eidolon_core import conversation as cv
from eidolon_core import dialogue as dg
from eidolon_core.contracts import ContractError
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.dialogue_profiles import DialogueProfiles
from eidolon_core.store import Store

SRC = str(Path(__file__).resolve().parents[1] / "src")
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


class Named(dg.SimulatedDialogueModel):
    """A simulated model with its own identity; optionally held until released, or failing."""

    def __init__(self, catalog, name, *, hold=False, output=None, error=None, timeout=None):
        super().__init__(catalog)
        self.model_id = "test/" + name
        self.calls, self.started, self.release = 0, threading.Event(), threading.Event()
        self.hold, self.output, self.error = hold, output, error
        if timeout is not None:
            self.adapter = SimpleNamespace(config=SimpleNamespace(timeout_seconds=timeout))
        if not hold:
            self.release.set()

    def reply(self, text, history, memory):
        self.calls += 1
        self.started.set()
        self.release.wait(10)
        if self.error is not None:
            raise self.error
        if self.output is not None:
            return self.output, {"history_used": len(history), "history_dropped": 0, "memory_dropped": False}
        return super().reply(text, history, memory)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        self.runtime = synthetic_runtime(Store(self.state))
        self.conversations = ConversationStore(self.runtime.store, create=True)
        self.cid = self.conversations.open(client_id="pc", client_key="k")["conversation_id"]
        self.a = Named(self.runtime.catalog, "a")
        self.b = Named(self.runtime.catalog, "b")

    def dialogue(self, profiles=None, **kwargs):
        profiles = profiles or DialogueProfiles({"local-a": lambda: self.a, "local-b": lambda: self.b})
        return dg.Dialogue(self.conversations, profiles, self.runtime.catalog, **kwargs)

    def say(self, dialogue, key, text="Diagnostique le nas."):
        return dialogue.respond(self.cid, client_id="pc", client_turn_key=key, text=text)

    def replies(self):
        return [item["reply"] for item in self.conversations.page(self.cid)["items"]]


class SelectionTests(Base):
    def test_a_fixed_model_names_itself_in_every_reply(self):
        d = dg.Dialogue(self.conversations, self.a, self.runtime.catalog)
        self.assertEqual(self.say(d, "t1")["reply"]["model"], {"profile": None, "model_id": "test/a"})

    def test_no_selection_means_no_model_never_a_default(self):
        result = self.say(self.dialogue(DialogueProfiles({"local-a": lambda: self.a})), "t1")
        reply = result["reply"]
        self.assertEqual((reply["kind"], reply["core_note"], reply["model"], result["model_called"]),
                         ("UNAVAILABLE", "DIALOGUE_PROFILE_NOT_SELECTED", {"profile": None, "model_id": None}, False))
        self.assertEqual(self.a.calls, 0)

    def test_explicit_change_keeps_history_and_each_reply_keeps_its_model(self):
        d = self.dialogue()
        self.conversations.select_profile("local-a", actor="toytoy")
        self.say(d, "t1", "Bonjour !")
        self.conversations.select_profile("local-b", actor="toytoy")
        self.say(d, "t2")
        self.assertEqual([r["model"]["profile"] for r in self.replies()], ["local-a", "local-b"])
        self.assertEqual([r["model"]["model_id"] for r in self.replies()], ["test/a", "test/b"])
        self.assertEqual((self.a.calls, self.b.calls), (1, 1))
        self.assertEqual(self.conversations.selected_profile()["actor"], "toytoy")

    def test_profile_absent_at_restart_is_unavailable_and_no_other_profile_is_used(self):
        self.conversations.select_profile("local-b", actor="toytoy")
        restarted = self.dialogue(DialogueProfiles({"local-a": lambda: self.a}))     # file changed meanwhile
        reply = self.say(restarted, "t1")["reply"]
        self.assertEqual((reply["kind"], reply["core_note"], reply["model"]),
                         ("UNAVAILABLE", "DIALOGUE_PROFILE_UNAVAILABLE", {"profile": "local-b", "model_id": None}))
        self.assertEqual((self.a.calls, self.b.calls), (0, 0))

    def test_unloadable_profile_never_leaks_its_configuration(self):
        def broken():
            raise OSError("/home/secret/model.json: token sk-not-a-real-secret")
        self.conversations.select_profile("local-a", actor="toytoy")
        result = self.say(self.dialogue(DialogueProfiles({"local-a": broken})), "t1")
        self.assertEqual(result["reply"]["core_note"], "DIALOGUE_PROFILE_UNAVAILABLE")
        self.assertNotIn("secret", json.dumps(result))

    def test_wall_budget_follows_the_profile_actually_used(self):
        d = self.dialogue(DialogueProfiles({"slow": lambda: Named(self.runtime.catalog, "slow", timeout=7)}),
                          attempt_seconds=None)
        self.conversations.select_profile("slow", actor="toytoy")
        identity, model, _ = d._resolve()
        self.assertEqual((identity["profile"], d._budget(model)), ("slow", 12))
        self.assertEqual(d._budget(self.a), 120.0)

    def test_invalid_names_and_identities_are_refused(self):
        with self.assertRaisesRegex(ContractError, "INVALID_CONVERSATION"):
            self.conversations.select_profile("../autre", actor="toytoy")
        with self.assertRaisesRegex(ContractError, "INVALID_DIALOGUE_PROFILES"):
            DialogueProfiles({"Majuscule": lambda: self.a})
        turn = self.conversations.append_turn(self.cid, client_id="pc", client_turn_key="x", text="Bonjour")["turn"]
        with self.assertRaisesRegex(ContractError, "invalid model identity"):
            cv.decide_reply(turn, None, self.runtime.catalog, model={"profile": "a", "model_id": "x", "extra": 1})


class InFlightTests(Base):
    def test_change_during_a_reply_does_not_reattribute_it(self):
        self.a = Named(self.runtime.catalog, "a", hold=True)
        d = self.dialogue()
        self.conversations.select_profile("local-a", actor="toytoy")
        first = {}
        worker = threading.Thread(target=lambda: first.update(self.say(d, "t1")))
        worker.start()
        self.assertTrue(self.a.started.wait(5))
        self.conversations.select_profile("local-b", actor="toytoy")               # changed while A answers
        second = self.say(d, "t2", "Bonjour !")
        self.a.release.set()
        worker.join(10)
        self.assertEqual(first["reply"]["model"]["profile"], "local-a")
        self.assertEqual(second["reply"]["model"]["profile"], "local-b")
        self.assertEqual([r["model"]["profile"] for r in self.replies()], ["local-a", "local-b"])
        self.assertEqual(self.replies()[1]["kind"], "ANSWER")                       # the recent turn is intact

    def test_a_late_answer_of_the_old_profile_is_discarded(self):
        self.a = Named(self.runtime.catalog, "a", hold=True)
        d = self.dialogue(attempt_seconds=0.3)
        self.conversations.select_profile("local-a", actor="toytoy")
        cut = self.say(d, "t1")["reply"]
        self.assertEqual((cut["core_note"], cut["model"]["profile"]), ("MODEL_TIMEOUT", "local-a"))
        self.conversations.select_profile("local-b", actor="toytoy")
        recent = self.say(d, "t2", "Bonjour !")["reply"]
        self.a.release.set()
        time.sleep(0.2)                                                             # A answers, too late
        self.assertEqual(self.replies(), [cut, recent])
        self.assertIsNone(self.conversations.current_proposal(self.cid))           # A's proposal never landed
        self.assertEqual(self.say(d, "t1")["reply"], cut)                           # the same key replays, no call
        self.assertEqual(self.a.calls, 1)


class FailureTests(Base):
    def test_truncated_output_is_invalid_and_keeps_the_model_identity(self):
        self.a = Named(self.runtime.catalog, "a", output='{"version": 1, "kind": "answer", "text": "Bonj')
        self.conversations.select_profile("local-a", actor="toytoy")
        reply = self.say(self.dialogue(), "t1")["reply"]
        self.assertEqual((reply["kind"], reply["core_note"], reply["model"]),
                         ("UNAVAILABLE", "MODEL_OUTPUT_INVALID", {"profile": "local-a", "model_id": "test/a"}))
        self.assertIsNone(reply["model_text"])

    def test_unreachable_engine_is_unavailable_and_nothing_else_is_tried(self):
        self.a = Named(self.runtime.catalog, "a", error=ConnectionRefusedError("127.0.0.1:9 refused"))
        self.conversations.select_profile("local-a", actor="toytoy")
        result = self.say(self.dialogue(), "t1")
        self.assertEqual((result["reply"]["kind"], result["reply"]["core_note"], result["reply"]["model"]["profile"]),
                         ("UNAVAILABLE", "MODEL_UNAVAILABLE", "local-a"))
        self.assertEqual(self.b.calls, 0)


class FileAndCommandTests(Base):
    def write(self, value, mode=0o600):
        path = Path(self.tmp.name) / "profiles.json"
        path.write_text(json.dumps(value)); os.chmod(path, mode)
        return path

    def test_profile_file_is_private_exact_and_never_leaks_paths(self):
        hidden = str(Path(self.tmp.name) / "absent-model-config.json")
        path = self.write({"schema": "eidolon-dialogue-profiles/1",
                           "profiles": {"sim": {"kind": "simulated"}, "local": {"kind": "model_config", "path": hidden}}})
        profiles = DialogueProfiles.load(path, self.runtime.catalog)
        self.assertEqual(profiles.names(), ["local", "sim"])
        self.assertEqual(profiles.model("sim").model_id, dg.SIMULATED_MODEL_ID)
        with self.assertRaises(ContractError) as caught:
            profiles.model("local")
        self.assertNotIn("absent-model-config", str(caught.exception))
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(ContractError, "DIALOGUE_PROFILES_UNAVAILABLE"):
            DialogueProfiles.load(path, self.runtime.catalog)
        for bad in ({"schema": "eidolon-dialogue-profiles/1", "profiles": {"x": {"kind": "download", "url": "u"}}},
                    {"schema": "eidolon-dialogue-profiles/1", "profiles": {"x": {"kind": "model_config", "path": "rel"}}},
                    {"schema": "eidolon-dialogue-profiles/2", "profiles": {"x": {"kind": "simulated"}}}):
            with self.assertRaisesRegex(ContractError, "INVALID_DIALOGUE_PROFILES"):
                DialogueProfiles.load(self.write(bad), self.runtime.catalog)

    def test_operator_command_selects_only_a_configured_profile(self):
        path = self.write({"schema": "eidolon-dialogue-profiles/1", "profiles": {"sim": {"kind": "simulated"}}})

        def run(*args):
            done = subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", str(self.state),
                                   "profile", *args], env=ENV, capture_output=True, text=True, timeout=60)
            return done.returncode, json.loads(done.stdout)
        self.assertEqual(run("select", "--name", "absent", "--actor", "toytoy", "--profiles", str(path)),
                         (2, {"error": "DIALOGUE_PROFILE_UNAVAILABLE"}))
        self.assertEqual(run("show"), (0, {"selected": None}))
        code, out = run("select", "--name", "sim", "--actor", "toytoy", "--profiles", str(path))
        self.assertEqual((code, out["status"], out["selected"]["name"]), (0, "SELECTED", "sim"))
        self.assertEqual(run("show")[1]["selected"]["name"], "sim")
        self.assertEqual(self.conversations.selected_profile()["name"], "sim")


if __name__ == "__main__":
    unittest.main()
