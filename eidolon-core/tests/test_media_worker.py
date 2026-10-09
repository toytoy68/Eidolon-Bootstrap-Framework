# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_worker.py
# Description : Consentement, concurrence et coupures du worker média
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core import conversation as cv, conversation_media as cm
from eidolon_core.contracts import ContractError, digest
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.media_agents import MediaError
from eidolon_core.media_artifacts import ArtifactStore, initialize as initialize_artifacts
from eidolon_core.media_resources import ResourcePool, initialize as initialize_pool
from eidolon_core.media_worker import MediaWorker, initialize
from eidolon_core.store import Store


class Backend:
    def __init__(self):
        self.calls = 0
    def plan(self, *args):
        return {"adapter": "synthetic-worker-test"}
    def run(self, request, *args, progress):
        self.calls += 1
        progress("ANALYSIS_SUBMITTING" if request["operation"] == "analyze" else "QUEUE_SUBMITTING", {})
        return {"state": "RESULT_UNVERIFIED", "text": "Observation synthétique <script>"} if request["operation"] == "analyze" else {
            "state": "QUEUED", "prompt_id": "synthetic"}


def run_child(root, worker_id, store_id, state, ticket, config, barrier, result, effects):
    conv = ConversationStore(Store(state))
    worker = MediaWorker(root, worker_id=worker_id, store_id=store_id)
    class ChildBackend(Backend):
        def run(self, *args, **kwargs):
            with effects.get_lock():
                effects.value += 1
            return super().run(*args, **kwargs)
    barrier.wait(timeout=10)
    try:
        r = worker.run_once(ticket, client_id="pc", conversations=conv, config=config,
                            execute_local=True, backend=ChildBackend())
        result.put(r["state"])
    except MediaError as exc:
        result.put(exc.code)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.conv = ConversationStore(Store(self.state), create=True)
        self.cid = self.conv.open(client_id="pc", client_key="conversation")["conversation_id"]
        self.path = self.root / "worker"
        self.marker = initialize(self.path, store_id=self.conv.store_id)
        self.worker = self.reopen()
        pool_root = self.root / "pool"
        pool_id = initialize_pool(pool_root)["pool_id"]
        self.pool = ResourcePool(pool_root, pool_id)
        self.cfg = {"resource_pool": {"root": str(pool_root), "pool_id": pool_id}}
        self.artifacts_root = self.root / "artifacts"
        initialize_artifacts(self.artifacts_root)
        self.artifacts = ArtifactStore(self.artifacts_root)
        self.cfg["artifact_store"] = {"root": str(self.artifacts_root), "store_id": self.artifacts.store_id}
        self.backend = Backend()
        self.counter = 0
        self.current = None
        # G122 owns persistence of media proposals. Use its documented current_proposal
        # boundary; owner/turn/attachment methods still run against a REAL ConversationStore.
        self.current_patch = patch.object(self.conv, "current_proposal", side_effect=lambda _: self.current)
        self.current_patch.start(); self.addCleanup(self.current_patch.stop)

    def reopen(self):
        return MediaWorker(self.path, worker_id=self.marker["worker_id"], store_id=self.conv.store_id)

    def proposal(self, operation="create", agent="image"):
        self.counter += 1
        turn = self.conv.append_turn(self.cid, client_id="pc", client_turn_key=f"turn{self.counter}", text="Un phare")["turn"]
        args = {"prompt": "Un phare"}
        if operation != "analyze":
            args["format"] = "square"
            if agent == "video":
                args["duration_seconds"] = 5
        if operation != "create":
            raw = b"\x89PNG\r\n\x1a\nfixture" if agent == "image" else b"\x00\x00\x00\x18ftypisomfixture"
            self.source = self.artifacts.import_bytes(raw, display_name="source.png" if agent == "image" else "source.mp4")["reference"]
            self.conv.attach(owner_client_id="pc", conversation_id=self.cid, reference=self.source,
                             verify=lambda r: cm.check_artifact(self.artifacts, r))
            args["artifact_id"] = self.source["artifact_id"]
        kind, proposal = cm.propose(self.conv, turn, {"template": f"media.{agent}.{operation}", "parameters": args},
                                    owner_client_id="pc", previous=self.current)
        self.assertEqual(kind, "PROPOSAL")
        self.current = proposal
        return {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": "pc",
                "command_key": f"command{self.counter}", "conversation_id": self.cid, "proposal_id": proposal["proposal_id"],
                "proposal_version": proposal["version"], "proposal_sha256": digest(proposal), "actor": "human:pc",
                "reason": "Validation humaine synthétique"}

    def enqueue(self, submission=None):
        return self.worker.enqueue(submission or self.proposal(), conversations=self.conv,
                                   authenticated_client_id="pc", authenticated_actor="human:pc")

    def run_ticket(self, ticket, **kwargs):
        return self.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv,
                                    config=self.cfg, execute_local=True, backend=kwargs.get("backend", self.backend))

    def test_enqueue_does_not_create_job_reserve_or_call_engine(self):
        sub = self.proposal(); ticket = self.enqueue(sub)
        self.assertEqual(ticket["state"], "ACCEPTED")
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")
        self.assertFalse((self.path / ticket["ticket_id"]).exists())
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.reopen().receipt(client_id="pc", command_key=sub["command_key"]), ticket)
        self.assertIsNone(self.worker.receipt(client_id="other", command_key=sub["command_key"]))
        with self.assertRaisesRegex(MediaError, "MEDIA_EXECUTION_NOT_ENABLED"):
            self.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv, config=self.cfg)

    def test_scope_actor_stale_digest_and_changed_command_refused(self):
        sub = self.proposal()
        for name, value in (("client_id", "intruder"), ("actor", "intruder"), ("proposal_sha256", "0" * 64)):
            with self.subTest(name=name), self.assertRaises((MediaError, ContractError)):
                self.enqueue({**sub, name: value})
        original = self.enqueue(sub)
        with self.assertRaisesRegex(MediaError, "MEDIA_COMMAND_KEY_REUSED"):
            self.enqueue({**sub, "reason": "changed"})
        with self.assertRaisesRegex(MediaError, "MEDIA_PROPOSAL_ALREADY_SUBMITTED"):
            self.enqueue({**sub, "command_key": "new-key"})
        self.proposal()
        self.assertEqual(self.enqueue(sub), original)  # exact replay survives newer proposal
        with self.assertRaisesRegex(ContractError, "PROPOSAL_STALE"):
            self.enqueue({**sub, "command_key": "new-after-edit"})

    def test_six_modes_single_attempt_and_result_view(self):
        for agent in ("image", "video"):
            for op in ("create", "edit", "analyze"):
                with self.subTest(agent=agent, operation=op):
                    ticket = self.enqueue(self.proposal(op, agent))
                    result = self.run_ticket(ticket)
                    self.assertEqual(result["state"], "RETURNED")
                    view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
                    self.assertEqual(view["result"]["binding"], "MATCHED")
                    self.assertEqual(view["result"]["job_id"], ticket["job_id"])
                    self.assertFalse(view["result"]["success_claim"])
                    calls = self.backend.calls
                    self.assertEqual(self.run_ticket(ticket), result)
                    self.assertEqual(self.backend.calls, calls)
                    current = self.pool.inspect()["current"]
                    self.assertEqual(current["job_id"], ticket["job_id"])
                    self.pool.release(current["lease_id"], reviewed_idle=True, reason="Synthetic engine reviewed")
        self.assertEqual(self.backend.calls, 6)

    def test_foreign_owner_and_identical_request_other_job_not_visible(self):
        ticket = self.enqueue(); self.run_ticket(ticket)
        with self.assertRaisesRegex(MediaError, "MEDIA_TICKET_UNKNOWN"):
            self.worker.result(ticket["ticket_id"], client_id="intruder", conversations=self.conv, artifact_store=self.artifacts)
        journal = self.path / ticket["ticket_id"] / "job.json"
        row = json.loads(journal.read_text()); row["id"] = "media-" + "f" * 32
        journal.write_text(json.dumps(row))
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["observation"], "JOB_UNAVAILABLE_OR_CHANGED")
        self.assertIsNone(view["result"])

    def test_modified_artifact_before_attempt_never_calls_engine(self):
        ticket = self.enqueue(self.proposal("edit"))
        payload = self.artifacts_root / self.source["artifact_id"] / "payload"
        payload.write_bytes(b"\x89PNG\r\n\x1a\nchanged")
        with self.assertRaisesRegex(ContractError, "ARTIFACT_MODIFIED"):
            self.run_ticket(ticket)
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.worker.tickets(client_id="pc")[0]["state"], "ACCEPTED")
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")

    def test_claim_disk_failure_before_effect_does_not_call_engine(self):
        ticket = self.enqueue()
        with patch("eidolon_core.media_worker._save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_ticket(ticket)
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")
        self.assertEqual(self.reopen().tickets(client_id="pc")[0]["state"], "ACCEPTED")

    def test_job_publication_failure_after_claim_never_retries(self):
        ticket = self.enqueue()
        with patch("eidolon_core.media_agents.write_record", side_effect=OSError("disk full secret path")):
            with self.assertRaisesRegex(MediaError, "MEDIA_ATTEMPT_UNCERTAIN"):
                self.run_ticket(ticket)
        receipt = self.run_ticket(ticket)
        self.assertEqual(receipt["state"], "REVIEW_REQUIRED")
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.pool.inspect()["current"]["job_id"], ticket["job_id"])
        self.assertNotIn("secret", json.dumps(receipt))

    def test_final_queue_write_failure_retains_attempt_and_linked_result(self):
        ticket = self.enqueue()
        with patch.object(self.worker, "_finish", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_ticket(ticket)
        self.assertEqual(self.run_ticket(ticket)["state"], "ATTEMPTED")
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["result"]["binding"], "MATCHED")
        self.assertEqual(self.backend.calls, 1)

    def test_threads_same_ticket_only_one_effect(self):
        ticket = self.enqueue(); entered = threading.Event(); release = threading.Event()
        base = self.backend
        class Blocking(Backend):
            def run(self, *args, **kwargs):
                entered.set(); release.wait(timeout=5)
                return base.run(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(self.run_ticket, ticket, backend=Blocking())
            self.assertTrue(entered.wait(timeout=5))
            second = workers.submit(self.run_ticket, ticket)
            try:
                self.assertEqual(second.result(timeout=5)["state"], "ATTEMPTED")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)["state"], "RETURNED")
        self.assertEqual(self.backend.calls, 1)

    def test_eight_processes_same_ticket_only_one_effect(self):
        ticket = self.enqueue()
        ctx = multiprocessing.get_context("fork")
        barrier, result, effects = ctx.Barrier(8), ctx.Queue(), ctx.Value("i", 0)
        children = [ctx.Process(target=run_child, args=(str(self.path), self.marker["worker_id"], self.conv.store_id,
                    str(self.state), ticket["ticket_id"], self.cfg, barrier, result, effects)) for _ in range(8)]
        for child in children: child.start()
        for child in children:
            child.join(timeout=15)
            self.assertEqual(child.exitcode, 0)
        values = [result.get(timeout=2) for _ in children]
        self.assertTrue(all(v in {"ATTEMPTED", "RETURNED", "WORKER_BUSY"} for v in values), values)
        self.assertEqual(effects.value, 1)

    def test_killed_process_after_submit_phase_no_second_attempt(self):
        ticket = self.enqueue()
        script = '''
import json,os,sys
from eidolon_core.media_worker import MediaWorker
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.store import Store
class Backend:
 def plan(self,*a):return {"adapter":"synthetic"}
 def run(self,*a,progress):
  progress("QUEUE_SUBMITTING",{})
  os._exit(77)
w=MediaWorker(sys.argv[1],worker_id=sys.argv[2],store_id=sys.argv[3])
w.run_once(sys.argv[4],client_id="pc",conversations=ConversationStore(Store(sys.argv[5])),config=json.loads(sys.argv[6]),execute_local=True,backend=Backend())
'''
        p = subprocess.run([sys.executable, "-c", script, str(self.path), self.marker["worker_id"], self.conv.store_id,
                            ticket["ticket_id"], str(self.state), json.dumps(self.cfg)], capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 77, p.stderr)
        self.assertEqual(self.run_ticket(ticket)["state"], "ATTEMPTED")
        self.assertEqual(self.backend.calls, 0)
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["result"]["state_received"], "REVIEW_REQUIRED")
        self.assertEqual(self.pool.inspect()["state"], "RESERVED")

    def test_private_paths_replacement_hardlinks_and_corruption_fail_closed(self):
        alias = self.root / "alias"; alias.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(OSError):
            MediaWorker(alias, worker_id=self.marker["worker_id"], store_id=self.conv.store_id)
        for filename in ("writer.lock", "queue.json"):
            link = self.root / "hardlink"; os.link(self.path / filename, link)
            with self.assertRaises(MediaError): self.worker.tickets(client_id="pc")
            link.unlink()
        old = self.root / "old"; self.path.rename(old)
        initialize(self.path, store_id=self.conv.store_id)
        with self.assertRaisesRegex(MediaError, "WORKER_REPLACED"):
            self.worker.tickets(client_id="pc")
        with self.assertRaisesRegex(MediaError, "WORKER_IDENTITY_MISMATCH"):
            self.reopen()

    def test_queue_limit_rejects_without_engine_effect(self):
        self.enqueue()
        sub = self.proposal()
        with patch("eidolon_core.media_worker.MAX_TICKETS", 1):
            with self.assertRaisesRegex(MediaError, "WORKER_CAPACITY"):
                self.enqueue(sub)
        self.assertEqual(self.backend.calls, 0)

    def queued_with_history(self):
        import hashlib
        flow = {"1": {"class_type": "SyntheticSave", "inputs": {"text": "fixture"}}}
        flow_sha = hashlib.sha256(json.dumps(flow, sort_keys=True).encode()).hexdigest()
        class Queued(Backend):
            def plan(self, *a):
                return {"adapter": "comfyui-prompt/2", "endpoint": "http://127.0.0.1:8188", "workflow_sha256": flow_sha}
        ticket = self.enqueue(); self.run_ticket(ticket, backend=Queued())
        history = {"synthetic": {"status": {"completed": True, "status_str": "success"},
                   "prompt": [1, "synthetic", flow, {}, ["1"]],
                   "outputs": {"1": {"images": [{"filename": "result.png", "subfolder": "", "type": "output"}]}}}}
        return ticket, history

    def test_poll_then_collection_single_import_and_bound_result(self):
        ticket, history = self.queued_with_history()
        calls = []
        def get(*args): calls.append(args); return copy.deepcopy(history)
        def raw(*args): calls.append(args); return "image/png", b"\x89PNG\r\n\x1a\noutput"
        observed = self.worker.poll_once(ticket["ticket_id"], client_id="pc", transport=get)
        self.assertEqual(observed["state"], "ENGINE_COMPLETED_UNVERIFIED")
        self.assertNotIn("outputs", observed)
        before = (self.path / ticket["ticket_id"] / "job.json").read_bytes()
        self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts, transport=get, binary_transport=raw)
        count = len(calls)
        self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts, transport=get, binary_transport=raw)
        self.assertEqual(len(calls), count)
        self.assertEqual([a[0] for a in calls], ["GET", "GET", "GET"])
        self.assertEqual((self.path / ticket["ticket_id"] / "job.json").read_bytes(), before)
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["result"]["stage"], "result_unverified")
        self.assertEqual(len(view["result"]["outputs"]), 1)
        self.assertEqual(view["result"]["outputs"][0]["verification"], "hash_verified")
        self.assertEqual(self.pool.inspect()["state"], "RESERVED")

    def test_partial_collection_is_visible_without_duplicate_import(self):
        ticket, history = self.queued_with_history()
        history["synthetic"]["outputs"]["1"]["images"].append({"filename": "second.png", "subfolder": "", "type": "output"})
        reads = []
        def raw(*args):
            reads.append(args)
            if len(reads) == 2: raise TimeoutError("secret/path")
            return "image/png", b"\x89PNG\r\n\x1a\nfirst"
        with self.assertRaisesRegex(MediaError, "MEDIA_COLLECTION_REVIEW_REQUIRED"):
            self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts,
                                     transport=lambda *a: history, binary_transport=raw)
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["result"]["collection"]["imported"], 1)
        self.assertTrue(view["result"]["collection"]["partial"])
        self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts,
                                 transport=lambda *a: self.fail("unexpected GET"))
        self.assertEqual(len(self.artifacts.inventory()["artifacts"]), 1)

    def test_claim_before_collection_target_crash_still_blocks_second_attempt(self):
        ticket, _ = self.queued_with_history()
        with patch("eidolon_core.media_outputs.collect", side_effect=OSError("full")):
            with self.assertRaisesRegex(MediaError, "MEDIA_COLLECTION_REVIEW_REQUIRED"):
                self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts)
        receipt = self.worker.collect_once(ticket["ticket_id"], client_id="pc", artifact_store=self.artifacts,
                                           transport=lambda *a: self.fail("unexpected GET"))
        self.assertTrue(receipt["collection_attempted"])
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv, artifact_store=self.artifacts)
        self.assertEqual(view["observation"], "COLLECTION_UNAVAILABLE_OR_CHANGED")

    def test_worker_requires_resource_pool_before_claim(self):
        ticket = self.enqueue()
        with self.assertRaisesRegex(MediaError, "WORKER_RESOURCE_POOL_REQUIRED"):
            self.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv,
                                 config={}, execute_local=True, backend=self.backend)
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.worker.tickets(client_id="pc")[0]["state"], "ACCEPTED")

    def test_cli_missing_state_not_created_and_errors_do_not_leak_paths(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from eidolon_core.media_worker_cli import main
        missing = self.root / "do-not-create"
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main(["--root", str(self.root / "new"), "--state", str(missing), "init"])
        self.assertEqual(rc, 2); self.assertEqual(out.getvalue(), "")
        self.assertEqual(json.loads(err.getvalue()), {"error": "WORKER_UNAVAILABLE"})
        self.assertFalse(missing.exists())
        self.assertFalse((self.root / "new").exists())

    def test_cli_human_list_preserves_database_and_hides_prompt_paths(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from eidolon_core.media_worker_cli import main
        self.enqueue()
        before = (self.state / "missions.sqlite3").read_bytes(), self.conv.path.read_bytes()
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main(["--root", str(self.path), "--state", str(self.state), "--worker-id", self.marker["worker_id"],
                       "--format", "human", "list", "--client-id", "pc"])
        self.assertEqual(rc, 0, err.getvalue()); self.assertEqual(err.getvalue(), "")
        self.assertIn("Eidolon Core Technologies", out.getvalue()); self.assertIn("ACCEPTED", out.getvalue())
        self.assertNotIn("Un phare", out.getvalue()); self.assertNotIn(str(self.root), out.getvalue())
        self.assertEqual(before, ((self.state / "missions.sqlite3").read_bytes(), self.conv.path.read_bytes()))

    def test_bad_local_configuration_can_be_fixed_without_consuming_ticket(self):
        from eidolon_core.media_backends import LocalMediaBackend
        from tests.test_media_agents import config
        ticket = self.enqueue()
        with self.assertRaises(MediaError):
            self.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv,
                                 config=self.cfg, execute_local=True)
        self.assertEqual(self.worker.tickets(client_id="pc")[0]["state"], "ACCEPTED")
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")
        fixed = {**config(), **self.cfg}
        sent = []
        def transport(*args): sent.append(args); return {"prompt_id": "fixed"}
        result = self.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv,
                                      config=fixed, execute_local=True, backend=LocalMediaBackend(fixed, transport=transport))
        self.assertEqual(result["state"], "RETURNED")
        self.assertEqual(len(sent), 1)

    def test_busy_resource_leaves_waiting_ticket_accepted(self):
        first = self.enqueue(); second = self.enqueue(self.proposal())
        self.run_ticket(first)
        with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVED"):
            self.run_ticket(second)
        self.assertEqual(self.worker.tickets(client_id="pc")[1]["state"], "ACCEPTED")
        self.assertEqual(self.backend.calls, 1)
        current = self.pool.inspect()["current"]
        self.pool.release(current["lease_id"], reviewed_idle=True, reason="Synthetic review")
        self.assertEqual(self.run_ticket(second)["state"], "RETURNED")
        self.assertEqual(self.backend.calls, 2)

    def test_check_offline_has_no_effect_or_path_and_detects_resource_busy(self):
        from tests.test_media_agents import config
        ticket = self.enqueue(); fixed = {**config(), **self.cfg}
        before = (self.path / "queue.json").read_bytes(), self.conv.path.read_bytes()
        with patch("eidolon_core.media_backends.json_http", side_effect=AssertionError("network")):
            ready = self.worker.check(ticket["ticket_id"], client_id="pc", conversations=self.conv, config=fixed)
        self.assertTrue(ready["ready"])
        self.assertEqual(ready["resource_state"], "AVAILABLE")
        self.assertFalse(ready["hardware_qualified"])
        self.assertNotIn(str(self.root), json.dumps(ready))
        self.assertEqual(before, ((self.path / "queue.json").read_bytes(), self.conv.path.read_bytes()))
        self.pool.reserve("media-" + "a" * 32, "video.create")
        blocked = self.worker.check(ticket["ticket_id"], client_id="pc", conversations=self.conv, config=fixed)
        self.assertFalse(blocked["ready"])
        self.assertEqual(self.worker.tickets(client_id="pc")[0]["state"], "ACCEPTED")
