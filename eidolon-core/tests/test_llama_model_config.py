# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_llama_model_config.py
# Description : Configuration et parcours CLI du candidat llama-server
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run the actual CLI against a synthetic local HTTP protocol, not llama.cpp."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.model_config import ModelConfigError, load_model
from eidolon_core.openai_chat_model import OpenAIChatModel
from tests.test_openai_chat_model import MODEL, KEY_ENV, SECRET, completion, plan_for


def configuration(endpoint="http://127.0.0.1:8080"):
    return {"version": 1, "provider": "llama-server", "endpoint": endpoint, "model": MODEL,
            "options": {"temperature": 0, "seed": 7, "max_tokens": 512},
            "context_tokens": 8192, "api_key_env": KEY_ENV, "timeout_seconds": 2}


class LlamaConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "model.json"

    def load(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")
        self.path.chmod(0o600)
        return load_model(self.path)

    def test_loading_is_canonical_without_network_or_secret_lookup(self):
        with patch("socket.socket", side_effect=AssertionError("network started")), \
             patch.object(OpenAIChatModel, "headers", side_effect=AssertionError("secret read")):
            first = self.load(configuration())
            self.assertIsInstance(first, OpenAIChatModel)
            self.path.write_text(json.dumps(configuration(), indent=2, sort_keys=True), encoding="utf-8")
            second = load_model(self.path)
        self.assertEqual(first.model_id, second.model_id)
        manifest = first.config.manifest()
        self.assertEqual(manifest["api_key_env"], KEY_ENV)
        self.assertEqual(manifest["budgets"]["output_tokens"], 512)
        self.assertFalse(manifest["allow_non_loopback"])

    def test_provider_specific_keys_do_not_cross_adapter_boundary(self):
        for change in ({"provider": "openai"}, {"provider": {}}, {"provider": ["llama-server"]},
                       {"api_key": SECRET}, {"headers": {"Authorization": SECRET}},
                       {"allow_non_loopback": True}, {"options": {"num_predict": 512}},
                       {"options": {"max_tokens": 512, "num_ctx": 8192}},
                       {"context_tokens": -1}, {"api_key_env": "literal-key-value"}):
            with self.subTest(fields=list(change)), self.assertRaisesRegex(ModelConfigError, "^INVALID_MODEL_CONFIG$"):
                self.load({**configuration(), **change})
        for field in ("api_key_env", "context_tokens"):
            value = {"version": 1, "provider": "ollama", "endpoint": "http://127.0.0.1:11434",
                     "model": "synthetic", "options": {"num_predict": 512}, field: configuration()[field]}
            with self.subTest(field=field), self.assertRaises(ModelConfigError):
                self.load(value)

    def test_cli_requires_bounded_explicit_output_tokens(self):
        for options in ({}, {"max_tokens": True}, {"max_tokens": 0}, {"max_tokens": -1},
                        {"max_tokens": 1.5}, {"max_tokens": 8193}, {"max_tokens": 10**400}):
            with self.subTest(options=options), self.assertRaises(ModelConfigError):
                self.load({**configuration(), "options": options})
        for value in (1, 8192):
            model = self.load({**configuration(), "options": {"max_tokens": value}})
            self.assertEqual(model.config.options["max_tokens"], value)

    def test_literal_loopback_and_no_url_secrets(self):
        for endpoint in ("http://localhost:8080", "https://api.example.invalid", "http://192.0.2.1:8080",
                         "http://127.0.0.1:8080/v1", "http://@127.0.0.1:8080", "http://:x@127.0.0.1:8080",
                         "http://127.0.0.1:8080?", "http://127.0.0.1:8080#", "http://127.0.0.1:8080/?token=x",
                         "http://127.0.0.1:0", "http://127.0.0.1:\n8080", "http://127.0.0.1:8080\x7f"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ModelConfigError):
                self.load(configuration(endpoint))
        model = self.load(configuration("http://[::1]:8080"))
        self.assertEqual(model.config.url(), "http://[::1]:8080/v1/chat/completions")

    def test_optional_secret_and_context_can_be_omitted(self):
        value = configuration()
        del value["api_key_env"], value["context_tokens"]
        model = self.load(value)
        self.assertIsNone(model.config.api_key_env)
        self.assertIsNone(model.config.context_tokens)


class LlamaCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.requests = []
        self.response_kind = "valid"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append((self.path, raw, self.headers.get("Authorization")))
                content, status = plan_for(raw), 200
                if owner.response_kind == "unauthorized":
                    content = json.dumps({"version": 1, "steps": [{"id": "danger", "tool": "service.restart", "parameters": {}}]})
                elif owner.response_kind == "invalid":
                    content = "not a plan"
                elif owner.response_kind == "reflected-content":
                    content = SECRET
                payload = completion(content)
                if owner.response_kind == "auth-error":
                    status, payload = 401, {"error": {"type": SECRET, "message": SECRET}}
                elif owner.response_kind == "context-error":
                    status, payload = 400, {"error": {"type": "exceed_context_size_error", "message": SECRET}}
                elif owner.response_kind == "truncated":
                    payload = completion(content, finish="length")
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.stop)
        self.path = self.root / "model.json"
        self.config = configuration(f"http://127.0.0.1:{self.server.server_port}")
        self.write()
        self.state = self.root / "state"

    def stop(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def write(self):
        self.path.write_text(json.dumps(self.config), encoding="utf-8")
        self.path.chmod(0o600)

    def cli(self, *args, key=SECRET, configured=True):
        environment = dict(os.environ)
        environment.pop(KEY_ENV, None)
        if key is not None:
            environment[KEY_ENV] = key
        command = [sys.executable, "-m", "eidolon_core", "--state", str(self.state), "--timeout", "5"]
        if configured:
            command += ["--model-config", str(self.path)]
        return subprocess.run([*command, *args], capture_output=True, text=True, timeout=15, env=environment)

    def assert_secret_absent(self, process):
        self.assertNotIn(SECRET, process.stdout + process.stderr)
        for path in self.state.rglob("*"):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes(), path.name)

    def test_real_cli_worker_and_resume_preserve_tool_contract(self):
        run = self.cli("demo")
        self.assertEqual(run.returncode, 0, run.stderr)
        mission = json.loads(run.stdout)
        self.assertEqual(mission["status"], "SUCCEEDED")
        self.assertTrue(mission["configuration"]["model"].startswith("openai-chat/"))
        self.assertEqual(len(self.requests), 1)
        path, raw, auth = self.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(auth, "Bearer " + SECRET)
        body = json.loads(raw)
        self.assertIs(body["stream"], False)
        self.assertEqual(body["response_format"]["type"], "json_object")
        self.assertEqual(body["max_tokens"], 512)
        self.assertNotIn("tools", body)
        self.assert_secret_absent(run)
        resumed = self.cli("run", mission["id"])
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(len(self.requests), 1)

    def test_create_requires_no_secret_and_config_changes_block_before_network(self):
        created = self.cli("create", DEMO_REQUEST, key=None)
        self.assertEqual(created.returncode, 0, created.stderr)
        mission_id = json.loads(created.stdout)["id"]
        original = dict(self.config)
        for change in ({"context_tokens": 4096}, {"api_key_env": "EIDOLON_OTHER_KEY"},
                       {"model": "other-model"}, {"options": {"max_tokens": 256}}):
            self.config = {**original, **change}
            self.write()
            refused = self.cli("run", mission_id)
            self.assertEqual(refused.returncode, 2)
            self.assertIn("CONFIGURATION_CHANGED", refused.stdout + refused.stderr)
            self.assertEqual(self.requests, [])
        self.config = original
        self.write()
        self.assertEqual(self.cli("run", mission_id).returncode, 0)
        self.assertEqual(len(self.requests), 1)

    def test_missing_or_invalid_secret_sends_nothing(self):
        for key, reason in ((None, "MISSING_SECRET"), ("bad\r\nheader", "INVALID_SECRET")):
            with self.subTest(reason=reason):
                run = self.cli("demo", key=key)
                self.assertEqual(run.returncode, 2, run.stderr)
                mission = json.loads(run.stdout)
                self.assertEqual(mission["error"]["code"], "MODEL_UNAVAILABLE")
                self.assertIn(reason, mission["error"]["message"])
                self.assertEqual(mission["calls"], [])
                self.assertEqual(self.requests, [])
                if key:
                    self.assertNotIn(key, run.stdout + run.stderr)

    def test_server_errors_and_reflection_are_not_silently_replaced_by_fake_model(self):
        for kind, code in (("auth-error", "AUTHENTICATION"), ("context-error", "CONTEXT_EXCEEDED"),
                           ("truncated", "INCOMPLETE"), ("reflected-content", "SECRET_IN_RESPONSE")):
            with self.subTest(kind=kind):
                self.response_kind = kind
                run = self.cli("demo")
                self.assertEqual(run.returncode, 2, run.stderr)
                mission = json.loads(run.stdout)
                self.assertEqual(mission["status"], "BLOCKED")
                self.assertIn(code, mission["error"]["message"])
                self.assertIsNone(mission["model_output"])
                self.assertEqual(mission["calls"], [])
                self.assert_secret_absent(run)

    def test_invalid_and_unauthorized_plans_have_no_tool_effect(self):
        for kind, exit_code, error in (("invalid", 3, "MODEL_INVALID"), ("unauthorized", 2, "PREFLIGHT_REFUSED")):
            self.response_kind = kind
            run = self.cli("demo")
            self.assertEqual(run.returncode, exit_code, run.stderr)
            mission = json.loads(run.stdout)
            self.assertEqual(mission["error"]["code"], error)
            self.assertEqual(mission["calls"], [])

    def test_no_config_means_no_model_and_incompatible_command_does_not_initialize_state(self):
        refused = self.cli("--profile", "research-sim", "research", "synthetic request")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("MODEL_CONFIG_COMMAND_NOT_SUPPORTED", refused.stderr)
        self.assertFalse(self.state.exists())
        run = self.cli("demo", configured=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.requests, [])
        self.assertNotIn("openai-chat/", run.stdout)


if __name__ == "__main__":
    unittest.main()
