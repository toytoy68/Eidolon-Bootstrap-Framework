# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_store.py
# Description : Dépôt des conversations : ordre, doublons, coupures, concurrence, stockage indisponible (C-TASK-G085)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import conversation as cv
from eidolon_core import conversation_store as cs
from eidolon_core.contracts import ContractError
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store

SRC = str(Path(__file__).resolve().parents[1] / "src")
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


class Crash(BaseException):
    pass


def model(target="nas", kind="proposal"):
    proposal = {"template": cv.DIAGNOSTIC, "parameters": {"target_reference": target}} if kind == "proposal" else None
    return json.dumps({"version": 1, "kind": kind, "text": "Réponse du modèle simulé.", "proposal": proposal})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.runtime = synthetic_runtime(Store(self.state))
        self.conv = cs.ConversationStore(self.runtime.store, create=True)
        self.cid = self.conv.open(client_id="pc", client_key="k1")["conversation_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def say(self, key, text="Diagnostique le nas.", output=None, conv=None):
        conv = conv or self.conv
        turn = conv.append_turn(self.cid, client_id="pc", client_turn_key=key, text=text)["turn"]
        previous = conv.current_proposal(self.cid)
        reply = cv.decide_reply(turn, output or model(), self.runtime.catalog, previous_proposal=previous)
        return conv.record_reply(reply)

    def submission(self, proposal, key="submit-1", **changes):
        value = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": "pc",
                 "command_key": key, "conversation_id": self.cid, "proposal_id": proposal["proposal_id"],
                 "proposal_version": proposal["version"], "proposal_sha256": cv.proposal_sha256(proposal),
                 "actor": "toytoy", "reason": "validé"}
        value.update(changes)
        return value

    def create(self, request, intent):
        return self.runtime.store.create(request, self.runtime.configuration(), intent=intent)

    def missions(self):
        with self.runtime.store.connection() as db:
            return [r[0] for r in db.execute("SELECT id FROM missions ORDER BY id")]


class ConversationTests(Base):
    def test_open_is_idempotent_per_client_key(self):
        self.assertEqual(self.conv.open(client_id="pc", client_key="k1"), {"conversation_id": self.cid, "created": False})
        self.assertNotEqual(self.conv.open(client_id="pc", client_key="k2")["conversation_id"], self.cid)

    def test_turns_are_ordered_chained_and_replayed_without_duplicates(self):
        first = self.say("t1")
        again = self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="Diagnostique le nas.")
        self.assertTrue(again["replayed"])
        self.assertEqual(again["reply"], first)
        self.say("t2", "Et la mémoire ?", model("mémoire"))
        page = self.conv.page(self.cid)
        self.assertEqual([i["turn"]["sequence"] for i in page["items"]], [1, 2])
        self.assertEqual(page["items"][1]["turn"]["previous_turn_sha256"], cv.digest(page["items"][0]["turn"]))
        with self.assertRaisesRegex(ContractError, "TURN_KEY_REUSED"):
            self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="autre chose")

    def test_unknown_conversation_and_full_conversation(self):
        with self.assertRaisesRegex(ContractError, "CONVERSATION_UNKNOWN"):
            self.conv.append_turn("c-" + "0" * 32, client_id="pc", client_turn_key="x", text="bonjour")
        with patch.object(cs, "MAX_TURNS", 2):
            self.say("a", output=model(kind="answer")), self.say("b", output=model(kind="answer"))
            with self.assertRaisesRegex(ContractError, "CONVERSATION_FULL"):
                self.conv.append_turn(self.cid, client_id="pc", client_turn_key="c", text="encore")

    def test_one_reply_per_turn(self):
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="Bonjour")["turn"]
        reply = cv.decide_reply(turn, model(kind="answer"), self.runtime.catalog)
        self.assertEqual(self.conv.record_reply(reply), reply)
        self.assertEqual(self.conv.record_reply(reply), reply)
        other = cv.decide_reply(turn, model(kind="clarification"), self.runtime.catalog)
        with self.assertRaisesRegex(ContractError, "REPLY_ALREADY_RECORDED"):
            self.conv.record_reply(other)

    def test_forged_replies_are_refused(self):
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="Bonjour")["turn"]
        reply = cv.decide_reply(turn, model(), self.runtime.catalog)
        for bad in ({**reply, "turn_sha256": "0" * 64}, {**reply, "in_reply_to": "t-" + "0" * 32},
                    {**reply, "store_id": "s-" + "0" * 32}, {**reply, "proposal_sha256": "0" * 64}):
            with self.subTest(bad=bad), self.assertRaisesRegex(ContractError, "REPLY_INVALID"):
                self.conv.record_reply(bad)

    def test_proposal_versions_are_recorded_in_order(self):
        v1 = self.say("t1")["proposal"]
        v2 = self.say("t2", "Plutôt la mémoire.", model("mémoire"))["proposal"]
        self.assertEqual((v2["version"], v2["proposal_id"]), (2, v1["proposal_id"]))
        self.assertEqual(self.conv.current_proposal(self.cid), v2)
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t3", text="Le nas.")["turn"]
        stale = cv.decide_reply(turn, model(), self.runtime.catalog, previous_proposal=v1)  # forks from v1
        with self.assertRaisesRegex(ContractError, "PROPOSAL_STALE"):
            self.conv.record_reply(stale)

    def test_pages_resume_after_reconnection(self):
        for n in range(5):
            self.say(f"t{n}", f"message {n}", model(kind="answer"))
        first = self.conv.page(self.cid, limit=2)
        self.assertEqual((len(first["items"]), first["has_more"], first["next_after"]), (2, True, 2))
        reopened = cs.ConversationStore(self.runtime.store)              # a new process after reconnection
        rest = reopened.page(self.cid, after=first["next_after"], limit=50)
        self.assertEqual([i["turn"]["sequence"] for i in rest["items"]], [3, 4, 5])
        self.assertFalse(rest["has_more"])
        for bad in ({"after": -1}, {"limit": 0}, {"limit": 51}):
            with self.assertRaises(ContractError):
                self.conv.page(self.cid, **bad)

    def test_context_respects_the_budget(self):
        for n in range(6):
            self.say(f"t{n}", "x" * 1000, model(kind="answer"))
        context = self.conv.context(self.cid, max_chars=3100)    # 3 x (1000 + 25 reply chars) = 3075
        self.assertEqual([t["sequence"] for t in context["turns"]], [4, 5, 6])
        self.assertTrue(context["truncated"])
        self.assertLessEqual(context["chars"], 3100)

    def test_conversation_writes_never_touch_the_mission_database(self):
        def fingerprint():
            return hashlib.sha256((self.state / "missions.sqlite3").read_bytes()).hexdigest()
        before = fingerprint()
        self.say("t1"), self.say("t2", output=model(kind="answer")), self.conv.page(self.cid)
        self.assertEqual(fingerprint(), before)


class SubmissionTests(Base):
    def test_submission_creates_one_mission_and_retries_return_the_receipt(self):
        proposal = self.say("t1")["proposal"]
        receipt = self.conv.submit(self.submission(proposal), create=self.create)
        self.assertEqual((receipt["status"], receipt["execution_evidence"]), ("MISSION_CREATED", False))
        self.assertEqual(self.conv.submit(self.submission(proposal), create=self.create), receipt)
        self.assertEqual(self.missions(), [receipt["mission_id"]])
        cv.check_link(receipt["link"], proposal, self.runtime.store.get(receipt["mission_id"]))
        self.assertEqual(self.conv.receipt(client_id="pc", command_key="submit-1"), receipt)
        self.assertIsNone(self.conv.receipt(client_id="pc", command_key="never-sent"))

    def test_refusals_create_nothing(self):
        v1 = self.say("t1")["proposal"]
        self.say("t2", "la mémoire", model("mémoire"))
        with self.assertRaisesRegex(ContractError, "PROPOSAL_STALE"):
            self.conv.submit(self.submission(v1), create=self.create)
        v2 = self.conv.current_proposal(self.cid)
        with self.assertRaisesRegex(ContractError, "PROPOSAL_CHANGED"):
            self.conv.submit(self.submission(v2, proposal_sha256="0" * 64), create=self.create)
        with self.assertRaisesRegex(ContractError, "STORE_CHANGED"):
            self.conv.submit(self.submission(v2, store_id="s-" + "0" * 32), create=self.create)
        self.assertEqual(self.missions(), [])
        self.conv.submit(self.submission(v2), create=self.create)
        with self.assertRaisesRegex(ContractError, "COMMAND_KEY_REUSED"):
            self.conv.submit(self.submission(v2, reason="autre"), create=self.create)
        with self.assertRaisesRegex(ContractError, "PROPOSAL_ALREADY_SUBMITTED"):
            self.conv.submit(self.submission(v2, key="submit-2"), create=self.create)
        self.assertEqual(len(self.missions()), 1)

    def test_cut_before_mission_creation_creates_it_once_on_retry(self):
        proposal = self.say("t1")["proposal"]
        def crash(name):
            if name == "SUBMISSION_RESERVED":
                raise Crash()
        with self.assertRaises(Crash):
            cs.ConversationStore(self.runtime.store, checkpoint=crash).submit(self.submission(proposal), create=self.create)
        self.assertEqual(self.missions(), [])
        self.assertEqual(self.conv.receipt(client_id="pc", command_key="submit-1")["status"], "RESERVED")
        receipt = cs.ConversationStore(self.runtime.store).submit(self.submission(proposal), create=self.create)
        self.assertEqual((receipt["status"], self.missions()), ("MISSION_CREATED", [receipt["mission_id"]]))

    def test_cut_then_newer_proposal_never_creates_the_superseded_mission(self):
        v1 = self.say("t1")["proposal"]
        def crash(name):
            if name == "SUBMISSION_RESERVED":
                raise Crash()
        with self.assertRaises(Crash):
            cs.ConversationStore(self.runtime.store, checkpoint=crash).submit(self.submission(v1), create=self.create)
        self.say("t2", "Finalement la mémoire.", model("mémoire"))                # v2 recorded after the cut
        receipt = self.conv.submit(self.submission(v1), create=self.create)
        self.assertEqual((receipt["status"], receipt["mission_id"], self.missions()),
                         ("SUPERSEDED_NOT_CREATED", None, []))
        v2 = self.conv.current_proposal(self.cid)
        created = self.conv.submit(self.submission(v2, key="submit-2"), create=self.create)
        self.assertEqual(self.runtime.store.get(created["mission_id"])["objective"]["target_id"], "sim-memory")

    def test_cut_after_mission_creation_is_uncertain_never_doubled(self):
        proposal = self.say("t1")["proposal"]
        def crash(name):
            if name == "MISSION_CREATED":
                raise Crash()
        with self.assertRaises(Crash):
            cs.ConversationStore(self.runtime.store, checkpoint=crash).submit(self.submission(proposal), create=self.create)
        created = self.missions()
        receipt = self.conv.submit(self.submission(proposal), create=self.create)
        self.assertEqual((receipt["status"], receipt["mission_id"], receipt["resolution"]["candidates"]),
                         ("MISSION_CREATION_UNCERTAIN", None, created))
        self.assertEqual(self.conv.submit(self.submission(proposal), create=self.create), receipt)
        self.assertEqual(self.missions(), created)                          # still exactly one mission
        other = self.runtime.create_diagnostic("mémoire")["id"]
        with self.assertRaisesRegex(ContractError, "NOT_A_CANDIDATE"):
            self.conv.resolve_uncertain(client_id="pc", command_key="submit-1", mission_id=other,
                                        actor="toytoy", reason="test")
        resolved = self.conv.resolve_uncertain(client_id="pc", command_key="submit-1", mission_id=created[0],
                                               actor="toytoy", reason="c'est bien elle")
        self.assertEqual((resolved["status"], resolved["mission_id"]), ("MISSION_CREATED", created[0]))
        cv.check_link(resolved["link"], proposal, self.runtime.store.get(created[0]))

    def test_uncertain_can_be_closed_as_no_mission_then_resubmitted(self):
        proposal = self.say("t1")["proposal"]
        def crash(name):
            if name == "MISSION_CREATED":
                raise Crash()
        with self.assertRaises(Crash):
            cs.ConversationStore(self.runtime.store, checkpoint=crash).submit(self.submission(proposal), create=self.create)
        self.conv.submit(self.submission(proposal), create=self.create)
        closed = self.conv.resolve_uncertain(client_id="pc", command_key="submit-1", mission_id=None,
                                             actor="toytoy", reason="la mission trouvée n'est pas la mienne")
        self.assertEqual(closed["status"], "NO_MISSION_CONFIRMED")
        with self.assertRaisesRegex(ContractError, "NOT_UNCERTAIN"):
            self.conv.resolve_uncertain(client_id="pc", command_key="submit-1", mission_id=None,
                                        actor="toytoy", reason="encore")
        again = self.conv.submit(self.submission(proposal, key="submit-2"), create=self.create)
        self.assertEqual(again["status"], "MISSION_CREATED")


CRASH = r"""
import os, sys, json
sys.path.insert(0, sys.argv[1])
from eidolon_core import conversation_store as cs
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
runtime = synthetic_runtime(Store(sys.argv[2]))
def checkpoint(name):
    if name == sys.argv[4]:
        os._exit(9)                       # power cut: no cleanup, no rollback handler
conv = cs.ConversationStore(runtime.store, checkpoint=checkpoint)
submission = json.loads(sys.argv[3])
create = lambda request, intent: runtime.store.create(request, runtime.configuration(), intent=intent)
print(json.dumps(conv.submit(submission, create=create)))
"""

APPEND = r"""
import sys
sys.path.insert(0, sys.argv[1])
from eidolon_core import conversation_store as cs
from eidolon_core.store import Store
conv = cs.ConversationStore(Store(sys.argv[2]))
conv.append_turn(sys.argv[3], client_id="pc", client_turn_key=sys.argv[4], text="tour " + sys.argv[4])
"""


class ProcessTests(Base):
    def run_crash(self, submission, point):
        return subprocess.run([sys.executable, "-c", CRASH, SRC, str(self.state), json.dumps(submission), point],
                              capture_output=True, text=True, env=ENV, timeout=60)

    def test_killed_process_after_creation_leaves_one_mission(self):
        proposal = self.say("t1")["proposal"]
        self.assertEqual(self.run_crash(self.submission(proposal), "MISSION_CREATED").returncode, 9)
        created = self.missions()
        self.assertEqual(len(created), 1)
        retry = self.run_crash(self.submission(proposal), "never")
        self.assertEqual(json.loads(retry.stdout)["status"], "MISSION_CREATION_UNCERTAIN")
        self.assertEqual(self.missions(), created)

    def test_concurrent_turns_stay_contiguous(self):
        procs = [subprocess.Popen([sys.executable, "-c", APPEND, SRC, str(self.state), self.cid, f"k{n}"], env=ENV)
                 for n in range(8)]
        self.assertEqual([p.wait(timeout=60) for p in procs], [0] * 8)
        items = self.conv.page(self.cid, limit=50)["items"]
        self.assertEqual([i["turn"]["sequence"] for i in items], list(range(1, 9)))
        for previous, item in zip(items, items[1:]):
            self.assertEqual(item["turn"]["previous_turn_sha256"], cv.digest(previous["turn"]))

    def test_concurrent_identical_submissions_create_one_mission(self):
        proposal = self.say("t1")["proposal"]
        procs = [subprocess.Popen([sys.executable, "-c", CRASH, SRC, str(self.state),
                                   json.dumps(self.submission(proposal)), "never"],
                                  stdout=subprocess.PIPE, text=True, env=ENV) for _ in range(6)]
        receipts = [json.loads(p.communicate(timeout=60)[0]) for p in procs]
        self.assertEqual({r["mission_id"] for r in receipts}, set(self.missions()))
        self.assertEqual(len(self.missions()), 1)


class StorageTests(Base):
    def test_busy_store_is_reported_quickly(self):
        holder = sqlite3.connect(self.conv.path, isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")
        try:
            with patch.object(cs, "BUSY_SECONDS", 0.2), self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_BUSY"):
                self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="bonjour")
        finally:
            holder.rollback(), holder.close()
        self.conv.append_turn(self.cid, client_id="pc", client_turn_key="t1", text="bonjour")

    def test_corrupt_store_is_unavailable(self):
        self.conv.path.write_bytes(b"not a database" * 100)
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            cs.ConversationStore(self.runtime.store)

    def test_conversations_copied_to_another_mission_store_are_refused(self):
        other = Path(self.tmp.name) / "other"
        Store(other)
        shutil.copytree(self.state / "conversations", other / "conversations")
        with self.assertRaisesRegex(ContractError, "STORE_CHANGED"):
            cs.ConversationStore(Store(other))

    def test_g085_r1_a_link_in_place_of_the_database_is_refused_untouched(self):
        other = Store(Path(self.tmp.name) / "linked")
        os.mkdir(other.directory / "conversations", 0o700)
        external = Path(self.tmp.name) / "external.sqlite3"
        with sqlite3.connect(external) as db:
            db.execute("CREATE TABLE unrelated (value TEXT)")
        before = hashlib.sha256(external.read_bytes()).hexdigest()
        (other.directory / "conversations" / "conversations.sqlite3").symlink_to(external)
        for create in (False, True):
            with self.subTest(create=create), self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
                cs.ConversationStore(other, create=create)
        self.assertEqual(hashlib.sha256(external.read_bytes()).hexdigest(), before)

    def test_an_unrelated_regular_database_never_gets_our_tables(self):
        other = Store(Path(self.tmp.name) / "foreign")
        os.mkdir(other.directory / "conversations", 0o700)
        path = other.directory / "conversations" / "conversations.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE unrelated (value TEXT)")
        os.chmod(path, 0o600)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            cs.ConversationStore(other, create=True)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_g085_r2_a_replaced_database_is_refused_by_an_open_instance(self):
        other = cs.ConversationStore(Store(Path(self.tmp.name) / "b"), create=True)
        self.conv.path.unlink()
        shutil.copyfile(other.path, self.conv.path)
        os.chmod(self.conv.path, 0o600)
        with self.assertRaisesRegex(ContractError, "STORE_CHANGED"):
            self.conv.open(client_id="pc", client_key="after-replacement")
        with self.assertRaisesRegex(ContractError, "STORE_CHANGED"):          # reopening: foreign identity
            cs.ConversationStore(self.runtime.store)
        with sqlite3.connect(self.conv.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)

    def test_g085_r3_reads_never_create_a_missing_file(self):
        self.conv.path.unlink()
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_MISSING"):
            self.conv.page(self.cid)
        self.assertFalse(self.conv.path.exists())
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_MISSING"):
            cs.ConversationStore(self.runtime.store)                          # reopening never creates
        self.assertFalse(self.conv.path.exists())

    def test_g085_r4_context_bounds_are_checked(self):
        for bad in ({"max_turns": -1}, {"max_turns": 0}, {"max_turns": 201}, {"max_turns": True},
                    {"max_chars": -5}, {"max_chars": 200_001}, {"max_chars": 1.5}):
            with self.subTest(bad=bad), self.assertRaisesRegex(ContractError, "INVALID_CONVERSATION"):
                self.conv.context(self.cid, **bad)

    def test_open_permissions_are_refused(self):
        os.chmod(self.conv.path, 0o644)
        with self.assertRaisesRegex(ContractError, "not private"):
            self.conv.page(self.cid)
        os.chmod(self.conv.path, 0o600)
        os.chmod(self.conv.directory, 0o755)
        with self.assertRaisesRegex(ContractError, "not private"):
            self.conv.page(self.cid)
        os.chmod(self.conv.directory, 0o700)
        self.conv.page(self.cid)

    def test_files_are_private(self):
        self.assertEqual(os.stat(self.conv.directory).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.conv.path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
