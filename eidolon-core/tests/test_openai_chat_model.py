# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_openai_chat_model.py
# Description : Tests de l'adaptateur chat llama-server sur transport simulé et loopback
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Simulated protocol only: success here does not qualify llama.cpp, a GPU or a model."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import pickle
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import PLAN_SCHEMA
from eidolon_core.openai_chat_model import (OpenAIChatConfig, OpenAIChatError, OpenAIChatModel,
                                            UrllibChatTransport)
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

MODEL = "synthetic-planner-q4"
KEY_ENV = "EIDOLON_TEST_LLAMA_KEY"
SECRET = "synthetic-key-do-not-log-9f3c"


def completion(content, *, finish="stop", model=MODEL, **message_extra):
    message = {"role": "assistant", "content": content, **message_extra}
    return {"choices": [{"finish_reason": finish, "index": 0, "message": message}],
            "created": 1759670000, "model": model, "system_fingerprint": "b11418-synthetic",
            "object": "chat.completion", "id": "chatcmpl-synthetic",
            "usage": {"completion_tokens": 12, "prompt_tokens": 300, "total_tokens": 312,
                      "prompt_tokens_details": {"cached_tokens": 0}}}


def plan_for(body):
    request = json.loads(body)
    context = json.loads(request["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
    steps = [{"id": f"stats-{i + 1}", "tool": "text.stats",
              "parameters": {"reference": f"{item['information_id']}@{item['revision']}"}}
             for i, item in enumerate(context["items"])]
    return json.dumps({"version": 1, "steps": steps})


# Module-level transports: the Runtime runs the model in a spawn worker, which pickles them.
class PlanningTransport:
    def post(self, url, body, *, headers, timeout, max_bytes):
        return 200, "application/json; charset=utf-8", json.dumps(completion(plan_for(body))).encode()


class CannedTransport:
    def __init__(self, status, content_type, payload):
        self.status, self.content_type, self.payload = status, content_type, payload
        self.calls = []

    def post(self, url, body, *, headers, timeout, max_bytes):
        self.calls.append({"url": url, "body": json.loads(body), "headers": dict(headers),
                           "timeout": timeout, "max_bytes": max_bytes})
        raw = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return self.status, self.content_type, raw


class DownTransport:
    def post(self, url, body, *, headers, timeout, max_bytes):
        raise OpenAIChatError("TRANSPORT", "ConnectionRefusedError")


def config(**kwargs):
    values = {"endpoint": "http://127.0.0.1:8080", "model": MODEL,
              "options": {"temperature": 0, "seed": 7, "max_tokens": 512}, "context_tokens": 8192}
    values.update(kwargs)
    return OpenAIChatConfig(**values)


CONTEXT = {"items": [{"information_id": "synthetic-note", "revision": 1, "content": "texte"}]}


class ConfigurationTests(unittest.TestCase):
    def test_no_default_endpoint_or_model(self):
        with self.assertRaises(TypeError):
            OpenAIChatConfig()  # pylint: disable=no-value-for-parameter

    def test_endpoint_rules(self):
        for endpoint in ("ftp://127.0.0.1:8080", "http://user:pw@127.0.0.1:8080",
                         "http://127.0.0.1:8080/v1", "http://127.0.0.1:8080/?x=1", "127.0.0.1:8080",
                         "http://gpu.example.invalid:8080"):
            with self.assertRaises(ContractError, msg=endpoint):
                config(endpoint=endpoint)
        approved = config(endpoint="https://gpu.example.invalid:8443", allow_non_loopback=True)
        self.assertEqual(approved.url(), "https://gpu.example.invalid:8443/v1/chat/completions")

    def test_api_key_is_a_variable_name_and_needs_https_off_loopback(self):
        for value in ("sk-live-123", "lower_case", "WITH SPACE", "", 3):
            with self.assertRaises(ContractError, msg=value):
                config(api_key_env=value)
        with self.assertRaises(ContractError):
            config(endpoint="http://gpu.example.invalid:8080", allow_non_loopback=True, api_key_env=KEY_ENV)
        config(endpoint="https://gpu.example.invalid:8443", allow_non_loopback=True, api_key_env=KEY_ENV)
        config(api_key_env=KEY_ENV)  # loopback over http stays local

    def test_options_budgets_and_context(self):
        for kwargs in ({"options": {"temperature": float("inf")}}, {"options": {"tools": []}},
                       {"options": {"stream": True}}, {"options": {"temperature": "0"}},
                       {"options": {"seed": True}}, {"context_tokens": 0}, {"context_tokens": 1.5},
                       {"timeout_seconds": 0}, {"max_prompt_bytes": 0}, {"model": "two words"},
                       {"allow_non_loopback": 1}):
            with self.assertRaises(ContractError, msg=kwargs):
                config(**kwargs)

    def test_model_id_and_immutability(self):
        source = {"temperature": 0, "seed": 7, "max_tokens": 512}
        cfg = config(options=source)
        model = OpenAIChatModel(cfg)
        base = model.model_id
        self.assertTrue(base.startswith(f"openai-chat/{MODEL}@"))
        source["temperature"] = 1
        self.assertEqual((cfg.options["temperature"], model.model_id), (0, base))
        with self.assertRaises(TypeError):
            cfg.options["temperature"] = 1  # type: ignore[index]
        for change in ({"model": "other"}, {"endpoint": "http://localhost:8080"},
                       {"options": {"temperature": 0.2}}, {"context_tokens": 4096},
                       {"api_key_env": KEY_ENV}, {"max_output_bytes": 1000}):
            self.assertNotEqual(OpenAIChatModel(config(**change)).model_id, base, change)
        model.config = replace(cfg, options={"temperature": 0.5})
        self.assertNotEqual(model.model_id, base)
        clone = pickle.loads(pickle.dumps(model.propose)).__self__
        self.assertEqual((clone.model_id, dict(clone.config.options)), (model.model_id, {"temperature": 0.5}))

    def test_secret_value_never_enters_manifest_or_model_id(self):
        cfg = config(api_key_env=KEY_ENV)
        with patch.dict(os.environ, {KEY_ENV: SECRET}):
            text = json.dumps(cfg.manifest()) + OpenAIChatModel(cfg).model_id + repr(cfg)
        self.assertNotIn(SECRET, text)
        self.assertIn(KEY_ENV, json.dumps(cfg.manifest()))


class ProtocolTests(unittest.TestCase):
    def propose(self, status=200, content_type="application/json", payload=None, **kwargs):
        transport = CannedTransport(status, content_type,
                                    completion('{"version":1}') if payload is None else payload)
        model = OpenAIChatModel(config(**kwargs), transport)
        return model.propose(DEMO_REQUEST, CONTEXT), transport

    def test_request_matches_the_server_contract(self):
        text, transport = self.propose()
        self.assertEqual(text, '{"version":1}')
        call = transport.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:8080/v1/chat/completions")
        body = call["body"]
        self.assertEqual(set(body), {"model", "messages", "stream", "response_format",
                                     "temperature", "seed", "max_tokens"})
        self.assertIs(body["stream"], False)
        self.assertNotIn("tools", body)
        self.assertEqual(body["response_format"], {"type": "json_object", "schema": PLAN_SCHEMA})
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        self.assertIn("untrusted", body["messages"][1]["content"])
        self.assertNotIn("Authorization", call["headers"])

    def test_bearer_key_comes_from_the_environment_at_call_time(self):
        with patch.dict(os.environ, {KEY_ENV: SECRET}):
            _, transport = self.propose(api_key_env=KEY_ENV)
        self.assertEqual(transport.calls[0]["headers"]["Authorization"], "Bearer " + SECRET)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(KEY_ENV, None)
            with self.assertRaises(OpenAIChatError) as raised:
                self.propose(api_key_env=KEY_ENV)
        self.assertEqual(raised.exception.code, "MISSING_SECRET")
        self.assertNotIn(SECRET, str(raised.exception))

    def test_failures_are_errors_never_a_plan(self):
        ok = completion("{}")
        cases = {
            "HTTP_STATUS": dict(status=500, payload={"error": {"code": 500, "message": "boom", "type": "server_error"}}),
            "HTTP_STATUS ": dict(status=503, payload=b"<html>loading model</html>"),
            "AUTHENTICATION": dict(status=401, payload={"error": {"message": "Invalid API Key",
                                                                  "type": "authentication_error"}}),
            "CONTEXT_EXCEEDED": dict(status=400, payload={"error": {"code": 400, "message": "too long",
                                                                    "type": "exceed_context_size_error"}}),
            "BAD_RESPONSE": dict(payload=b"not json"),
            "BAD_RESPONSE ": dict(content_type="text/event-stream"),
            "BAD_RESPONSE  ": dict(payload={**ok, "object": "chat.completion.chunk"}),
            "BAD_RESPONSE   ": dict(payload={**ok, "choices": [ok["choices"][0], ok["choices"][0]]}),
            "BAD_RESPONSE    ": dict(payload={**ok, "choices": []}),
            "BAD_RESPONSE     ": dict(payload=completion("{}", finish=None)),
            "BAD_RESPONSE      ": dict(payload={**ok, "usage": {"prompt_tokens": 1, "completion_tokens": 2,
                                                                 "total_tokens": 9}}),
            "BAD_RESPONSE       ": dict(payload={**ok, "usage": {"prompt_tokens": 9000, "completion_tokens": 2,
                                                                  "total_tokens": 9002}}),
            "BAD_RESPONSE        ": dict(payload=b'{"object":"chat.completion","usage":{"total_tokens":NaN}}'),
            "INCOMPLETE": dict(payload=completion('{"version":1,"st', finish="length")),
            "MODEL_MISMATCH": dict(payload=completion("{}", model="other-model")),
            "TOOL_CALL_REFUSED": dict(payload=completion(None, finish="tool_calls", tool_calls=[
                {"type": "function", "function": {"name": "service.restart", "arguments": "{}"}}])),
            "TOOL_CALL_REFUSED ": dict(payload=completion("{}", tool_calls=[{"type": "function"}])),
            "REFUSED": dict(payload=completion("{}", refusal="I cannot help with that")),
            "EMPTY_OUTPUT": dict(payload=completion("  ")),
            "EMPTY_OUTPUT ": dict(payload=completion(None, reasoning_content='{"version":1,"steps":[]}')),
            "OUTPUT_TOO_LARGE": dict(payload=completion("x" * 70_000)),
            "MODEL_ERROR": dict(payload={**ok, "error": "late failure"}),
        }
        for code, kwargs in cases.items():
            with self.assertRaises(OpenAIChatError, msg=code) as raised:
                self.propose(**kwargs)
            self.assertEqual(raised.exception.code, code.strip(), code)

    def test_completion_beyond_max_tokens_is_inconsistent(self):
        payload = completion("{}")
        payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 600, "total_tokens": 610}
        with self.assertRaises(OpenAIChatError):
            self.propose(payload=payload)

    def test_prompt_budget_checked_before_any_transport_call(self):
        transport = CannedTransport(200, "application/json", completion("{}"))
        model = OpenAIChatModel(config(max_prompt_bytes=2_000), transport)
        big = {"items": [{"information_id": "n", "revision": 1, "content": "y" * 3_000}]}
        with self.assertRaises(OpenAIChatError) as raised:
            model.propose(DEMO_REQUEST, big)
        self.assertEqual((raised.exception.code, transport.calls), ("PROMPT_TOO_LARGE", []))

    def test_oversized_injected_response_is_refused(self):
        model = OpenAIChatModel(config(max_response_bytes=1_000))
        with self.assertRaises(OpenAIChatError) as raised:
            model.read_response(200, "application/json", b" " * 1_001)
        self.assertEqual(raised.exception.code, "RESPONSE_TOO_LARGE")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        route = self.server.route
        self.server.seen.append({"path": self.path, "authorization": self.headers.get("Authorization")})
        if route == "redirect":
            self.send_response(307)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
            return
        if route == "slow":
            time.sleep(2)
        status = 200
        if self.server.key and self.headers.get("Authorization") != "Bearer " + self.server.key:
            status, payload = 401, {"error": {"message": "Invalid API Key", "type": "authentication_error"}}
        elif route == "huge":
            payload = completion("x" * 300_000)
        else:
            payload = completion(plan_for(body))
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The client gave up first (timeout or size limit), as the test intends.


class LoopbackServerTests(unittest.TestCase):
    """Real HTTP over 127.0.0.1 against a synthetic server; no external network."""

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.route, self.server.key, self.server.seen = "ok", None, []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}"

    def model(self, **kwargs):
        return OpenAIChatModel(config(endpoint=self.endpoint, timeout_seconds=0.5, **kwargs), UrllibChatTransport())

    def code(self, model):
        with self.assertRaises(OpenAIChatError) as raised:
            model.propose(DEMO_REQUEST, CONTEXT)
        return raised.exception.code

    def test_plan_text_over_http(self):
        text = self.model().propose(DEMO_REQUEST, CONTEXT)
        self.assertEqual(json.loads(text)["steps"][0]["tool"], "text.stats")
        self.assertEqual(self.server.seen[0]["path"], "/v1/chat/completions")

    def test_errors_redirects_size_timeout(self):
        for route, code in {"redirect": "HTTP_STATUS", "huge": "RESPONSE_TOO_LARGE", "slow": "TRANSPORT"}.items():
            self.server.route = route
            self.assertEqual(self.code(self.model()), code, route)

    def test_authentication_with_and_without_key(self):
        self.server.key = SECRET
        self.assertEqual(self.code(self.model()), "AUTHENTICATION")
        with patch.dict(os.environ, {KEY_ENV: SECRET}):
            self.model(api_key_env=KEY_ENV).propose(DEMO_REQUEST, CONTEXT)
        self.assertEqual(self.server.seen[-1]["authorization"], "Bearer " + SECRET)

    def test_connection_refused(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        model = OpenAIChatModel(config(endpoint=f"http://127.0.0.1:{port}", timeout_seconds=0.5))
        self.assertEqual(self.code(model), "TRANSPORT")


class RuntimeIntegrationTests(unittest.TestCase):
    """The adapter plugs into Runtime unchanged; Core keeps every check."""

    def run_with(self, transport, **kwargs):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = Store(temp.name)
        runtime = Runtime(store, model=OpenAIChatModel(config(**kwargs), transport))
        m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        return m, store

    def test_valid_plan_still_goes_through_core_checks(self):
        m, _ = self.run_with(PlanningTransport())
        self.assertEqual((m["status"], m["outcome"]["status"]), ("SUCCEEDED", "ACHIEVED"))
        self.assertTrue(m["configuration"]["model"].startswith("openai-chat/"))

    def test_transport_failure_blocks_instead_of_planning(self):
        m, _ = self.run_with(DownTransport())
        self.assertEqual((m["status"], m["error"]["code"], m["plan"]), ("BLOCKED", "MODEL_UNAVAILABLE", None))

    def test_invalid_or_unauthorized_plans_are_refused_by_core(self):
        bad, _ = self.run_with(CannedTransport(200, "application/json", completion('{"version":1,"steps":[]}')))
        self.assertEqual((bad["status"], bad["error"]["code"]), ("FAILED", "MODEL_INVALID"))
        restart = json.dumps({"version": 1, "steps": [
            {"id": "r", "tool": "service.restart", "parameters": {"target": "memory-engine"}}]})
        denied, _ = self.run_with(CannedTransport(200, "application/json", completion(restart)))
        self.assertEqual(denied["status"], "BLOCKED")
        self.assertEqual(denied["calls"], [])

    def test_secret_never_reaches_the_mission_record(self):
        with patch.dict(os.environ, {KEY_ENV: SECRET}):
            m, store = self.run_with(PlanningTransport(), api_key_env=KEY_ENV)
        self.assertEqual(m["status"], "SUCCEEDED")
        record = json.dumps(m) + json.dumps(store.events(m["id"]))
        self.assertNotIn(SECRET, record)


if __name__ == "__main__":
    unittest.main()
