# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_check.py
# Description : Recette locale reproductible avec processus et données isolés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Exercise only owned synthetic state and loopback processes, never a user Store.

Explicit web assets work both from a checkout and from an installed wheel.
No browser, SSH, GPU, network service or installer is exercised.
"""
import argparse
import hashlib
from importlib.metadata import version, PackageNotFoundError
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def run(web_root, checks):
    web_root = Path(web_root).resolve(strict=True)
    from .http_api import read_assets
    assets = read_assets(web_root)
    asset_hashes = {name: hashlib.sha256(body).hexdigest() for name, body in assets.items()}
    environment = dict(os.environ)

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


    with tempfile.TemporaryDirectory(prefix="eidolon-recipe-smoke-") as directory:
        root = Path(directory)
        fixture = root / "fixture"
        check("fixture_ready", cli("eidolon_core.beta_fixture", "--output", fixture)["status"] == "READY")
        manifest = json.loads((fixture / "manifest.json").read_text())
        state, token_file = fixture / "state", fixture / "read-token"
        old_token = token_file.read_text().strip()
        check("preflight_pass", cli("eidolon_core.http_api", "--state", state, "--token-file", token_file,
                                    "--web-root", web_root, "--port", 0, "--check")["status"] == "PASS")
        child = None
        stream = None

        def stop():
            nonlocal child, stream
            try:
                if child is not None and child.poll() is None:
                    child.terminate()  # exact owned PID, never a process-name kill
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=3)
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
                                      "--token-file", str(file), "--port", "0", "--web-root", str(web_root)],
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
    return asset_hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — recette locale isolée")
    parser.add_argument("--web-root", required=True, help="Dossier desktop/connected de la version testée")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    checks = []
    report = {"protocol": "eidolon-beta-check/1", "status": "FAIL", "checks": checks,
              "browser_tested": False, "ssh_tested": False, "windows_tested": False,
              "user_server_tested": False, "model_tested": False,
              "python": sys.version.split()[0]}
    try:
        report["package_version"] = version("eidolon-core")
    except PackageNotFoundError:
        report["package_version"] = "source-checkout"
    try:
        report["asset_sha256"] = run(args.web_root, checks)
        report["status"] = "PASS"
    except KeyboardInterrupt:
        report["error"] = "INTERRUPTED"
    except Exception:
        report["error"] = "LOCAL_RECIPE_FAILED"
    report["checks_passed"] = len(checks)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        from .presentation import header, message
        print(header(title="Recette locale isolée"))
        for name in checks:
            print(message("OK", name))
        print(message("INFO" if report["status"] == "PASS" else "ERREUR",
                      "Recette locale : " + report["status"]))
        print(message("ATTENTION", "Navigateur, Windows, SSH, modèle et serveur utilisateur non testés."))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
