# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed_media_worker.py
# Description : Recette worker installé : propositions persistées, six modes et HTTP moteur simulé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Execute with installed venv Python. Real CLI/HTTP/FFmpeg; no model or GPU."""
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

import eidolon_core.media_agents as agents
from eidolon_core import conversation as cv, conversation_media as cm
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.contracts import digest, encode
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.store import Store
from eidolon_core.media_worker import MediaWorker


def main():
    repo = Path(__file__).resolve().parents[4]
    installed = Path(agents.__file__).parent
    source_files = sorted((repo / "src/eidolon_core").glob("*.py"))
    assert installed != repo / "src/eidolon_core"
    assert all((installed / p.name).read_bytes() == p.read_bytes() for p in source_files)
    calls, uploaded, histories, output_bytes = [], {}, {}, {}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append("POST " + self.path)
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/upload/image":
                msg = BytesParser(policy=policy.default).parsebytes(
                    ("Content-Type: " + self.headers["Content-Type"] + "\r\n\r\n").encode() + raw)
                parts = {p.get_param("name", header="content-disposition"): p for p in msg.iter_parts()}
                assert parts["overwrite"].get_payload(decode=True) == b"false"
                name = parts["image"].get_filename(); assert name not in uploaded
                uploaded[name] = parts["image"].get_payload(decode=True)
                return self.reply({"name": name, "subfolder": "", "type": "input"})
            body = json.loads(raw)
            if self.path == "/api/show":
                assert set(body) == {"model", "verbose"} and body["verbose"] is False
                return self.reply({"capabilities": ["completion", "vision"]})
            if self.path == "/api/generate":
                assert 1 <= len(body["images"]) <= 8
                return self.reply({"model": body["model"], "done": True, "done_reason": "stop", "response": "Observation synthétique."})
            assert self.path == "/prompt"
            flow = body["prompt"]; inputs = flow["1"]["inputs"]
            if "source" in inputs:
                assert inputs["source"] in uploaded
            kind = "video" if "duration" in inputs else "image"
            pid = "installed-" + str(len(histories) + 1)
            name = pid + (".mp4" if kind == "video" else ".png")
            histories[pid] = {"prompt": [1, pid, flow, {}, ["1"]],
                              "status": {"completed": True, "status_str": "success"},
                              "outputs": {"1": {"videos" if kind == "video" else "images": [
                                  {"filename": name, "subfolder": "", "type": "output"}]}}}
            output_bytes[name] = media[kind]
            self.reply({"prompt_id": pid})
        def do_GET(self):
            calls.append("GET " + self.path.split("?")[0])
            u = urlsplit(self.path)
            if u.path == "/object_info/SyntheticFixture":
                return self.reply({"SyntheticFixture": {"name": "SyntheticFixture", "input": {
                    "required": {"text": ["STRING", {}], "width": ["INT", {}], "height": ["INT", {}]},
                    "optional": {"duration": ["INT", {}], "source": [["not-uploaded-yet.png"], {}]}}}})
            if u.path.startswith("/history/"):
                pid = u.path.rsplit("/", 1)[-1]
                return self.reply({pid: histories[pid]})
            assert u.path == "/view"
            query = parse_qs(u.query)
            body = (uploaded if query["type"] == ["input"] else output_bytes)[query["filename"][0]]
            self.reply(body, "video/mp4" if query["filename"][0].endswith(".mp4") else "image/png")
        def reply(self, value, kind="application/json"):
            body = value if type(value) is bytes else json.dumps(value).encode()
            self.send_response(200); self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="eidolon-media-recipe-") as directory:
            root = Path(directory)
            subprocess.run(["/usr/bin/ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=blue:s=64x64:r=2", "-t", "2", "-threads", "1", "-c:v", "mpeg4",
                            str(root / "fixture.mp4")], check=True, timeout=20)
            subprocess.run(["/usr/bin/ffmpeg", "-nostdin", "-v", "error", "-i", str(root / "fixture.mp4"),
                            "-frames:v", "1", "-threads", "1", str(root / "fixture.png")], check=True, timeout=20)
            media = {"image": (root / "fixture.png").read_bytes(), "video": (root / "fixture.mp4").read_bytes()}
            env = dict(os.environ); env.pop("PYTHONPATH", None)
            def cli(*args, code=0, report_on_stdout=False):
                p = subprocess.run([str(Path(sys.executable).parent / "eidolon-media"), *map(str, args)],
                                   cwd=root, env=env, capture_output=True, text=True, timeout=45)
                assert p.returncode == code, (args, p.returncode, p.stderr)
                return json.loads(p.stdout if code == 0 or report_on_stdout else p.stderr)
            assert len(cli("agents")["agents"]) == 2
            store = root / "artifacts"
            marker = cli("artifact-init", "--root", store)
            store_args = ("--root", store, "--store-id", marker["store_id"])
            refs = {}
            for kind, suffix in (("image", "png"), ("video", "mp4")):
                manifest = cli("artifact-import", *store_args, "--source", root / ("fixture." + suffix))
                refs[kind] = manifest["reference"]
                (root / ("fixture." + suffix)).unlink()
                reference_file = root / (kind + "-reference.json")
                reference_file.write_text(json.dumps(refs[kind]))
                metadata = cli("artifact-probe", *store_args, "--reference", reference_file, "--ffprobe", "/usr/bin/ffprobe")
                assert metadata["state"] == "METADATA_OBSERVED"
                assert (metadata["observed"]["width"], metadata["observed"]["height"]) == (64, 64)
                assert metadata["full_file_decoded"] is False and metadata["semantic_content_verified"] is False
            cfg = {"comfy_endpoint": "http://127.0.0.1:" + str(server.server_port),
                   "ollama_endpoint": "http://127.0.0.1:" + str(server.server_port),
                   "vision_model": "fixture:local", "ffmpeg": "/usr/bin/ffmpeg",
                   "source_transfer": "upload-verified", "artifact_store": {"root": str(store), "store_id": marker["store_id"]},
                   "workflows": {}}
            for kind in ("image", "video"):
                for operation in ("create", "edit"):
                    fields = {"prompt": "text", "width": "width", "height": "height"}
                    if kind == "video": fields["duration_seconds"] = "duration"
                    if operation == "edit": fields["source"] = "source"
                    cfg["workflows"][kind + "." + operation] = {
                        "prompt": {"1": {"class_type": "SyntheticFixture", "inputs": {v: "" for v in fields.values()}}},
                        "bindings": {k: ["1", v] for k, v in fields.items()}}
            pool = root / "resources"
            pool_marker = cli("resource-init", "--root", pool)
            pool_args = ("--root", pool, "--pool-id", pool_marker["pool_id"])
            cfg["resource_pool"] = {"root": str(pool), "pool_id": pool_marker["pool_id"]}
            def release_resource(result):
                before = len(calls)
                observed = cli("resource-inspect", *pool_args)
                assert observed["state"] == "RESERVED"
                assert observed["current"]["lease_id"] == result["resource_reservation"]["lease_id"]
                released = cli("resource-release", *pool_args, "--lease-id", observed["current"]["lease_id"],
                               "--reviewed-idle", "--reason", "Simulated engine completion independently observed")
                assert released["state"] == "RELEASED_BY_OPERATOR" and released["engine_idle_verified"] is False
                assert cli("resource-inspect", *pool_args)["state"] == "AVAILABLE"
                assert len(calls) == before
            config = root / "config.json"; config.write_text(json.dumps(cfg))
            setup = cli("config-check", "--config", config)
            assert setup["state"] == "CONFIGURED_SCOPE" and len(setup["operations"]) == 6
            assert setup["artifact_store"]["state"] == "IDENTITY_OBSERVED"
            assert setup["artifact_store"]["contents_checked"] is False
            assert setup["server_contacted"] is False and setup["execution_authorized"] is False and calls == []
            incomplete = root / "incomplete.json"; incomplete.write_text("{}")
            missing = cli("config-check", "--config", incomplete, code=2, report_on_stdout=True)
            assert missing["state"] == "INCOMPLETE" and calls == []
            partial = root / "partial.json"
            partial.write_text(json.dumps({k: cfg[k] for k in ("ollama_endpoint", "vision_model")}))
            scoped = cli("config-check", "--config", partial, "--require", "image.analyze")
            assert scoped["state"] == "CONFIGURED_SCOPE" and scoped["required_operations"] == ["image.analyze"] and calls == []
            state = root / "state"
            conversations = ConversationStore(Store(state), create=True)
            cid = conversations.open(client_id="fixture", client_key="worker-recipe")["conversation_id"]
            credentials = ClientCredentials(conversations.store, create=True)
            paired = credentials.pair(client_id="fixture", actor="synthetic operator")
            authenticated = credentials.authenticate(paired["token"])
            for ref in refs.values():
                from eidolon_core.media_artifacts import ArtifactStore
                artifact_store = ArtifactStore(store, expected_store_id=marker["store_id"])
                conversations.attach(owner_client_id="fixture", conversation_id=cid, reference=ref,
                                     verify=lambda r: cm.check_artifact(artifact_store, r))
            worker_root = root / "worker"
            worker_command = [str(Path(sys.executable).parent / "eidolon-media-worker"), "--root", str(worker_root),
                              "--state", str(state)]
            p = subprocess.run(worker_command + ["init"], cwd=root, env=env, capture_output=True, text=True, timeout=10)
            assert p.returncode == 0, p.stderr
            worker_marker = json.loads(p.stdout)
            worker_command += ["--worker-id", worker_marker["worker_id"]]
            worker = MediaWorker(worker_root, worker_id=worker_marker["worker_id"], store_id=conversations.store_id)
            def worker_cli(*args, code=0, human=False):
                p = subprocess.run(worker_command + (["--format", "human"] if human else []) + list(map(str,args)),
                                   cwd=root, env=env, capture_output=True, text=True, timeout=45)
                assert p.returncode == code, (args, p.returncode, p.stderr)
                return p.stdout if human else json.loads(p.stdout if code == 0 else p.stderr)
            previous, results = None, {}
            for kind in ("image", "video"):
                for operation in ("create", "edit", "analyze"):
                    name = kind + "." + operation
                    parameters = {"prompt": "Scène synthétique"}
                    if operation != "create": parameters["artifact_id"] = refs[kind]["artifact_id"]
                    if operation != "analyze":
                        parameters["format"] = "square"
                        if kind == "video": parameters["duration_seconds"] = 5
                    turn = conversations.append_turn(cid, client_id="fixture", client_turn_key=name, text=name)["turn"]
                    reply_kind, proposal = cm.propose(conversations, turn, {"template": "media." + name,
                        "parameters": parameters}, owner_client_id="fixture", previous=previous)
                    assert reply_kind == "PROPOSAL"
                    # TRUSTED TEST FIXTURE: G122 owns the dialogue/reply persistence.
                    # Seed a canonical media proposal into the real v4 table. The worker
                    # must read it through the REAL current_proposal method, not a mock.
                    with conversations._db(write=True) as database:
                        database.execute("INSERT INTO proposals VALUES (?,?,?,?,?)", (proposal["proposal_id"],
                            proposal["version"],cid,encode(proposal),digest(proposal)))
                    previous = proposal
                    submission = {"protocol":cv.SUBMISSION_PROTOCOL,"store_id":conversations.store_id,
                        "client_id":"fixture","command_key":name,"conversation_id":cid,
                        "proposal_id":proposal["proposal_id"],"proposal_version":proposal["version"],
                        "proposal_sha256":digest(proposal),"actor":authenticated["actor"],
                        "reason":"Accord humain synthétique"}
                    before = len(calls)
                    ticket = worker.enqueue(submission, conversations=conversations,
                        authenticated_client_id=authenticated["client_id"],authenticated_actor=authenticated["actor"])
                    assert ticket["state"] == "ACCEPTED" and len(calls) == before
                    assert worker.enqueue(submission, conversations=conversations,
                        authenticated_client_id=authenticated["client_id"],authenticated_actor=authenticated["actor"]) == ticket
                    own = ("--client-id", "fixture", "--ticket", ticket["ticket_id"])
                    assert worker_cli("check", *own, "--config", config)["ready"] is True
                    assert len(calls) == before
                    run = ("run", *own, "--config", config, "--execute-local")
                    done = worker_cli(*run)
                    assert done["state"] == "RETURNED" and done["job_id"] == ticket["job_id"]
                    before = len(calls)
                    assert worker_cli(*run) == done and len(calls) == before
                    result_args = ("result", *own, "--artifact-root", store, "--artifact-store-id", marker["store_id"])
                    view = worker_cli(*result_args)
                    assert view["result"]["binding"] == "MATCHED" and view["result"]["job_id"] == ticket["job_id"]
                    assert view["result"]["success_claim"] is False
                    if operation != "analyze":
                        polled = worker_cli("poll", *own)
                        assert polled["state"] == "ENGINE_COMPLETED_UNVERIFIED" and "outputs" not in polled
                        collection_args = ("collect", *own, "--artifact-root", store,
                                           "--artifact-store-id", marker["store_id"], "--collect-local")
                        worker_cli(*collection_args)
                        before = len(calls); worker_cli(*collection_args); assert len(calls) == before
                        view = worker_cli(*result_args)
                        assert view["result"]["collection"]["imported"] == 1
                        assert view["result"]["collection"]["partial"] is False
                        assert view["result"]["outputs"][0]["verification"] == "hash_verified"
                    else:
                        assert view["result"]["observation"]["verified"] is False
                    before = len(calls)
                    queue_before = (worker_root / "queue.json").read_bytes()
                    rendered = worker_cli(*result_args, human=True)
                    assert "Eidolon Core Technologies" in rendered and "[OK]" not in rendered
                    assert str(root) not in rendered
                    assert (worker_root / "queue.json").read_bytes() == queue_before and len(calls) == before
                    held = cli("resource-inspect", *pool_args)
                    assert held["state"] == "RESERVED" and held["current"]["job_id"] == ticket["job_id"]
                    release_resource({"resource_reservation": held["current"]})
                    results[name] = view["result"]["stage"]
            assert len(worker_cli("list", "--client-id", "fixture")["tickets"]) == 6
            assert worker_cli("list", "--client-id", "other")["tickets"] == []
            assert len(uploaded) == 2 and len(histories) == 4
            assert len(cli("artifacts", *store_args)["artifacts"]) == 6
            print(json.dumps({"status":"PASS", "identical_installed_modules":len(source_files),
                "modes":results,"verified_uploads":2,"engine_queue_submissions":4,"analysis_calls":2,
                "durable_tickets":6,"duplicate_engine_calls":0,"collections":4,"duplicate_imports":0,
                "private_human_result_inspections":6,"explicit_resource_releases":6,
                "real_ffmpeg":True,"real_ffprobe":True,"real_http_loopback":True,"real_model":False,
                "conversation_proposals_seeded_directly_as_trusted_fixture":True,
                "dialogue_and_submission_http_flow_tested":False,"engine_calls":calls},indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    main()
