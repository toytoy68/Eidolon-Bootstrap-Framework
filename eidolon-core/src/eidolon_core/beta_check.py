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
from contextlib import contextmanager
import hashlib
from importlib.metadata import version, PackageNotFoundError
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


class _Interrupted(BaseException):
    def __init__(self, signum):
        self.signum = signum


@contextmanager
def _termination_signals():
    previous, stopping = {}, False
    def interrupt(signum, frame):
        nonlocal stopping
        if not stopping:
            stopping = True
            raise _Interrupted(signum)
        # A second signal must not cut short cleanup of owned children.
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _stop_owned(child):
    """Stop only a process group created with start_new_session by this recipe."""
    if child.returncode is not None:
        return
    try:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # Also stop descendants that survived their group leader or ignored TERM.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=3)


def run(web_root, checks, *, profile="missions"):
    if profile not in {"missions", "research-archives"}:
        raise ValueError("invalid recipe profile")
    web_root = Path(web_root).resolve(strict=True)
    from .http_api import read_assets
    assets = read_assets(web_root)
    asset_hashes = {name: hashlib.sha256(body).hexdigest() for name, body in assets.items()}
    environment = dict(os.environ)

    def cli(module, *args, expected_code=0):
        child = subprocess.Popen([sys.executable, "-m", module, *map(str, args)],
                                 env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, start_new_session=True)
        try:
            stdout, _ = child.communicate(timeout=30)
        finally:
            try:
                _stop_owned(child)
            finally:
                child.stdout.close(); child.stderr.close()
        if child.returncode != expected_code:
            raise AssertionError("CLI failed: " + module)
        return json.loads(stdout)

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)


    with tempfile.TemporaryDirectory(prefix="eidolon-recipe-smoke-") as directory:
        root = Path(directory)
        fixture = root / "fixture"
        check("fixture_ready", cli("eidolon_core.beta_fixture", "--output", fixture,
                                   "--profile", profile)["status"] == "READY")
        manifest = json.loads((fixture / "manifest.json").read_text())
        state, token_file = fixture / "state", fixture / "read-token"
        old_token = token_file.read_text().strip()
        archive_args = ["--research-archives", str(fixture / "archives")] if profile == "research-archives" else []
        check("preflight_pass", cli("eidolon_core.http_api", "--state", state, "--token-file", token_file,
                                    "--web-root", web_root, "--port", 0, *archive_args, "--check")["status"] == "PASS")
        child = None
        stream = None

        def stop():
            nonlocal child, stream
            try:
                if child is not None:
                    _stop_owned(child)
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
                                      "--token-file", str(file), "--port", "0", "--web-root", str(web_root), *archive_args],
                                     env=environment, stdout=stream, stderr=stream, start_new_session=True)
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
            before = {str(p.relative_to(state)): p.read_bytes() for p in state.rglob("*.sqlite3")}
            for path in ("/", "/app.js", "/style.css"):
                check("asset_" + path, request(port, path)[0] == 200)
            status, health = request(port, "/v1/health", old_token)
            check("authenticated_health", status == 200 and health["mode"] == "read_only")
            check("anonymous_refused", request(port, "/v1/health")[0] == 401)
            status, listing = request(port, "/v1/missions", old_token, {})
            expected_count = len(manifest["scenarios"])
            check("six_missions" if profile == "missions" else "three_research_missions",
                  status == 200 and len(listing["items"]) == expected_count)
            for scenario in manifest["scenarios"]:
                status, snapshot = request(port, "/v1/missions/" + scenario["mission_id"], old_token)
                check("snapshot_" + scenario["role"], status == 200 and snapshot["snapshot"]["mission"]["status"] == scenario["expected_status"])
            for query in manifest["receipt_queries"]:
                status, receipt = request(port, "/v1/command-receipt", old_token, query)
                check("receipt_" + query["command_key"], status == 200 and receipt["status"] == "FOUND" and receipt["authorizes_execution"] is False)
            if profile == "research-archives":
                route = "/v1/research-archives"
                check("anonymous_archives_refused", request(port, route, data={})[0] == 401)
                cursor, first_cursor, items = None, None, []
                forbidden = [str(root), "notice pont", *[r["mission_id"] for r in manifest["scenarios"]]]
                for index in range(3):
                    status, page = request(port, route, old_token, {"limit": 1, "cursor": cursor})
                    check("archive_page_" + str(index + 1), status == 200 and page["status"] == "PAGE"
                          and len(page["items"]) == 1 and page["items"][0]["index"] == index + 1
                          and page["has_more"] is (index < 2))
                    if any(value in json.dumps(page) for value in forbidden):
                        raise AssertionError("archive privacy")
                    if not all(page[name] is False for name in ("authorizes_execution", "authenticity_verified",
                               "live_journal_checked", "committed_status_known", "request_sent")):
                        raise AssertionError("archive authority")
                    cursor = page["next_cursor"]
                    if index == 0:
                        first_cursor = cursor
                    items.extend(page["items"])
                check("archive_catalog_complete_private_no_authority", len(items) == 3 and cursor is None
                      and page["archive_count"] == 3 and page["run_count"] == 3)
                check("raw_archive_route_absent", request(port, "/research-archive-000001.json", old_token)[0] == 404)
                # Only this recipe's disposable copies, never active research evidence.
                (fixture / "archives/research-archive-000003.json").unlink()
                status, reset = request(port, route, old_token, {"cursor": first_cursor})
                check("archive_change_requires_reset", status == 200 and reset["status"] == "RESET_REQUIRED"
                      and reset["reason"] == "CATALOG_CHANGED" and reset["items"] == [])
            check("read_state_unchanged", before == {str(p.relative_to(state)): p.read_bytes() for p in state.rglob("*.sqlite3")})
            mission = cli("eidolon_core", "--state", state, "create", "mission supplémentaire synthétique")
            status, listing = request(port, "/v1/missions", old_token, {})
            check("live_creation_visible", status == 200 and len(listing["items"]) == expected_count + 1)
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
    parser.add_argument("--profile", choices=("missions", "research-archives"), default="missions")
    args = parser.parse_args(argv)
    checks = []
    report = {"protocol": "eidolon-beta-check/1", "status": "FAIL", "checks": checks,
              "profile": args.profile,
              "browser_tested": False, "ssh_tested": False, "windows_tested": False,
              "user_server_tested": False, "model_tested": False,
              "python": sys.version.split()[0]}
    try:
        report["package_version"] = version("eidolon-core")
    except PackageNotFoundError:
        report["package_version"] = "source-checkout"
    try:
        with _termination_signals():
            report["asset_sha256"] = run(args.web_root, checks, profile=args.profile)
        report["status"] = "PASS"
    except _Interrupted as exc:
        report["error"] = "INTERRUPTED"
        report["signal"] = exc.signum
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
