# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_beta_preflight_g271.py
# Description : Diagnostic sans effets et sans exposition des secrets
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from eidolon_core.beta_preflight import inspect, main


def fixture(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    state = private / "state"
    state.mkdir(mode=0o700)
    profiles = {}
    for i in range(2):
        tokens = {}
        for role in ("read", "write"):
            path = private / f"{role}{i}"
            path.write_text(f"SECRET-{role}-{i}-" + "x" * 32)
            path.chmod(0o600)
            tokens[f"{role}_token_file"] = str(path)
        profiles[f"user{i}"] = dict(tokens, memory_port=18765+i, web_enabled=False,
                                    daily_web_limit=10, file_roots={"nas": str(tmp_path)})
    config = dict(schema="eidolon-beta-runtime/1", state_directory=str(state), activity_source="host.eidolon",
                  clients={"pc0": "user0", "pc1": "user1"}, profiles=profiles, searxng_url=None)
    path = private / "runtime.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return path, config


def test_config_only_does_not_open_configured_paths(tmp_path):
    path, config = fixture(tmp_path)
    config["state_directory"] = "/nonexistent-eidolon/state"
    for p in config["profiles"].values():
        for key in ("read_token_file", "write_token_file"):
            p[key] = "/nonexistent-eidolon/" + Path(p[key]).name
    path.write_text(json.dumps(config))
    report, code = inspect(path)
    assert code == 0 and report["state"] == "CONFIG_VALID"
    assert report["beta_authorized"] is False
    assert next(c for c in report["checks"] if c["check"] == "local_files")["status"] == "NOT_RUN"
    report, code = inspect(path, local_files=True)
    assert code == 2 and report["state"] == "BLOCKED"
    assert str(tmp_path) not in json.dumps(report) and "SECRET" not in json.dumps(report)


@pytest.mark.parametrize("problem", ["same_secret", "token_mode", "state_mode", "missing_root", "root_link", "config_mode"])
def test_local_faults_block_without_changing_files(tmp_path, problem):
    path, config = fixture(tmp_path)
    p = config["profiles"]["user1"]
    if problem == "same_secret":
        Path(p["write_token_file"]).write_bytes(Path(config["profiles"]["user0"]["read_token_file"]).read_bytes())
    elif problem == "token_mode":
        Path(p["read_token_file"]).chmod(0o644)
    elif problem == "state_mode":
        Path(config["state_directory"]).chmod(0o755)
    elif problem == "config_mode":
        path.chmod(0o644)
    else:
        root = tmp_path / "unavailable"
        if problem == "root_link":
            root.symlink_to(tmp_path, target_is_directory=True)
        p["file_roots"]["nas"] = str(root)
        path.write_text(json.dumps(config))
    before = path.read_bytes()
    report, code = inspect(path, local_files=True)
    assert code == 2 and report["state"] == "BLOCKED"
    assert path.read_bytes() == before
    if problem == "same_secret":
        assert any(c["code"] == "CREDENTIAL_REUSED" for c in report["checks"])
    assert list(Path(config["state_directory"]).iterdir()) == []
    assert "SECRET" not in json.dumps(report) and str(tmp_path) not in json.dumps(report)


def test_read_only_profile_and_real_acceptance_remain_explicit(tmp_path):
    path, config = fixture(tmp_path)
    config["profiles"]["user1"]["write_token_file"] = None
    path.write_text(json.dumps(config))
    report, code = inspect(path, local_files=True)
    assert code == 0 and report["state"] == "LOCAL_FILES_VALID"
    rows = {c["check"]: c for c in report["checks"]}
    assert rows["profile_2.write_token"]["status"] == "NOT_APPLICABLE"
    assert rows["existing_state_binding"]["status"] == "NOT_RUN"
    assert rows["memory_identity_and_permissions"]["status"] == "NOT_RUN"
    assert report["beta_authorized"] is False


@pytest.mark.parametrize("content", ['{"schema":1,"schema":2}', '{"value":NaN}', '{', '[]'])
def test_malformed_config_is_bounded_generic_refusal(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    report, code = inspect(path)
    assert code == 2 and report["checks"] == [dict(check="configuration", status="FAIL", code="UNAVAILABLE_OR_INVALID")]


def test_cli_does_not_echo_private_arguments(tmp_path, capsys):
    assert main(["--unknown", "SECRET-PASTED-BY-MISTAKE"]) == 64
    captured = capsys.readouterr()
    assert json.loads(captured.out)["state"] == "USAGE_ERROR"
    assert captured.err == "" and "SECRET" not in captured.out
    path, _ = fixture(tmp_path)
    assert main(["--config", str(path), "--format", "human"]) == 0
    captured = capsys.readouterr()
    assert "Eidolon Core Technologies (ECT)" in captured.out
    assert "NOT_RUN" in captured.out and "SECRET" not in captured.out


def test_audit_forbids_network_writes_listing_processes_and_runtime(tmp_path):
    path, config = fixture(tmp_path)
    database = Path(config["state_directory"]) / "actions.sqlite3"
    database.write_bytes(b"not-a-database-must-not-be-opened")
    script = r'''
import sys, os, json
from eidolon_core.beta_preflight import inspect
from eidolon_core.beta_runtime import BetaRuntime
def no_runtime(*args, **kwargs):
    raise AssertionError("runtime must not start")
BetaRuntime.__init__ = no_runtime
def audit(event, args):
    if event == "open":
        if isinstance(args[0], str) and args[0].endswith("actions.sqlite3"):
            raise AssertionError("existing state opened")
        flags = args[2]
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError("write attempted")
    if event in ("os.listdir", "os.scandir"):
        target = args[0]
        # Importlib may list Python module directories; operator data must not
        # be listed, whether addressed by pathname or directory descriptor.
        if isinstance(target, int) or str(target).startswith(os.path.dirname(sys.argv[1])):
            raise AssertionError("user directory listing")
    if event.startswith(("socket.", "subprocess.", "sqlite3.")) or event in (
        "os.mkdir", "os.remove", "os.rename", "os.chmod", "os.link", "os.symlink"):
        raise AssertionError("side effect: " + event)
sys.addaudithook(audit)
report, code = inspect(sys.argv[1], local_files=True)
assert code == 0, report
print(json.dumps(report))
'''
    run = subprocess.run([sys.executable, "-B", "-c", script, str(path)], capture_output=True,
                         text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=10)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["state"] == "LOCAL_FILES_VALID"
    assert database.read_bytes() == b"not-a-database-must-not-be-opened"
