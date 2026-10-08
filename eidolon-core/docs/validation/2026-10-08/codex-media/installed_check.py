# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed_check.py
# Description : Recette des agents installés sur deux API locales simulées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with the installed venv Python, outside source imports. No real model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

import eidolon_core.media_agents as agents


def main():
    repo = Path(__file__).resolve().parents[4]
    installed = Path(agents.__file__).parent
    source = repo / "src/eidolon_core"
    source_files = sorted(source.glob("*.py"))
    assert all((installed / p.name).read_bytes() == p.read_bytes() for p in source_files)
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(self.path)
            result = ({"prompt_id": "installed-job"} if self.path == "/prompt" else
                      {"model": body["model"], "done": True, "done_reason": "stop", "response": "Test synthétique."})
            self.reply(result)
        def do_GET(self):
            calls.append(self.path)
            self.reply({"installed-job": {"status": {"completed": True, "status_str": "success"}, "outputs": {}}})
        def reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="eidolon-media-installed-") as directory:
            root = Path(directory)
            env = dict(os.environ); env.pop("PYTHONPATH", None)
            def cli(*args, code=0):
                p = subprocess.run([str(Path(sys.executable).parent / "eidolon-media"), *args],
                                   cwd=root, env=env, capture_output=True, text=True, timeout=20)
                assert p.returncode == code, (p.returncode, p.stderr)
                return json.loads(p.stdout if code == 0 else p.stderr)
            assert len(cli("agents")["agents"]) == 2
            png = root / "source.png"; png.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
            url = "http://127.0.0.1:" + str(server.server_port)
            cfg = {"ollama_endpoint": url, "vision_model": "fixture:local", "comfy_endpoint": url,
                   "workflows": {"image.create": {"prompt": {"1": {"class_type": "SyntheticFixture", "inputs": {"text": "", "width": 0, "height": 0}}},
                                                   "bindings": {"prompt": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"]}}}}
            config = root / "config.json"; config.write_text(json.dumps(cfg))
            req = root / "request.json"
            req.write_text(json.dumps({"agent": "image", "operation": "analyze", "prompt": "Décris", "source": str(png)}))
            assert cli("prepare", "--request", str(req))["submitted"] is False
            job = root / "analysis"
            result = cli("run", "--request", str(req), "--config", str(config), "--job", str(job), "--execute-local")
            assert result["state"] == "RESULT_UNVERIFIED" and result["verified"] is False
            assert cli("inspect", "--job", str(job))["source_evidence"]["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
            cli("run", "--request", str(req), "--config", str(config), "--job", str(job), "--execute-local", code=2)
            req.write_text(json.dumps({"agent": "image", "operation": "create", "prompt": "Un atelier", "format": "square"}))
            queued = root / "generation"
            assert cli("run", "--request", str(req), "--config", str(config), "--job", str(queued), "--execute-local")["state"] == "QUEUED"
            assert cli("poll", "--job", str(queued))["state"] == "ENGINE_COMPLETED_UNVERIFIED"
            assert calls == ["/api/generate", "/prompt", "/history/installed-job"]
            print(json.dumps({"status": "PASS", "identical_modules": len(source_files), "agents": 2,
                              "cli_analyze": "RESULT_UNVERIFIED", "cli_generate": "QUEUED",
                              "poll": "ENGINE_COMPLETED_UNVERIFIED", "duplicate_resubmission": False,
                              "engine_calls": calls, "real_model": False}, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    main()
