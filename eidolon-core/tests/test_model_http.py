# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_model_http.py
# Description : Frontières HTTP réelles des deux planificateurs candidats
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Raw loopback HTTP responses; no inference server or model is contacted."""
from email.message import Message
import io
import tempfile
from socketserver import StreamRequestHandler, ThreadingTCPServer
import threading
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from eidolon_core.ollama_model import OllamaError, UrllibTransport
from eidolon_core.openai_chat_model import OpenAIChatError, UrllibChatTransport, OpenAIChatConfig, OpenAIChatModel

CANARY = "synthetic-private-http-error"


class WireHandler(StreamRequestHandler):
    def handle(self):
        self.rfile.readline()
        length = 0
        while True:
            line = self.rfile.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1])
        self.rfile.read(length)
        self.server.requests += 1
        self.wfile.write(self.server.response)


class ModelHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingTCPServer(("127.0.0.1", 0), WireHandler)
        self.server.daemon_threads = True
        self.server.requests = 0
        self.server.response = b""
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/synthetic"

    def stop(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def post(self, provider, budget=1024):
        if provider == "ollama":
            return UrllibTransport().post(self.url, b"{}", timeout=.5, max_bytes=budget)
        return UrllibChatTransport().post(self.url, b"{}", headers={"Content-Type": "application/json"},
                                         timeout=.5, max_bytes=budget)

    def response(self, status, headers, body):
        self.server.response = (f"HTTP/1.1 {status} Synthetic\r\nContent-Type: application/json\r\n"
                                "Connection: close\r\n" + headers + "\r\n").encode() + body

    def assertRefused(self, code, *, budget=1024):
        for provider, error in (("ollama", OllamaError), ("llama", OpenAIChatError)):
            before = self.server.requests
            with self.subTest(provider=provider):
                with self.assertRaises(error) as raised:
                    self.post(provider, budget)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn(CANARY, "".join(traceback.format_exception(raised.exception)))
                self.assertEqual(self.server.requests, before + 1, "transport retried unexpectedly")

    def test_eof_inside_headers_is_incomplete_http_for_all_local_transports(self):
        from eidolon_core.media_agents import MediaError
        from eidolon_core.media_backends import json_http
        from eidolon_core.media_transfer import raw_http
        for response in (
                b"HTTP/1.1 200 OK\r\nContent-Ty",
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n",
                b"HTTP/1.1 500 Synthetic\r\nX-Private: " + CANARY.encode(),
                b"HTTP/1.1 100 Continue\r\n\r\n",
                b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Ty",
                b"HTTP/1.1 200 OK"):
            self.server.response = response
            self.assertRefused("INCOMPLETE_HTTP")
            for call in (lambda: json_http("POST", self.url, {}),
                         lambda: raw_http("GET", self.url, None, None, 1024)):
                before = self.server.requests
                with self.assertRaises(MediaError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "INCOMPLETE_HTTP")
                self.assertNotIn(CANARY, "".join(traceback.format_exception(raised.exception)))
                self.assertEqual(self.server.requests, before + 1)

    def test_interim_headers_and_close_delimited_body_keep_the_original_stream(self):
        for prefix in (b"", b"HTTP/1.1 100 Continue\r\nX-Synthetic: yes\r\n\r\n"):
            self.server.response = prefix + b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{}"
            for provider in ("ollama", "llama"):
                status, content_type, body = self.post(provider)
                self.assertEqual((status, content_type, body), (200, "application/json", b"{}"))
        self.server.response = b"HTTP/1.1 200 OK\nContent-Type: application/json\nContent-Length: 2\n\n{}"
        self.assertEqual(self.post("ollama")[2], b"{}")  # Preserve stdlib's LF handling.

    def test_eof_before_any_response_keeps_transport_failure(self):
        self.server.response = b""
        self.assertRefused("TRANSPORT")

    def test_complete_content_length_chunked_and_close_delimited(self):
        for status in (200, 500):
            for headers, raw in (("Content-Length: 2\r\n", b"{}"), ("", b"{}"),
                                 ("Transfer-Encoding: chunked\r\n", b"2\r\n{}\r\n0\r\n\r\n")):
                self.response(status, headers, raw)
                for provider in ("ollama", "llama"):
                    with self.subTest(status=status, headers=headers, provider=provider):
                        actual, content_type, body = self.post(provider)
                        self.assertEqual((actual, content_type, body), (status, "application/json", b"{}"))

    def test_premature_eof_is_not_a_complete_body_even_when_json_parses(self):
        for status in (200, 500):
            self.response(status, "Content-Length: 12\r\n", b"{}")
            with self.subTest(status=status):
                self.assertRefused("INCOMPLETE_HTTP")

    def test_ambiguous_or_invalid_http_framing_is_refused(self):
        for status in (200, 500):
            for headers in ("Content-Length: 2\r\nContent-Length: 3\r\n",
                            "Content-Length: 2\r\nContent-Length: 2\r\n",
                            "Content-Length: -1\r\n", "Content-Length: +2\r\n",
                            "Content-Length: " + CANARY + "\r\n",
                            "Content-Length: 2\r\nTransfer-Encoding: chunked\r\n",
                            "Transfer-Encoding: gzip, chunked\r\n",
                            "Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n"):
                self.response(status, headers, b"{}")
                with self.subTest(status=status, headers=headers):
                    self.assertRefused("BAD_HTTP_FRAMING")

    def test_oversized_header_or_body_respects_budget(self):
        for status in (200, 500):
            self.response(status, "Content-Length: 1000\r\n", b"{}")
            self.assertRefused("RESPONSE_TOO_LARGE", budget=16)
            self.response(status, "", b"a" * 17)
            self.assertRefused("RESPONSE_TOO_LARGE", budget=16)

    def test_malformed_chunk_in_http_error_uses_sanitized_transport_error(self):
        for status in (200, 500):
            self.response(status, "Transfer-Encoding: chunked\r\n", CANARY.encode() + b"\r\n")
            with self.subTest(status=status):
                self.assertRefused("TRANSPORT")

    def test_error_body_read_failure_is_sanitized_and_closed(self):
        class BrokenBody(io.BytesIO):
            def read(self, *_):
                raise OSError(CANARY)

        for provider, error in (("ollama", OllamaError), ("llama", OpenAIChatError)):
            body = BrokenBody()
            headers = Message()
            headers["Content-Type"] = "application/json"
            failed = HTTPError(self.url, 500, "server error", headers, body)

            def fail_open(*args, **kwargs):
                raise failed

            with patch("urllib.request.build_opener", return_value=SimpleNamespace(open=fail_open)):
                with self.assertRaises(error) as raised:
                    self.post(provider)
            self.assertEqual(raised.exception.code, "TRANSPORT")
            self.assertNotIn(CANARY, "".join(traceback.format_exception(raised.exception)))
            self.assertTrue(body.closed)

    def test_malformed_json_traceback_does_not_reflect_unknown_key(self):
        model = OpenAIChatModel(OpenAIChatConfig(endpoint=self.url.rsplit("/", 1)[0], model="synthetic"))
        raw = ('{"' + CANARY + '":1,"' + CANARY + '":2}').encode()
        try:
            model.read_response(200, "application/json", raw)
        except OpenAIChatError as error:
            diagnostic = "".join(traceback.format_exception(error))
        else:
            self.fail("malformed JSON accepted")
        self.assertNotIn(CANARY, diagnostic)

    def test_version_two_missions_do_not_resume_under_changed_transport_contract(self):
        from eidolon_core.contracts import digest
        from eidolon_core.memory import DEMO_REQUEST
        from eidolon_core.ollama_model import OllamaConfig, OllamaModel
        from eidolon_core.runtime import Runtime
        from eidolon_core.store import Store
        endpoint = self.url.rsplit("/", 1)[0]
        cases = ((OllamaModel(OllamaConfig(endpoint, "synthetic")), "ollama", "ollama-chat/2"),
                 (OpenAIChatModel(OpenAIChatConfig(endpoint, "synthetic")), "openai-chat", "openai-chat-llamacpp/2"))
        for model, prefix, prior_version in cases:
            with self.subTest(adapter=prior_version), tempfile.TemporaryDirectory() as state:
                runtime = Runtime(Store(state), model=model)
                previous = {**model.config.manifest(), "adapter": prior_version}
                old = {**runtime.configuration(), "model": f"{prefix}/synthetic@{digest(previous)[:16]}"}
                mission = runtime.store.create(DEMO_REQUEST, old)
                result = runtime.run(mission["id"])
                self.assertEqual(result["error"]["code"], "CONFIGURATION_CHANGED")
                self.assertEqual(result["calls"], [])
                self.assertEqual(self.server.requests, 0)


if __name__ == "__main__":
    unittest.main()
