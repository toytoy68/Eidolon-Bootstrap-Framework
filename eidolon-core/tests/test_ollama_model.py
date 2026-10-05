# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_ollama_model.py
# Description : Tests de l'adaptateur Ollama sur transport simulé et serveur loopback
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Simulated protocol only: success here does not qualify Ollama, a GPU or a model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import tempfile
import threading
import time
import unittest

from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import OllamaConfig, OllamaError, OllamaModel, UrllibTransport
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

MODEL = "synthetic-planner:1b"


def answer(content, **extra):
    payload = {"model": MODEL, "created_at": "2026-10-05T12:00:00Z",
               "message": {"role": "assistant", "content": content},
               "done": True, "done_reason": "stop", "eval_count": 12}
    payload.update(extra)
    return payload


def plan_for(body):
    """What a well-behaved planner would answer: one step per recalled reference."""
    request = json.loads(body)
    context = json.loads(request["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
    steps = [{"id": f"stats-{i + 1}", "tool": "text.stats",
              "parameters": {"reference": f"{item['information_id']}@{item['revision']}"}}
             for i, item in enumerate(context["items"])]
    return json.dumps({"version": 1, "steps": steps})


# Module-level transports: the Runtime runs the model in a spawn worker, which pickles them.
class PlanningTransport:
    def post(self, url, body, *, timeout, max_bytes):
        return 200, "application/json; charset=utf-8", json.dumps(answer(plan_for(body))).encode()


class CannedTransport:
    def __init__(self, status, content_type, payload):
        self.status, self.content_type, self.payload = status, content_type, payload
        self.calls = []

    def post(self, url, body, *, timeout, max_bytes):
        self.calls.append({"url": url, "body": json.loads(body), "timeout": timeout, "max_bytes": max_bytes})
        raw = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return self.status, self.content_type, raw


class DownTransport:
    def post(self, url, body, *, timeout, max_bytes):
        raise OllamaError("TRANSPORT", "ConnectionRefusedError")


def config(**kwargs):
    values = {"endpoint": "http://127.0.0.1:11434", "model": MODEL,
              "options": {"temperature": 0, "seed": 7, "num_predict": 512}}
    values.update(kwargs)
    return OllamaConfig(**values)


CONTEXT = {"items": [{"information_id": "synthetic-note", "revision": 1, "content": "texte"}]}


class ConfigurationTests(unittest.TestCase):
    def test_no_default_endpoint_or_model(self):
        with self.assertRaises(TypeError):
            OllamaConfig()  # pylint: disable=no-value-for-parameter

    def test_endpoint_must_be_a_bare_loopback_base_url_unless_approved(self):
        for endpoint in ("ftp://127.0.0.1:11434", "http://user:pw@127.0.0.1:11434",
                         "http://127.0.0.1:11434/api/chat", "http://127.0.0.1:11434/?x=1", "127.0.0.1:11434",
                         "http://nas.example.invalid:11434", "https://ollama.com"):
            with self.assertRaises(ContractError, msg=endpoint):
                config(endpoint=endpoint)
        approved = config(endpoint="http://ollama.example.invalid:11434", allow_non_loopback=True)
        self.assertEqual(approved.url(), "http://ollama.example.invalid:11434/api/chat")
        self.assertEqual(config(endpoint="http://[::1]:11434/").url(), "http://[::1]:11434/api/chat")

    def test_options_and_budgets_are_validated(self):
        for kwargs in ({"options": {"temperature": float("nan")}}, {"options": {"stop": ["}"]}},
                       {"options": {"temperature": "0"}}, {"timeout_seconds": 0}, {"max_output_bytes": 0},
                       {"model": "two words"}, {"model": ""}, {"allow_non_loopback": 1}):
            with self.assertRaises(ContractError, msg=kwargs):
                config(**kwargs)

    def test_model_id_reflects_the_canonical_configuration(self):
        base = OllamaModel(config()).model_id
        self.assertTrue(base.startswith(f"ollama/{MODEL}@"))
        self.assertEqual(OllamaModel(config(options={"num_predict": 512, "seed": 7, "temperature": 0})).model_id, base)
        for change in ({"model": "other:1b"}, {"endpoint": "http://localhost:11434"},
                       {"options": {"temperature": 0.2}}, {"timeout_seconds": 30}, {"max_output_bytes": 1000}):
            self.assertNotEqual(OllamaModel(config(**change)).model_id, base, change)
        self.assertEqual(config().manifest()["budgets"]["output_tokens"], 512)


class ProtocolTests(unittest.TestCase):
    def propose(self, status=200, content_type="application/json", payload=None, **kwargs):
        transport = CannedTransport(status, content_type, answer('{"version":1}') if payload is None else payload)
        model = OllamaModel(config(**kwargs), transport)
        return model.propose(DEMO_REQUEST, CONTEXT), transport

    def test_request_follows_the_documented_non_streaming_chat_call(self):
        text, transport = self.propose()
        self.assertEqual(text, '{"version":1}')
        call = transport.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:11434/api/chat")
        body = call["body"]
        self.assertEqual(set(body), {"model", "messages", "stream", "format", "options"})
        self.assertIs(body["stream"], False)
        self.assertNotIn("tools", body)
        self.assertEqual(body["options"], {"num_predict": 512, "seed": 7, "temperature": 0})
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        self.assertIn("untrusted", body["messages"][1]["content"])
        self.assertEqual(body["format"]["required"], ["version", "steps"])
        self.assertEqual((call["timeout"], call["max_bytes"]), (60.0, 256_000))

    def test_documented_latest_tag_is_the_same_model(self):
        text, _ = self.propose(payload=answer("{}", model="synthetic-planner:1b"), model="synthetic-planner:1b")
        self.assertEqual(text, "{}")
        text, _ = self.propose(payload=answer("{}", model="planner:latest"), model="planner")
        self.assertEqual(text, "{}")

    def test_failures_are_errors_never_an_empty_plan(self):
        long_text = "x" * 70_000
        cases = {
            "HTTP_STATUS": dict(status=404, payload={"error": "model 'x' not found"}),
            "HTTP_STATUS ": dict(status=502, payload=b"<html>bad gateway</html>"),
            "BAD_RESPONSE": dict(payload=b"not json"),
            "BAD_RESPONSE ": dict(content_type="application/x-ndjson"),
            "BAD_RESPONSE  ": dict(payload=["list"]),
            "BAD_RESPONSE   ": dict(payload=answer("{}", done=False)),
            "BAD_RESPONSE    ": dict(payload={"model": MODEL, "done": True, "message": {"role": "user", "content": "{}"}}),
            "MODEL_ERROR": dict(payload={"error": "an error was encountered while running the model"}),
            "INCOMPLETE": dict(payload=answer('{"version":1,"st', done_reason="length")),
            "MODEL_MISMATCH": dict(payload=answer("{}", model="other:70b")),
            "MODEL_MISMATCH ": dict(payload={k: v for k, v in answer("{}").items() if k != "model"}),
            "TOOL_CALL_REFUSED": dict(payload=answer("", message={"role": "assistant", "content": "",
                                      "tool_calls": [{"function": {"name": "service.restart", "arguments": {}}}]})),
            "EMPTY_OUTPUT": dict(payload=answer("   ")),
            "EMPTY_OUTPUT ": dict(payload=answer(None)),
            "OUTPUT_TOO_LARGE": dict(payload=answer(long_text)),
            "BAD_RESPONSE     ": dict(payload=b'{"model":"x","done":true,"eval_count":NaN}'),
        }
        for code, kwargs in cases.items():
            with self.assertRaises(OllamaError, msg=code) as raised:
                self.propose(**kwargs)
            self.assertEqual(raised.exception.code, code.strip(), code)

    def test_prompt_budget_is_checked_before_any_transport_call(self):
        transport = CannedTransport(200, "application/json", answer("{}"))
        model = OllamaModel(config(max_prompt_bytes=2_000), transport)
        big = {"items": [{"information_id": "n", "revision": 1, "content": "y" * 3_000}]}
        with self.assertRaises(OllamaError) as raised:
            model.propose(DEMO_REQUEST, big)
        self.assertEqual((raised.exception.code, transport.calls), ("PROMPT_TOO_LARGE", []))


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        route = self.server.route
        if route == "redirect":
            self.send_response(307)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
            return
        if route == "slow":
            time.sleep(2)
        if route == "huge":
            raw = json.dumps(answer("x" * 300_000)).encode()
        elif route == "missing":
            raw = json.dumps({"error": f"model '{MODEL}' not found"}).encode()
        else:
            raw = json.dumps(answer(plan_for(body))).encode()
        self.send_response(404 if route == "missing" else 200)
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
        self.server.route = "ok"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.model = OllamaModel(config(endpoint=f"http://127.0.0.1:{self.server.server_port}",
                                        timeout_seconds=0.5), UrllibTransport())

    def code(self):
        with self.assertRaises(OllamaError) as raised:
            self.model.propose(DEMO_REQUEST, CONTEXT)
        return raised.exception.code

    def test_plan_text_over_http(self):
        self.assertEqual(json.loads(self.model.propose(DEMO_REQUEST, CONTEXT))["steps"][0]["tool"], "text.stats")

    def test_http_errors_redirects_size_and_timeout(self):
        expected = {"missing": "HTTP_STATUS", "redirect": "HTTP_STATUS", "huge": "RESPONSE_TOO_LARGE",
                    "slow": "TRANSPORT"}
        for route, code in expected.items():
            self.server.route = route
            self.assertEqual(self.code(), code, route)

    def test_connection_refused(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        model = OllamaModel(config(endpoint=f"http://127.0.0.1:{port}", timeout_seconds=0.5))
        with self.assertRaises(OllamaError) as raised:
            model.propose(DEMO_REQUEST, CONTEXT)
        self.assertEqual(raised.exception.code, "TRANSPORT")


class RuntimeIntegrationTests(unittest.TestCase):
    """The adapter plugs into Runtime unchanged; Core keeps every check."""

    def run_with(self, transport):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Store(temp.name), model=OllamaModel(config(), transport))
        return runtime.run(runtime.create(DEMO_REQUEST)["id"])

    def test_valid_plan_still_goes_through_core_checks(self):
        m = self.run_with(PlanningTransport())
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertTrue(m["configuration"]["model"].startswith("ollama/"))

    def test_transport_failure_blocks_instead_of_planning(self):
        m = self.run_with(DownTransport())
        self.assertEqual((m["status"], m["error"]["code"], m["plan"]), ("BLOCKED", "MODEL_UNAVAILABLE", None))

    def test_invalid_or_unauthorized_plans_are_refused_by_core(self):
        bad = self.run_with(CannedTransport(200, "application/json", answer('{"version":1,"steps":[]}')))
        self.assertEqual((bad["status"], bad["error"]["code"]), ("FAILED", "MODEL_INVALID"))
        restart = json.dumps({"version": 1, "steps": [
            {"id": "r", "tool": "service.restart", "parameters": {"target": "memory-engine"}}]})
        denied = self.run_with(CannedTransport(200, "application/json", answer(restart)))
        self.assertEqual((denied["status"], denied["error"]["code"]), ("BLOCKED", "PREFLIGHT_REFUSED"))
        self.assertEqual(denied["calls"], [])


if __name__ == "__main__":
    unittest.main()
