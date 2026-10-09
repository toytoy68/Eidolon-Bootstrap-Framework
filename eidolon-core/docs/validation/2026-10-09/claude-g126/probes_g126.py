# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g126.py
# Description : Contre-revue indépendante du worker média C-064..C-067 par le vrai parcours conversation (C-TASK-G126)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 -m unittest discover -s docs/validation/2026-10-09/claude-g126 -p 'probes_*.py' -v

Independent of Codex's tests: proposals are frozen by the REAL dialogue and stored by the REAL
conversation store (no patched current_proposal); submissions go through the REAL API. Only the
engine is simulated (a backend object counting calls). media_*.py is never modified.
Each probe states the property; a failing probe is a finding to report, not to fix here."""
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from eidolon_core import conversation as cv
from eidolon_core import conversation_media as cm
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.contracts import digest
from eidolon_core.conversation_api import ConversationAPI
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.http_api import open_media_workspace
from eidolon_core.media_agents import MediaError
from eidolon_core.media_resources import ResourcePool
from eidolon_core.media_worker import MediaWorker
from eidolon_core.media_workspace import initialize as workspace_init, inspect as workspace_inspect
from eidolon_core.store import Store

HERE = Path(__file__).resolve().parent
PNG = b"\x89PNG\r\n\x1a\nprobe source"


class Engine:
    """Simulated engine: counts every call; never contacts anything."""
    def __init__(self, fail=None):
        self.calls, self.fail = 0, fail

    def plan(self, *args):
        return {"adapter": "claude-g126-probe"}

    def run(self, request, *args, progress):
        self.calls += 1
        progress("ANALYSIS_SUBMITTING" if request["operation"] == "analyze" else "QUEUE_SUBMITTING", {})
        if self.fail:
            raise MediaError(self.fail)
        if request["operation"] == "analyze":
            return {"state": "RESULT_UNVERIFIED", "text": "<b>Observation</b> non vérifiée"}
        return {"state": "QUEUED", "prompt_id": "probe"}


def concurrent_run(state, root, worker_id, store_id, ticket, config, barrier, results, calls):
    conv = ConversationStore(Store(state))
    worker = MediaWorker(root, worker_id=worker_id, store_id=store_id)

    class Counting(Engine):
        def run(self, *a, **k):
            with calls.get_lock():
                calls.value += 1
            return super().run(*a, **k)
    barrier.wait(timeout=20)
    try:
        results.put(worker.run_once(ticket, client_id="pc", conversations=conv, config=config,
                                    execute_local=True, backend=Counting())["state"])
    except MediaError as exc:
        results.put(exc.code)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / "state"
        self.runtime = synthetic_runtime(Store(self.state))
        self.conv = ConversationStore(self.runtime.store, create=True)
        creds = ClientCredentials(self.runtime.store, create=True)
        self.key = creds.pair(client_id="pc", actor="toytoy")["token"]
        self.other_key = creds.pair(client_id="intrus", actor="autre")["token"]
        made = workspace_init(self.base / "media", state=str(self.state))
        self.workspace_id = made["workspace_id"]
        self.worker, self.artifacts = open_media_workspace(str(self.base / "media"), self.workspace_id)
        self.config = json.loads((self.base / "media" / "media.json").read_text())
        self.api = ConversationAPI(self.runtime, dialogue_model=SimulatedDialogueModel(self.runtime.catalog),
                                   media_worker=self.worker, media_artifacts=self.artifacts)
        self.cid = self.post("open", {"client_key": "g126"})[1]["conversation_id"]
        self.n = 0

    def post(self, route, body, key=None):
        headers = {"Authorization": ["Bearer " + (key or self.key)], "Content-Type": ["application/json"]}
        return self.api.handle("POST", "/v1/conversations/" + route, headers, json.dumps(body).encode())

    def say(self, text):
        self.n += 1
        return self.post("turn", {"conversation_id": self.cid, "client_turn_key": f"t{self.n}", "text": text})[1]["reply"]

    def submit(self, reply, key="s1", **changes):
        p = reply["proposal"]
        body = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": self.conv.store_id, "client_id": "pc",
                "command_key": key, "conversation_id": self.cid, "proposal_id": p["proposal_id"],
                "proposal_version": p["version"], "proposal_sha256": reply["proposal_sha256"], "actor": "toytoy",
                "reason": "Accord humain synthétique"}
        body.update(changes)
        return self.post("submit", body)

    def ticket(self, text="Crée une image : un phare", key="s1"):
        status, ticket = self.submit(self.say(text), key=key)
        self.assertEqual(status, 200, ticket)
        return ticket

    def run_ticket(self, ticket, engine, client="pc", **kw):
        return self.worker.run_once(ticket["ticket_id"], client_id=client, conversations=self.conv,
                                    config=kw.get("config", self.config), execute_local=True, backend=engine)

    def attach(self):
        ref = self.artifacts.import_bytes(PNG, display_name="phare.png")["reference"]
        self.conv.attach(owner_client_id="pc", conversation_id=self.cid, reference=ref,
                         verify=lambda r: cm.check_artifact(self.artifacts, r))
        return ref

    def pool(self):
        return ResourcePool(Path(self.config["resource_pool"]["root"]), self.config["resource_pool"]["pool_id"])


class ConsentAndOwnership(Base):
    def test_p1_a_newer_proposal_makes_the_older_one_unsubmittable(self):
        first = self.say("Crée une image : un phare")
        self.say("Crée une image : un phare au crépuscule")
        status, body = self.submit(first)
        self.assertEqual((status, body["error"]), (409, "PROPOSAL_STALE"))
        self.assertEqual(self.worker.tickets(client_id="pc"), [])

    def test_p2_consent_given_then_superseded_before_the_operator_runs(self):
        """FINDING CANDIDATE: a ticket accepted for v1 still runs after the human froze v2."""
        ticket = self.ticket("Crée une image : un phare")
        self.say("Crée une image : plutôt une forêt")             # the human changed their mind (v2)
        engine = Engine()
        try:
            state = self.run_ticket(ticket, engine)["state"]
        except MediaError as exc:
            state = exc.code
        self.__class__.p2_observed = {"state": state, "engine_calls": engine.calls}
        print("P2_OBSERVED", json.dumps({"state": state, "engine_calls": engine.calls}))
        # Recorded, not asserted: the contract (MEDIA-WORKER.md) does not say; see the report.
        self.assertIn(state, {"RETURNED", "MEDIA_PROPOSAL_SUPERSEDED", "PROPOSAL_STALE"})

    def test_p3_ticket_id_is_not_a_right(self):
        ticket = self.ticket()
        engine = Engine()
        with self.assertRaises(MediaError) as caught:
            self.run_ticket(ticket, engine, client="intrus")
        self.assertEqual((caught.exception.code, engine.calls), ("MEDIA_TICKET_UNKNOWN", 0))
        with self.assertRaises(MediaError):
            self.worker.result(ticket["ticket_id"], client_id="intrus", conversations=self.conv,
                               artifact_store=self.artifacts)
        self.assertEqual(self.post("media_results", {"conversation_id": self.cid}, key=self.other_key)[0], 404)

    def test_p4_replayed_key_with_changed_content_is_refused(self):
        reply = self.say("Crée une image : un phare")
        self.assertEqual(self.submit(reply)[0], 200)
        status, body = self.submit(reply, reason="Autre motif")
        self.assertEqual((status, body["error"]), (409, "MEDIA_COMMAND_KEY_REUSED"))
        status, body = self.submit(reply, key="s2")
        self.assertEqual((status, body["error"]), (409, "MEDIA_PROPOSAL_ALREADY_SUBMITTED"))
        self.assertEqual(len(self.worker.tickets(client_id="pc")), 1)


class OneAttemptOnly(Base):
    def test_p5_four_concurrent_processes_call_the_engine_once(self):
        ticket = self.ticket()
        ctx = multiprocessing.get_context("fork")
        barrier, results, calls = ctx.Barrier(4), ctx.Queue(), ctx.Value("i", 0)
        procs = [ctx.Process(target=concurrent_run, args=(str(self.state), str(self.base / "media" / "worker"),
                                                          self.worker.worker_id, self.conv.store_id,
                                                          ticket["ticket_id"], self.config, barrier, results, calls))
                 for _ in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(60)
        outcomes = sorted(results.get(timeout=5) for _ in procs)
        self.assertEqual(calls.value, 1, outcomes)
        self.assertEqual(outcomes.count("RETURNED") + outcomes.count("WORKER_BUSY"), 4, outcomes)

    def test_p6_crash_between_reservation_and_engine_return(self):
        ticket = self.ticket()
        done = subprocess.run([sys.executable, str(HERE / "crash_g126.py"), str(self.state),
                               str(self.base / "media" / "worker"), self.worker.worker_id, self.conv.store_id,
                               ticket["ticket_id"], json.dumps(self.config)],
                              env=dict(os.environ), capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 77, done.stderr[-400:])
        worker = MediaWorker(self.base / "media" / "worker", worker_id=self.worker.worker_id, store_id=self.conv.store_id)
        receipt = worker.receipt(client_id="pc", command_key="s1")
        self.assertEqual(receipt["state"], "ATTEMPTED")                      # durable before the engine call
        self.assertEqual(self.pool().inspect()["state"], "RESERVED")         # never released implicitly
        engine = Engine()
        again = worker.run_once(ticket["ticket_id"], client_id="pc", conversations=self.conv, config=self.config,
                                execute_local=True, backend=engine)
        self.assertEqual((again["state"], engine.calls, again["automatic_retry"]), ("ATTEMPTED", 0, False))

    def test_p7_engine_deadline_after_submission_is_review_required_and_never_resent(self):
        ticket = self.ticket()
        engine = Engine(fail="MEDIA_HTTP_DEADLINE")
        with self.assertRaises(MediaError) as caught:
            self.run_ticket(ticket, engine)
        self.assertEqual(caught.exception.code, "MEDIA_ATTEMPT_UNCERTAIN")
        self.assertEqual(self.worker.receipt(client_id="pc", command_key="s1")["state"], "REVIEW_REQUIRED")
        self.assertEqual(self.pool().inspect()["state"], "RESERVED")
        second = Engine()
        self.assertEqual(self.run_ticket(ticket, second)["state"], "REVIEW_REQUIRED")
        self.assertEqual(second.calls, 0)


class InputsAndReservation(Base):
    def edit_ticket(self):
        self.attach()
        return self.ticket("Retouche la photo : ajoute un ciel étoilé")

    def test_p8_missing_or_modified_source_consumes_no_attempt(self):
        ticket = self.edit_ticket()
        root = self.base / "media" / "artifacts"
        art = next(p for p in root.iterdir() if p.name.startswith("ma-"))
        payload = art / "payload"
        body = bytearray(payload.read_bytes()); body[-1] ^= 1; payload.write_bytes(bytes(body))
        engine = Engine()
        with self.assertRaises(Exception):
            self.run_ticket(ticket, engine)
        self.assertEqual((engine.calls, self.worker.receipt(client_id="pc", command_key="s1")["state"]), (0, "ACCEPTED"))
        body[-1] ^= 1; payload.write_bytes(bytes(body))                     # restored: same ticket can run once
        self.assertEqual(self.run_ticket(ticket, engine)["state"], "RETURNED")
        self.assertEqual(engine.calls, 1)

    def test_p9_a_held_gpu_reservation_refuses_before_any_attempt(self):
        ticket = self.ticket()
        lease = self.pool().reserve("media-" + "f" * 32, "image.create")
        # worker.check() needs a real engine configuration (no backend parameter): not usable with a
        # simulated engine, so the refusal is observed on run_once itself.
        engine = Engine()
        with self.assertRaises(MediaError) as caught:
            self.run_ticket(ticket, engine)
        self.assertEqual((caught.exception.code, engine.calls), ("RESOURCE_RESERVED", 0))
        self.assertEqual(self.worker.receipt(client_id="pc", command_key="s1")["state"], "ACCEPTED")
        self.assertTrue(lease)

    def test_p10_no_state_claims_success_and_analysis_text_stays_unverified(self):
        self.attach()
        ticket = self.ticket("Analyse la photo : décris-la")
        self.assertEqual(self.run_ticket(ticket, Engine())["state"], "RETURNED")
        view = self.worker.result(ticket["ticket_id"], client_id="pc", conversations=self.conv,
                                  artifact_store=self.artifacts)
        self.assertEqual((view["receipt"]["success_claim"], view["result"]["success_claim"]), (False, False))
        self.assertEqual(view["result"]["observation"], {"text": "<b>Observation</b> non vérifiée", "verified": False})
        body = self.post("media_results", {"conversation_id": self.cid})[1]
        self.assertNotIn(self.tmp.name, json.dumps(body))


class Workspace(Base):
    def test_p11_interrupted_workspace_init_is_never_reused(self):
        for stage in ("intent", "artifacts", "resources", "worker", "configuration"):
            target = self.base / f"ws-{stage}"

            def cut(name, stage=stage):
                if name == stage:
                    raise KeyboardInterrupt(stage)
            with self.assertRaises(KeyboardInterrupt):
                workspace_init(target, state=str(self.state), checkpoint=cut)
            record = json.loads((target / "workspace.json").read_text())
            report = workspace_inspect(target, workspace_id=record["workspace_id"])
            self.assertEqual(report["state"], "REVIEW_REQUIRED", stage)
            with self.assertRaises(FileExistsError):
                workspace_init(target, state=str(self.state))
            with self.assertRaises(ValueError):
                open_media_workspace(str(target), record["workspace_id"])

    def test_p12_replaced_configuration_or_identity_is_refused_at_server_start(self):
        cfg = self.base / "media" / "media.json"
        good = cfg.read_text()
        cfg.write_text(json.dumps({**json.loads(good), "artifact_store": {"root": "/ailleurs", "store_id": "mas-" + "0" * 32}}))
        with self.assertRaises(ValueError):
            open_media_workspace(str(self.base / "media"), self.workspace_id)
        cfg.write_text(good)
        with self.assertRaises(Exception):
            open_media_workspace(str(self.base / "media"), "mws-" + "0" * 32)


if __name__ == "__main__":
    unittest.main()
