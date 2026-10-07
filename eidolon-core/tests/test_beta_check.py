# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_beta_check.py
# Description : Contrat et nettoyage de la recette locale autonome
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import beta_check

CORE = Path(__file__).resolve().parents[1]
WEB = CORE / "desktop" / "connected"


class BetaCheckTests(unittest.TestCase):
    def test_real_recipe_from_unrelated_directory_has_machine_report(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "eidolon_core.beta_check", "--web-root", str(WEB)],
                cwd=directory, env={**os.environ, "PYTHONPATH": str(CORE / "src")},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["checks_passed"], 24)
            self.assertIn("read_state_unchanged", report["checks"])
            self.assertIn("restart_preserves_store_and_cursor", report["checks"])
            self.assertFalse(report["browser_tested"])
            self.assertFalse(report["ssh_tested"])
            self.assertNotIn(directory, result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_assets_fail_before_preparing_state_without_path_leak(self):
        output = io.StringIO()
        with patch.object(beta_check.tempfile, "TemporaryDirectory", side_effect=AssertionError("must not prepare")), redirect_stdout(output):
            code = beta_check.main(["--web-root", "/nonexistent/private-core-assets"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(report["checks_passed"], 0)
        self.assertEqual(report["error"], "LOCAL_RECIPE_FAILED")
        self.assertNotIn("private-core-assets", output.getvalue())

    def test_server_spawn_failure_cleans_owned_files_and_hides_raw_error(self):
        original = subprocess.Popen

        def fail_server(args, *a, **kw):
            if "eidolon_core.http_api" in args and "--check" not in args:
                raise OSError("private fixture failure")
            return original(args, *a, **kw)

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(tempfile, "tempdir", directory), patch.object(subprocess, "Popen", side_effect=fail_server), redirect_stdout(output):
                code = beta_check.main(["--web-root", str(WEB)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["checks_passed"], 2)
            self.assertNotIn("private fixture failure", output.getvalue())
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
