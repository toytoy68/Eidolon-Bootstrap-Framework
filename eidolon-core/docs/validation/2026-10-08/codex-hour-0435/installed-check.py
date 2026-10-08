# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed-check.py
# Description : Recette hors réseau du paquet installé et des nouvelles CLI
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/. Disposable venv, synthetic reports and loopback servers."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import venv


def main():
    source = Path.cwd().resolve()
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_NO_INDEX"] = "1"
    with tempfile.TemporaryDirectory(prefix="eidolon-package-1008-") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        shutil.copy2(source / "pyproject.toml", project)
        shutil.copytree(source / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))

        def command(args, expected=0):
            completed = subprocess.run(list(map(str, args)), cwd=root, env=environment,
                                       capture_output=True, text=True, timeout=60)
            if completed.returncode != expected or completed.stderr and expected != 0:
                raise AssertionError("installed command returned an unexpected status/diagnostic")
            return completed.stdout

        command([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                 "--wheel-dir", root / "wheels", project])
        wheel, = (root / "wheels").glob("*.whl")
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv/bin/python"
        cli = root / "venv/bin/eidolon-core"
        command([python, "-m", "pip", "install", "--no-deps", wheel])
        package_path = Path(command([python, "-c", "import eidolon_core;print(eidolon_core.__file__)"]).strip()).parent
        assert package_path.is_relative_to(root / "venv")
        modules = list((source / "src/eidolon_core").glob("*.py"))
        assert all(path.read_bytes() == (package_path / path.name).read_bytes() for path in modules)
        assert "qualification-check" in command([cli, "--help"])

        qualifications = []
        for filename, code, verdict in (("passed-scope-synthetic.json", 0, "PASSED_SCOPE"),
                                         ("incomplete-missing-measure.json", 2, "INCOMPLETE"),
                                         ("rejected-one-violation.json", 3, "REJECTED")):
            report_file = root / filename
            shutil.copy2(source / "examples/qualification" / filename, report_file)
            before = report_file.read_bytes()
            result = json.loads(command([cli, "--state", root / "must-not-exist", "qualification-check",
                                         "--report", report_file], expected=code))
            assert result["status"] == verdict
            assert result["report_sha256"] == hashlib.sha256(before).hexdigest()
            assert result["authorizes_execution"] is False and result["telemetry_authenticated"] is False
            assert report_file.read_bytes() == before and not (root / "must-not-exist").exists()
            qualifications.append({"status": verdict, "exit_code": code})

        requests = []
        synthetic_key = "synthetic-package-credential-not-for-logs"

        class FakePlanner(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, self.headers.get("Authorization")))
                context = json.loads(body["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
                plan = {"version": 1, "steps": [{"id": f"stats-{i}", "tool": "text.stats",
                        "parameters": {"reference": f"{item['information_id']}@{item['revision']}"}}
                        for i, item in enumerate(context["items"], 1)]}
                message = {"role": "assistant", "content": json.dumps(plan)}
                payload = ({"model": body["model"], "done": True, "done_reason": "stop", "message": message}
                           if self.path == "/api/chat" else
                           {"model": body["model"], "object": "chat.completion",
                            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
                            "usage": {"prompt_tokens": 300, "completion_tokens": 12, "total_tokens": 312}})
                raw = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(("127.0.0.1", 0), FakePlanner)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        model_results = []
        try:
            for provider, token_option, path in (("ollama", "num_predict", "/api/chat"),
                                                  ("llama-server", "max_tokens", "/v1/chat/completions")):
                config = {"version": 1, "provider": provider, "model": "synthetic-package:1b",
                          "endpoint": f"http://127.0.0.1:{server.server_port}",
                          "options": {token_option: 512}, "timeout_seconds": 2}
                if provider == "llama-server":
                    config["api_key_env"] = "EIDOLON_PACKAGE_TEST_KEY"
                    environment["EIDOLON_PACKAGE_TEST_KEY"] = synthetic_key
                config_file = root / (provider + ".json")
                config_file.write_text(json.dumps(config))
                config_file.chmod(0o600)
                state = root / (provider + "-state")
                arguments = [cli, "--state", state, "--model-config", config_file]
                initial_requests = len(requests)
                mission = json.loads(command([*arguments, "demo"]))
                assert mission["status"] == "SUCCEEDED" and len(requests) == initial_requests + 1
                assert requests[-1] == (path, "Bearer " + synthetic_key if provider == "llama-server" else None)
                assert json.loads(command([*arguments, "run", mission["id"]])) == mission
                assert len(requests) == initial_requests + 1
                assert synthetic_key not in json.dumps(mission)
                assert all(synthetic_key.encode() not in file.read_bytes() for file in state.rglob("*") if file.is_file())
                model_results.append({"provider": provider, "status": "PASS", "requests": 1,
                                      "resume_without_replay": True, "credential_absent_from_state": True})
        finally:
            server.shutdown()
            thread.join(5)
            server.server_close()
        recipes = []
        for profile, expected_checks in (("missions", 24), ("research-archives", 25)):
            arguments = [python, "-m", "eidolon_core.beta_check", "--web-root", source / "desktop/connected"]
            if profile != "missions":
                arguments.extend(["--profile", profile])
            recipe = json.loads(command(arguments))
            assert recipe["status"] == "PASS" and recipe["checks_passed"] == expected_checks
            recipes.append({"profile": profile, "checks_passed": expected_checks, "status": "PASS"})
        result = {"status": "PASS", "offline_build": True, "isolated_install": True,
                  "installed_modules_match_source": len(modules),
                  "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                  "qualification_cli": qualifications, "synthetic_model_cli": model_results, "recipes": recipes,
                  "real_model_or_hardware_qualified": False}
    result["temporary_files_removed"] = not root.exists()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
