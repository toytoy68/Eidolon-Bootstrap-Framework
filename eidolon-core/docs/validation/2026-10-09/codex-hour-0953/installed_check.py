# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed_check.py
# Description : Recette installée média, configuration des six opérations et précontrôles
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
            request = root / "request.json"; results = {}
            for kind in ("image", "video"):
                for operation in ("create", "edit", "analyze"):
                    req = {"agent": kind, "operation": operation, "prompt": "Scène synthétique"}
                    if operation != "create": req["artifact"] = refs[kind]
                    if operation != "analyze":
                        req["format"] = "square"
                        if kind == "video": req["duration_seconds"] = 5
                    request.write_text(json.dumps(req))
                    assert cli("prepare", "--request", request)["submitted"] is False
                    diagnostic = ("preflight", "--request", request, "--config", config)
                    before = len(calls)
                    local = cli(*diagnostic)
                    assert local["state"] == "LOCAL_INPUTS_VALID" and len(calls) == before
                    observed = cli(*diagnostic, "--probe-local")
                    assert observed["state"] == "PREREQUISITES_OBSERVED"
                    assert observed["submitted"] is False and observed["hardware_qualified"] is False
                    assert observed["execution_authorized"] is False and observed["plan_reusable"] is False
                    assert len(calls) == before + 1
                    job = root / (kind + "-" + operation)
                    args = ("run", "--request", request, "--config", config, "--job", job, "--execute-local")
                    result = cli(*args)
                    before = len(calls); cli(*args, code=2); assert len(calls) == before
                    if operation == "analyze":
                        assert result["state"] == "RESULT_UNVERIFIED"
                        results[kind + "." + operation] = result["state"]
                        continue
                    assert result["state"] == "QUEUED"
                    assert cli("poll", "--job", job)["state"] == "ENGINE_COMPLETED_UNVERIFIED"
                    collection = root / (job.name + "-outputs")
                    args = ("collect", "--job", job, *store_args, "--collection", collection)
                    collected = cli(*args)
                    assert collected["state"] == "OUTPUTS_IMPORTED_UNVERIFIED"
                    assert collected["semantic_content_verified"] is False
                    before = len(calls); cli(*args, code=2); assert len(calls) == before
                    reference = root / "reference.json"; reference.write_text(json.dumps(collected["artifacts"][0]["reference"]))
                    assert cli("artifact-inspect", *store_args, "--reference", reference)["content_hash_checked"] is True
                    exported = root / (job.name + (".png" if kind == "image" else ".mp4"))
                    export_args = ("artifact-export", *store_args, "--reference", reference, "--destination", exported)
                    assert cli(*export_args)["exported"] is True
                    assert exported.read_bytes() == media[kind]
                    cli(*export_args, code=2)
                    assert cli("collection-inspect", "--collection", collection)["state"] == collected["state"]
                    results[kind + "." + operation] = collected["state"]
            assert len(cli("artifacts", *store_args)["artifacts"]) == 6
            assert len(uploaded) == 2 and len(histories) == 4
            print(json.dumps({"status": "PASS", "identical_installed_modules": len(source_files),
                              "modes": results, "artifacts": 6, "verified_uploads": 2,
                              "submissions": 4, "analysis_calls": 2, "exports": 4, "duplicate_retry": False,
                              "offline_preflights_without_network": 6, "metadata_only_probes": 6,
                              "offline_configuration_checks": 3, "incomplete_configuration_exit": 2,
                              "original_sources_deleted_before_runs": True, "real_ffmpeg": True,
                              "real_model": False, "engine_calls": calls}, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    main()
