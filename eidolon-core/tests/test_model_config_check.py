# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_model_config_check.py
# Description : Diagnostic de configuration sans réseau ni état ni secret
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.openai_chat_model import OpenAIChatModel
from tests.test_llama_model_config import configuration
from tests.test_openai_chat_model import KEY_ENV, SECRET


class ModelConfigCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "private-config.json"
        self.path.write_text(json.dumps(configuration()), encoding="utf-8")
        self.path.chmod(0o600)
        self.state = self.root / "state"

    def invoke(self, *options):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--state", str(self.state), *options, "model-config-check", "--config", str(self.path)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_check_does_not_read_credential_contact_server_or_initialize_runtime(self):
        before = self.path.read_bytes()
        original_getitem = os.environ.__class__.__getitem__

        def guarded_getitem(environment, key):
            if key == KEY_ENV:
                raise AssertionError("credential accessed")
            return original_getitem(environment, key)

        with patch.dict(os.environ, {KEY_ENV: SECRET}), \
             patch.object(os.environ.__class__, "__getitem__", guarded_getitem), \
             patch("socket.socket", side_effect=AssertionError("network opened")), \
             patch("eidolon_core.cli.Store", side_effect=AssertionError("state opened")), \
             patch("eidolon_core.cli.Runtime", side_effect=AssertionError("runtime initialized")), \
             patch.object(OpenAIChatModel, "headers", side_effect=AssertionError("credential resolved")):
            code, stdout, stderr = self.invoke()
        self.assertEqual((code, stderr), (0, ""))
        result = json.loads(stdout)
        self.assertEqual(result["schema"], "eidolon-model-config-check/1")
        self.assertEqual(result["status"], "VALID_CONFIG")
        self.assertIsNone(result["model_available"])
        for field in ("server_contacted", "secret_value_read", "authorizes_execution"):
            self.assertIs(result[field], False)
        self.assertEqual(result["manifest"]["api_key_env"], KEY_ENV)
        self.assertEqual(result["manifest"]["adapter"], "openai-chat-llamacpp/3")
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.state.exists())

    def test_existing_state_and_report_configuration_remain_untouched(self):
        self.state.mkdir()
        database = self.state / "missions.sqlite3"
        database.write_bytes(b"synthetic sentinel, not a database")
        metadata = database.stat()
        first = self.invoke()
        self.path.write_text(json.dumps(configuration(), indent=2, sort_keys=True), encoding="utf-8")
        second = self.invoke()
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0)
        self.assertEqual(database.read_bytes(), b"synthetic sentinel, not a database")
        self.assertEqual(database.stat().st_mtime_ns, metadata.st_mtime_ns)
        self.assertEqual(list(self.state.iterdir()), [database])

    def test_malformed_or_public_config_uses_private_diagnostic_before_state_creation(self):
        self.path.write_text(json.dumps({"private-canary": SECRET}))
        code, stdout, stderr = self.invoke()
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(json.loads(stderr), {"error": "ModelConfigError", "message": "INVALID_MODEL_CONFIG"})
        self.assertNotIn(SECRET, stderr)
        self.assertNotIn(str(self.path), stderr)
        self.path.write_text(json.dumps(configuration()))
        self.path.chmod(0o644)
        code, stdout, stderr = self.invoke("--format", "human")
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("MODEL_CONFIG_NOT_PRIVATE_OR_TOO_LARGE", stderr)
        self.assertNotIn("[OK]", stderr)
        self.assertFalse(self.state.exists())

    def test_mission_options_refused_before_file_load(self):
        for options in (("--model-config", "missing"), ("--memory-root", "missing"),
                        ("--profile", "action-sim"), ("--targets", "missing"),
                        ("--allow-target", "vm100"), ("--research-scenario", "empty")):
            with self.subTest(options=options), \
                 patch("eidolon_core.model_config.load_model", side_effect=AssertionError("loaded configuration")):
                code, stdout, stderr = self.invoke(*options)
                self.assertEqual((code, stdout), (2, ""))
                self.assertTrue(json.loads(stderr)["message"].endswith("NOT_SUPPORTED"))
        self.assertFalse(self.state.exists())

    def test_installed_style_cli_for_each_provider_and_human_scope_label(self):
        for provider in ("ollama", "llama-server"):
            value = configuration()
            if provider == "ollama":
                value.update(provider=provider, options={"num_predict": 512})
                del value["api_key_env"], value["context_tokens"]
            self.path.write_text(json.dumps(value))
            for output_format in ("json", "human"):
                with self.subTest(provider=provider, format=output_format):
                    result = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(self.state),
                                             "--format", output_format, "model-config-check", "--config", str(self.path)],
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    if output_format == "json":
                        self.assertEqual(json.loads(result.stdout)["status"], "VALID_CONFIG")
                    else:
                        self.assertIn("[OK] Configuration conforme au contrat local de la CLI.", result.stdout)
                        self.assertIn("Serveur non contacté, valeur de clé non lue", result.stdout)
                        self.assertIn("Eidolon Core Technologies (ECT)", result.stdout)
            self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
