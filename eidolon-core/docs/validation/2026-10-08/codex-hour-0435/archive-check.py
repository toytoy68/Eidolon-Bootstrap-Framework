# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : archive-check.py
# Description : Recette de l'archive comparée aux objets Git du commit annoncé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/, against an archive of an explicitly reviewed commit.

Every packaged source is compared to this checkout's Git objects before code
from the extraction runs. This verifies identity to that commit, not authorship
or general trust in an arbitrary downloaded Git repository.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    source = Path.cwd().resolve()
    spec = importlib.util.spec_from_file_location("beta_bundle_check", source / "tools/build_beta_bundle.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    verified = builder.verify(args.archive)
    assert verified["commit"] == args.commit
    _, tree, expected_files = builder.collect(source.parent, args.commit)
    assert verified["files"] == len(expected_files)
    with tempfile.TemporaryDirectory(prefix="eidolon-published-archive-") as temporary:
        root = Path(temporary)
        with tarfile.open(args.archive, "r:gz") as bundle:
            bundle.extractall(root, filter="data")
        release, = root.iterdir()
        manifest = json.loads((release / "MANIFEST.json").read_text())
        assert manifest["tree"] == tree
        for entry in expected_files:
            assert (release / entry["path"]).read_bytes() == entry["data"]
        project = release / "eidolon-core"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(project / "src")
        environment.pop("PYTHONHOME", None)

        def command(arguments, exit_code=0):
            process = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(root / "no-state"),
                                      *map(str, arguments)], cwd=root, env=environment,
                                     capture_output=True, text=True, timeout=5)
            assert process.returncode == exit_code and not process.stderr
            assert not (root / "no-state").exists()
            return json.loads(process.stdout)

        qualification = []
        for name, status, code in (("passed-scope-synthetic.json", "PASSED_SCOPE", 0),
                                  ("incomplete-missing-measure.json", "INCOMPLETE", 2),
                                  ("rejected-one-violation.json", "REJECTED", 3)):
            result = command(["qualification-check", "--report", project / "examples/qualification" / name], code)
            assert result["status"] == status and result["authorizes_execution"] is False
            qualification.append({"status": status, "exit_code": code})
        inspected = []
        for provider, token_option in (("ollama", "num_predict"), ("llama-server", "max_tokens")):
            path = root / (provider + ".json")
            path.write_text(json.dumps({"version": 1, "provider": provider, "endpoint": "http://127.0.0.1:8080",
                                       "model": "synthetic-config-only", "options": {token_option: 512}}))
            path.chmod(0o600)
            result = command(["model-config-check", "--config", path])
            assert result["status"] == "VALID_CONFIG"
            assert result["server_contacted"] is False and result["secret_value_read"] is False
            assert result["model_available"] is None and result["authorizes_execution"] is False
            inspected.append({"provider": provider, "status": "VALID_CONFIG", "server_contacted": False})
        report = {"status": "PASS", "commit": args.commit, "tree": tree,
                  "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                  "files_identical_to_git_objects": len(expected_files), "configuration_checks": inspected,
                  "qualification_checks": qualification, "state_not_created": True,
                  "real_model_or_hardware_qualified": False}
    report["temporary_extraction_removed"] = not root.exists()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
