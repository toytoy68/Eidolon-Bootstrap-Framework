# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_hf_cache_audit_g266.py
# Description : Audit HF : variables imposées, réseau bloqué, écritures observées, arguments, exceptions (G266-10)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""FAKE transformers/torch modules only: nothing is downloaded and no real model exists here. The fake
AutoConfig behaves as instructed by the FAKE_MODE variable, to exercise each branch of the tool."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "claude_hf_cache_audit.py"

FAKE = textwrap.dedent("""
    import os, socket
    class AutoConfig:
        @staticmethod
        def from_pretrained(repo, cache_dir, local_files_only):
            assert local_files_only is True
            seen = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HOME")}
            open(os.path.join(cache_dir, "seen-env.json"), "r").close() if False else None
            mode = os.environ.get("FAKE_MODE", "ok")
            if mode == "env":
                if seen["HF_HUB_OFFLINE"] != "1" or seen["TRANSFORMERS_OFFLINE"] != "1" or seen["HF_HOME"] != cache_dir:
                    raise RuntimeError("offline variables not imposed")
            elif mode == "network":
                socket.create_connection(("127.0.0.1", 9), timeout=1)
            elif mode == "write":
                with open(os.path.join(cache_dir, "version.txt"), "w") as handle:
                    handle.write("1")
            elif mode == "error":
                raise OSError("couldn't find SECRET-DETAIL in " + cache_dir + "/models--x " + "y" * 500)
            return {"model_type": "bert"}
""")


@pytest.fixture
def fake(tmp_path):
    pkg = tmp_path / "fake" / "transformers"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(FAKE)
    cache = tmp_path / "cache"
    cache.mkdir()
    return tmp_path / "fake", cache


def audit(fake, cache, *args, mode="ok", env=None):
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("HF_", "TRANSFORMERS"))}
    environment.update(PYTHONPATH=str(fake), FAKE_MODE=mode, **(env or {}))
    r = subprocess.run([sys.executable, str(TOOL), *(["--cache", str(cache)] if cache else []), *args],
                       capture_output=True, text=True, env=environment, timeout=60)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr


def test_clean_load_imposes_the_offline_environment(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, mode="env")
    assert code == 0 and report["result"] == "ok" and report["loaded"] == "configuration"
    assert report["imposed"]["HF_HUB_OFFLINE"] == "1" and report["imposed"]["HF_HOME"] == "<cache>"


def test_a_caller_environment_that_is_online_is_overridden_and_reported(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, mode="env", env={"HF_HUB_OFFLINE": "0", "HF_HOME": "/elsewhere"})
    assert code == 0 and report["overridden"] == ["HF_HOME", "HF_HUB_OFFLINE"]


def test_network_is_blocked_not_only_observed(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, mode="network")
    assert code == 1 and report["network_blocked"] in (["socket.connect"], ["socket.getaddrinfo"])
    assert report["result"].startswith("NetworkBlocked") and report["loaded"] is None


def test_writes_are_observed_and_fail_the_audit(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, mode="write")
    assert code == 1 and report["writes"] == [["open", "<cache>/version.txt"]]


def test_exception_messages_are_bounded_and_redacted(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, mode="error")
    assert code == 1 and str(cache) not in json.dumps(report) and len(report["result"]) <= 200
    assert report["result"].startswith("OSError: ") and "<cache>" in report["result"]


def test_full_mode_never_claims_a_torch_load_when_torch_is_absent(fake):
    path, cache = fake
    code, report, _ = audit(path, cache, "--full")
    assert code == 1 and report["loaded"] is None and report["result"].startswith("UNAVAILABLE")


@pytest.mark.parametrize("args, cache_kind", [([], None), (["--unknown"], "dir"), ([], "relative"),
                                               ([], "missing"), ([], "link")])
def test_missing_unknown_or_unsafe_arguments_are_usage_errors(fake, tmp_path, args, cache_kind):
    path, cache = fake
    target = {None: None, "dir": cache, "relative": Path("relative"), "missing": tmp_path / "absent",
              "link": tmp_path / "alias"}[cache_kind]
    if cache_kind == "link":
        target.symlink_to(cache)
    code, report, err = audit(path, target, *args)
    assert code == 2 and report is None and "usage" in err


def test_without_transformers_nothing_is_claimed(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    code, report, _ = audit(tmp_path / "nothing-here", cache)
    if report and report["result"] == "ok":
        pytest.skip("a real transformers is installed in this interpreter")
    assert code == 1 and report["loaded"] is None and report["result"].startswith("UNAVAILABLE")
