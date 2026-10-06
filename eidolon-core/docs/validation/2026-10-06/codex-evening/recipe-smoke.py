# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe-smoke.py
# Description : Recette Linux temporaire avec processus serveur réels
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/. No browser, SSH, installer or external service.

Every child and file belongs to this invocation. Tokens remain in memory and
private temporary files. Prints only named checks and the tested source SHA.
"""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def main():
    source = Path.cwd()
    environment = {**os.environ, "PYTHONPATH": str(source / "src")}
    checks = []

    def cli(module, *args, expected_code=0):
        result = subprocess.run([sys.executable, "-m", module, *map(str, args)],
                                env=environment, capture_output=True, text=True, timeout=30)
        if result.returncode != expected_code:
            raise AssertionError("CLI failed: " + module)
        return json.loads(result.stdout)

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print("PASS", name, flush=True)

    with tempfile.TemporaryDirectory(prefix="eidolon-recipe-smoke-") as directory:
        root = Path(directory)
        fixture = root / "fixture"
        check("fixture_ready", cli("eidolon_core.beta_fixture", "--output", fixture)["status"] == "READY")
        manifest = json.loads((fixture / "manifest.json").read_text())
        state, token_file = fixture / "state", fixture / "read-token"
        old_token = token_file.read_text().strip()
        check("preflight_pass", cli("eidolon_core.http_api", "--state", state, "--token-file", token_file,
                                    "--web-root", source / "desktop/connected", "--port", 0, "--check")["status"] == "PASS")
        child = None
        stream = None

        def stop():
            nonlocal child, stream
            if child is not None:
                child.terminate()  # exact owned PID, no process-name kill
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
                    raise AssertionError("server did not terminate")
                finally:
                    child = None
            if stream is not None:
                stream.close()
                stream = None

        def start(file, log_name):
            nonlocal child, stream
            log = root / log_name
            stream = log.open("w")
            child = subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", str(state),
                                      "--token-file", str(file), "--port", "0", "--web-root", str(source / "desktop/connected")],
                                     env=environment, stdout=stream, stderr=stream)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise AssertionError("server startup failed")
                match = re.search(r"http://127\.0\.0\.1:(\d+)", log.read_text())
                if match:
                    return int(match[1])
                time.sleep(.03)
            raise AssertionError("server startup deadline")

        def request(port, path, token=None, data=None):
            connection = HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                headers = {"Authorization": "Bearer " + token} if token else {}
                body = None
                if data is not None:
                    headers["Content-Type"] = "application/json"
                    body = json.dumps(data)
                connection.request("POST" if data is not None else "GET", path, body=body, headers=headers)
                result = connection.getresponse()
                raw = result.read()
                value = json.loads(raw) if result.getheader("Content-Type", "").startswith("application/json") else raw
                return result.status, value
            finally:
                connection.close()

        try:
            port = start(token_file, "first-server.log")
            before = {p.name: p.read_bytes() for p in state.glob("*.sqlite3")}
            for path in ("/", "/app.js", "/style.css"):
                check("asset_" + path, request(port, path)[0] == 200)
            status, health = request(port, "/v1/health", old_token)
            check("authenticated_health", status == 200 and health["mode"] == "read_only")
            check("anonymous_refused", request(port, "/v1/health")[0] == 401)
            status, listing = request(port, "/v1/missions", old_token, {})
            check("six_missions", status == 200 and len(listing["items"]) == 6)
            for scenario in manifest["scenarios"]:
                status, snapshot = request(port, "/v1/missions/" + scenario["mission_id"], old_token)
                check("snapshot_" + scenario["role"], status == 200 and snapshot["snapshot"]["mission"]["status"] == scenario["expected_status"])
            for query in manifest["receipt_queries"]:
                status, receipt = request(port, "/v1/command-receipt", old_token, query)
                check("receipt_" + query["command_key"], status == 200 and receipt["status"] == "FOUND" and receipt["authorizes_execution"] is False)
            check("read_state_unchanged", before == {p.name: p.read_bytes() for p in state.glob("*.sqlite3")})
            mission = cli("eidolon_core", "--state", state, "create", "mission supplémentaire synthétique")
            status, listing = request(port, "/v1/missions", old_token, {})
            check("live_creation_visible", status == 200 and len(listing["items"]) == 7)
            cli("eidolon_core", "--state", state, "cancel", mission["id"], expected_code=4)
            status, snapshot = request(port, "/v1/missions/" + mission["id"], old_token)
            check("live_cancellation_visible", status == 200 and snapshot["snapshot"]["mission"]["status"] == "CANCELLED")
            rotated_file = fixture / "next-read-token"
            check("second_token_created", cli("eidolon_core.access_token", "--output", rotated_file)["status"] == "CREATED")
            new_token = rotated_file.read_text().strip()
            check("running_server_keeps_original_token", request(port, "/v1/health", old_token)[0] == 200 and request(port, "/v1/health", new_token)[0] == 401)
            stop()
            port = start(rotated_file, "second-server.log")
            check("restart_uses_explicit_new_token", request(port, "/v1/health", new_token)[0] == 200 and request(port, "/v1/health", old_token)[0] == 401)
            status, after = request(port, "/v1/missions/" + mission["id"] + "/poll", new_token, {"cursor": snapshot["cursor"]})
            check("restart_preserves_store_and_cursor", status == 200 and after["store_id"] == manifest["store_id"] and after["status"] == "DELTA" and after["events"] == [])
        finally:
            stop()
    print(json.dumps({"checks_passed": len(checks), "browser_tested": False, "ssh_tested": False,
                      "python": sys.version.split()[0], "source_commit": subprocess.check_output(
                          ["git", "rev-parse", "HEAD"], text=True).strip()}, indent=2))


if __name__ == "__main__":
    main()
