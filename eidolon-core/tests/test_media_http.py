# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_http.py
# Description : Échéances HTTP média : flux lents, framing et effet incertain
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import contextmanager
import socketserver
import threading
import time
import unittest

from eidolon_core.media_agents import MediaError
from eidolon_core.media_backends import json_http, LocalMediaBackend
from eidolon_core.media_http import exchange
from eidolon_core.media_transfer import raw_http


@contextmanager
def engine(reply, *, read_request=True):
    stop = threading.Event(); calls = []
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            calls.append(True)
            self.request.settimeout(2)
            try:
                if read_request:
                    data = b""
                    while b"\r\n\r\n" not in data:
                        data += self.request.recv(4096)
                        if len(data) > 100000: raise AssertionError("request too large")
                reply(self.request, stop)
            except OSError:
                pass  # the deadline deliberately closes the connection
    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
    server = Server(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
    worker.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_address[1]), calls
    finally:
        stop.set(); server.shutdown(); server.server_close(); worker.join(3)


def drip(parts):
    def reply(sock, stop):
        for part in parts:
            sock.sendall(part)
            if stop.wait(.035): break
    return reply


class HTTPDeadlineTests(unittest.TestCase):
    def bounded(self, response, *, binary=False):
        with engine(response) as (url, calls):
            started = time.monotonic()
            with self.assertRaisesRegex(MediaError, "MEDIA_HTTP_DEADLINE"):
                if binary:
                    raw_http("GET", url + "/view", None, None, 1024, timeout=.18)
                else:
                    json_http("POST", url + "/prompt", {}, timeout=.18)
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, .8)
            self.assertGreater(elapsed, .1)
            self.assertEqual(len(calls), 1)

    def test_trickled_status_and_headers_cannot_extend_deadline(self):
        self.bounded(drip([bytes([c]) for c in b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}"] ))
        self.bounded(drip([b"HTTP/1.1 200 OK\r\n"] + [b"X-A: a\r\n"] * 40 + [b"\r\n{}"] ))

    def test_fixed_chunked_and_close_bodies_have_one_deadline(self):
        headers = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        for framing, pieces in ((b"Content-Length: 30\r\n\r\n", [b" "] * 28 + [b"{}"]),
                                (b"Transfer-Encoding: chunked\r\n\r\n", [b"1\r\n \r\n"] * 28 + [b"0\r\n\r\n"]),
                                (b"Connection: close\r\n\r\n", [b" "] * 28 + [b"{}"])):
            with self.subTest(framing=framing):
                self.bounded(drip([headers + framing] + pieces))

    def test_binary_download_and_slow_chunk_size_lines_are_bounded(self):
        self.bounded(drip([b"HTTP/1.1 200 OK\r\nContent-Length: 30\r\n\r\n"] + [b"x"] * 30), binary=True)
        self.bounded(drip([b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"]
                          + [b"0"] * 20 + [b"\r\n\r\n"]))

    def test_request_send_to_nonreading_peer_is_bounded(self):
        with engine(lambda sock, stop: stop.wait(2), read_request=False) as (url, calls):
            started = time.monotonic()
            with self.assertRaisesRegex(MediaError, "MEDIA_HTTP_DEADLINE"):
                exchange("POST", url + "/upload/image", b"x" * (16 * 1024 * 1024), {}, 1024, timeout=.18)
            self.assertLess(time.monotonic() - started, .9)
            self.assertEqual(len(calls), 1)

    def test_normal_fixed_chunked_and_close_responses_still_decode(self):
        head = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        for body in (head+b"Content-Length: 2\r\n\r\n{}", head+b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n",
                     head+b"Connection: close\r\n\r\n{}"):
            with self.subTest(body=body), engine(lambda sock, stop: sock.sendall(body)) as (url, _):
                self.assertEqual(json_http("POST", url + "/prompt", {}, timeout=1), {})

    def test_timeout_and_nonlocal_urls_rejected_before_connect(self):
        for timeout in (0, -1, True, float("inf"), float("nan"), 3601):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(MediaError, "INVALID_MEDIA_HTTP_TIMEOUT"):
                json_http("POST", "http://127.0.0.1:9/prompt", {}, timeout=timeout)
        for url in ("http://example.invalid:80/prompt", "file:///etc/passwd", "http://127.0.0.1:9/prompt#fragment"):
            with self.subTest(url=url), self.assertRaises(MediaError):
                json_http("POST", url, {})

    def test_timeout_during_worker_attempt_keeps_lease_and_never_retries(self):
        from tests.test_media_worker import WorkerTests
        from tests.test_media_agents import config
        from eidolon_core.media_agents import inspect
        fixture = WorkerTests(); fixture.setUp()
        try:
            ticket = fixture.enqueue()
            with engine(drip([b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 30\r\n\r\n"]
                             + [b" "] * 28 + [b"{}"])) as (url, calls):
                cfg = {**config(), **fixture.cfg, "comfy_endpoint": url}
                backend = LocalMediaBackend(cfg, transport=lambda m,u,p: json_http(m,u,p,timeout=.18))
                with self.assertRaisesRegex(MediaError, "MEDIA_ATTEMPT_UNCERTAIN"):
                    fixture.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=fixture.conv,
                                            config=cfg, execute_local=True, backend=backend)
                result = fixture.worker.run_once(ticket["ticket_id"], client_id="pc", conversations=fixture.conv,
                                                 config=cfg, execute_local=True, backend=backend)
                self.assertEqual(result["state"], "REVIEW_REQUIRED")
                self.assertEqual(len(calls), 1)
                self.assertEqual(fixture.pool.inspect()["state"], "RESERVED")
                self.assertEqual(inspect(fixture.path / ticket["ticket_id"])["failure_code"], "MEDIA_HTTP_DEADLINE")
        finally:
            fixture.doCleanups()
