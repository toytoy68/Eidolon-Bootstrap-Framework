# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_openai_chat_boundaries.py
# Description : Confidentialité et validation stricte des réponses chat
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from dataclasses import dataclass
import json
import os
import tempfile
import threading
from socketserver import BaseRequestHandler, ThreadingTCPServer
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.openai_chat_model import OpenAIChatModel, OpenAIChatError
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from tests.test_openai_chat_model import completion, config, CONTEXT, KEY_ENV, SECRET


@dataclass(frozen=True)
class ReflectingTransport:
    mode: str

    def post(self, url, body, *, headers, timeout, max_bytes):
        key = headers["Authorization"].removeprefix("Bearer ")
        if self.mode == "http":
            status, payload = 500, {"error": {"type": key, "message": key}}
        elif self.mode == "model":
            status, payload = 200, {**completion("{}"), "error": key}
        elif self.mode == "finish":
            status, payload = 200, completion("{}", finish=key)
        elif self.mode == "escaped-content":
            escaped = "".join("\\u%04x" % ord(c) for c in key)
            content = '{"version":1,"steps":[{"id":"x","tool":"text.stats","parameters":{"reference":"' + escaped + '"}}]}'
            status, payload = 200, completion(content)
        else:
            status, payload = 200, completion(key)
        return status, "application/json", json.dumps(payload).encode()


class BrokenStatusHandler(BaseRequestHandler):
    def handle(self):
        self.request.recv(65536)
        self.request.sendall(SECRET.encode() + b"\r\n\r\n")


class ChatBoundaryTests(unittest.TestCase):
    def test_malformed_http_status_cannot_leak_credential_through_exception(self):
        with ThreadingTCPServer(("127.0.0.1", 0), BrokenStatusHandler) as server:
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {KEY_ENV: SECRET}):
                    store = Store(state)
                    model = OpenAIChatModel(config(endpoint=f"http://127.0.0.1:{server.server_address[1]}", api_key_env=KEY_ENV))
                    runtime = Runtime(store, model=model)
                    m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
                    self.assertEqual(m["status"], "BLOCKED")
                    self.assertIn("TRANSPORT", m["error"]["message"])
                    self.assertNotIn(SECRET, json.dumps(m) + json.dumps(store.events(m["id"])))
                    self.assertNotIn(SECRET.encode(), store.path.read_bytes())
            finally:
                server.shutdown()

    def test_reflected_credential_never_reaches_mission_or_events(self):
        for mode in ("http", "model", "finish", "content", "escaped-content"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {KEY_ENV: SECRET}):
                store = Store(state)
                model = OpenAIChatModel(config(api_key_env=KEY_ENV), ReflectingTransport(mode))
                runtime = Runtime(store, model=model)
                m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
                self.assertEqual(m["status"], "BLOCKED")
                self.assertEqual(m["error"]["code"], "MODEL_UNAVAILABLE")
                self.assertIsNone(m["model_output"])
                self.assertFalse(m["calls"])
                self.assertNotIn(SECRET, json.dumps(m) + json.dumps(store.events(m["id"])))
                self.assertNotIn(SECRET.encode(), store.path.read_bytes())

    def test_duplicate_keys_nonfinite_and_surrogates_rejected(self):
        raw = json.dumps(completion("{}"))
        malformed = [raw.replace('"object": "chat.completion"', '"object":"bad","object":"chat.completion"'),
                     json.dumps(completion("\ud800")),
                     raw.replace('"prompt_tokens": 300', '"prompt_tokens": 1e999')]
        model = OpenAIChatModel(config())
        for document in malformed:
            with self.assertRaises(OpenAIChatError) as raised:
                model.read_response(200, "application/json", document.encode())
            self.assertEqual(raised.exception.code, "BAD_RESPONSE")

    def test_missing_usage_and_wrong_control_types_rejected(self):
        model = OpenAIChatModel(config())
        cases = [{k: v for k, v in completion("{}").items() if k != "usage"},
                 completion("{}", tool_calls={}), completion("{}", tool_calls=False),
                 completion("{}", refusal=False)]
        for payload in cases:
            with self.assertRaises(OpenAIChatError) as raised:
                model.read_response(200, "application/json", json.dumps(payload).encode())
            self.assertEqual(raised.exception.code, "BAD_RESPONSE")

    def test_invalid_scalar_options_and_endpoints_rejected_early(self):
        cases = [{"options": {"temperature": 10**400}}, {"options": {"max_tokens": -1}},
                 {"options": {"max_tokens": 1.5}}, {"options": {"seed": 1.5}},
                 {"options": {"top_k": 1.5}}, {"options": {"top_p": 2}},
                 {"options": {"temperature": -0.5}}, {"timeout_seconds": 10**400},
                 {"endpoint": "http://127.0.0.1:99999"}, {"endpoint": "http://127.0.0.1:bad"},
                 {"endpoint": "http://127.0.0.1:\n8080"}, {"model": "bad\ud800"}]
        for values in cases:
            with self.subTest(fields=list(values)), self.assertRaises(ContractError):
                config(**values)

    def test_invalid_secret_never_reaches_transport(self):
        class NeverTransport:
            def post(self, *args, **kwargs):
                raise AssertionError("invalid credential was sent")
        for key in ("bad\r\nheader", "x" * 8193, "é"):
            with patch.dict(os.environ, {KEY_ENV: key}), self.assertRaises(OpenAIChatError) as raised:
                OpenAIChatModel(config(api_key_env=KEY_ENV), NeverTransport()).propose(DEMO_REQUEST, CONTEXT)
            self.assertEqual(raised.exception.code, "INVALID_SECRET")
            self.assertNotIn(key, str(raised.exception))

    def test_returned_schema_cannot_modify_shared_contract(self):
        model = OpenAIChatModel(config())
        identity = model.model_id
        body = model.body(DEMO_REQUEST, CONTEXT)
        body["response_format"]["schema"]["type"] = "array"
        self.assertEqual(model.model_id, identity)
        self.assertEqual(model.body(DEMO_REQUEST, CONTEXT)["response_format"]["schema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
