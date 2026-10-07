# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : core-package-final.py
# Description : Construction hors réseau et recette du paquet en venv jetable
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/. Requires installed setuptools/wheel, never downloads."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
import selectors
import threading
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


def main():
    source = Path.cwd().resolve()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PIP_NO_INDEX"] = "1"
    with tempfile.TemporaryDirectory(prefix="eidolon-package-") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        shutil.copy2(source / "pyproject.toml", project)
        shutil.copytree(source / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))

        def command(args, cwd=root):
            result = subprocess.run(list(map(str, args)), cwd=cwd, env=env,
                                    capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError("isolated package verification failed")
            return result.stdout

        command([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                 "--wheel-dir", root / "wheels", project])
        wheel, = (root / "wheels").glob("*.whl")
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv/bin/python"
        command([python, "-m", "pip", "install", "--no-deps", wheel])
        info = json.loads(command([python, "-c", "import json,eidolon_core; from importlib.metadata import version; "
                                 "print(json.dumps({'path':eidolon_core.__file__,'version':version('eidolon-core')}))"]))
        installed = Path(info["path"]).parent
        assert installed.is_relative_to(root / "venv")
        modules = list((source / "src/eidolon_core").glob("*.py"))
        assert all(p.read_bytes() == (installed / p.name).read_bytes() for p in modules)
        recipe = json.loads(command([python, "-m", "eidolon_core.beta_check", "--web-root", source / "desktop/connected"]))
        assert recipe["status"] == "PASS" and recipe["checks_passed"] == 24
        assert "Eidolon" in command([root / "venv/bin/eidolon-core", "--help"])
        research_state = root / "research-state"
        research_args = [python, "-m", "eidolon_core", "--state", research_state, "--profile", "research-sim"]
        mission = json.loads(command([*research_args, "research", "notice jean@example.invalid", "--required-pages", "2"]))
        assert mission["status"] == "SUCCEEDED" and mission["outcome"]["readable_pages"] == 2
        resumed = json.loads(command([*research_args, "run", mission["id"]]))
        assert resumed == mission
        history = json.loads(command([python, "-m", "eidolon_core.query_history", "--directory", research_state / "research-fixture/guard"]))
        assert len(history["entries"]) == 1 and history["entries"][0]["text"] == "notice"
        assert history["entries"][0]["run_id"] == mission["result"]["research"]["research_guard"]["run_id"]
        before_inspection = (research_state / "missions.sqlite3").read_bytes()
        diagnostic = json.loads(command([python, "-m", "eidolon_core", "--state", research_state,
                                         "runtime-inspect", mission["id"]]))
        assert diagnostic["protocol"] == "eidolon-runtime-inspect/1" and diagnostic["status"] == "SUCCEEDED"
        assert diagnostic["authorizes_execution"] is False and diagnostic["receipt_content_verified"] is False
        assert diagnostic["invocation_budget"]["used"] == 4
        assert "jean@example.invalid" not in json.dumps(diagnostic)
        recovery_state = root / "review-state"
        historical = json.loads(command([python, "-m", "eidolon_core", "recovery-prepare",
                                "--source", research_state / "missions.sqlite3", "--destination", recovery_state,
                                "--actor", "synthetic", "--reason", "installed package verification"]))
        assert historical["execution_authority"] is False and historical["historical_only"] is True
        inspected = json.loads(command([python, "-m", "eidolon_core", "--state", recovery_state,
                                        "recovery-inspect", "--mission-id", mission["id"]]))
        assert inspected["mission"]["status_at_snapshot"] == "SUCCEEDED" and inspected["execution_authority"] is False
        assert (research_state / "missions.sqlite3").read_bytes() == before_inspection
        archives = root / "archives"
        archives.mkdir(mode=0o700)
        archive_args = [python, "-m", "eidolon_core.research_archive", "--directory", archives]
        catalog = json.loads(command([*archive_args, "inspect"]))
        assert catalog["authorizes_execution"] is False
        command([*archive_args, "index"])
        assert (archives / "liste.md").is_file()
        fixture = root / "research-beta"
        generated = json.loads(command([python, "-m", "eidolon_core.beta_fixture", "--output", fixture,
                                        "--profile", "research-archives"]))
        assert generated["status"] == "READY" and generated["mission_count"] == 3
        preflight = json.loads(command([python, "-m", "eidolon_core.http_api", "--state", fixture / "state",
                            "--token-file", fixture / "read-token", "--research-archives", fixture / "archives", "--check"]))
        assert preflight["status"] == "PASS"
        child_code = ("import sys,json;from eidolon_core.http_api import ReadServer,read_token;"
                      "server=ReadServer(sys.argv[1],read_token(sys.argv[2]),port=0,research_archives=sys.argv[3]);"
                      "print(json.dumps({'port':server.server_port}),flush=True);server.serve_forever()")
        child = subprocess.Popen([str(python), "-u", "-c", child_code, str(fixture / "state"),
                                  str(fixture / "read-token"), str(fixture / "archives")], cwd=root,
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                assert selector.select(10), "installed server startup timeout"
                port = json.loads(child.stdout.readline())["port"]
            connection = HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                connection.request("POST", "/v1/research-archives", body='{"limit":2}',
                                   headers={"Authorization": "Bearer " + (fixture / "read-token").read_text().strip(),
                                            "Content-Type": "application/json"})
                response = connection.getresponse()
                page = json.loads(response.read())
                assert response.status == 200 and len(page["items"]) == 2 and page["has_more"]
                assert page["archive_count"] == 3 and page["committed_status_known"] is False
            finally:
                connection.close()
        finally:
            child.terminate()
            try:
                child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.communicate(timeout=5)
        requests = []
        class FakePlanner(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(self.path)
                context = json.loads(body["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
                plan = {"version":1,"steps":[{"id":f"stats-{i}","tool":"text.stats",
                         "parameters":{"reference":f"{item['information_id']}@{item['revision']}"}}
                        for i,item in enumerate(context["items"],1)]}
                payload = json.dumps({"model":"synthetic-package:1b", "done":True,"done_reason":"stop",
                           "message":{"role":"assistant","content":json.dumps(plan)}}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(payload))); self.end_headers(); self.wfile.write(payload)
        server = ThreadingHTTPServer(("127.0.0.1",0),FakePlanner)
        thread = threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.01}); thread.start()
        try:
            config = root / "model.json"
            config.write_text(json.dumps({"version":1,"provider":"ollama",
                "endpoint":f"http://127.0.0.1:{server.server_port}","model":"synthetic-package:1b",
                "options":{"num_predict":512},"timeout_seconds":2}))
            config.chmod(0o600)
            model_args = [python,"-m","eidolon_core","--state",root / "model-state","--model-config",config]
            model_mission = json.loads(command([*model_args,"demo"]))
            assert model_mission["status"] == "SUCCEEDED"
            assert json.loads(command([*model_args,"run",model_mission["id"]])) == model_mission
            assert requests == ["/api/chat"]
        finally:
            server.shutdown(); thread.join(5); server.server_close()
        research_recipe = json.loads(command([python, "-m", "eidolon_core.beta_check", "--web-root",
                                              source / "desktop/connected", "--profile", "research-archives"]))
        assert research_recipe["status"] == "PASS" and research_recipe["checks_passed"] == 25
        report = {"research_recipe": research_recipe, "installed_archive_http": {"fixture_missions":3,"archives":3,"first_page":2,"status":"PASS"},
                  "installed_model_cli":{"status":"PASS","synthetic_http_only":True,"model_requests":1,
                                          "resume_unchanged":True,"real_model_qualified":False},
                  "archive_cli_installed": True, "inspection_profile": {"status": "PASS", "original_state_unchanged": True,
                  "runtime_inspection_read_only": True, "recovery_copy_stays_historical": True}, "research_profile": {"status": mission["status"], "readable_pages": 2,
                  "resume_unchanged": True, "history_entries": 1, "cleaned_text_verified": True},
                  "status": "PASS", "offline_build": True, "isolated_install": True,
                  "installed_modules_match_source": len(modules), "version": info["version"],
                  "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "recipe": recipe}
    report["temporary_files_removed"] = not root.exists()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
