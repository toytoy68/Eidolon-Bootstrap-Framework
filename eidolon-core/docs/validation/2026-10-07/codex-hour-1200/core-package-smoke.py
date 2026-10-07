# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : core-package-smoke.py
# Description : Construction hors réseau et recette du paquet en venv jetable
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/. Requires installed setuptools/wheel, never downloads."""
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
        report = {"inspection_profile": {"status": "PASS", "original_state_unchanged": True,
                  "runtime_inspection_read_only": True, "recovery_copy_stays_historical": True}, "research_profile": {"status": mission["status"], "readable_pages": 2,
                  "resume_unchanged": True, "history_entries": 1, "cleaned_text_verified": True},
                  "status": "PASS", "offline_build": True, "isolated_install": True,
                  "installed_modules_match_source": len(modules), "version": info["version"],
                  "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "recipe": recipe}
    report["temporary_files_removed"] = not root.exists()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
