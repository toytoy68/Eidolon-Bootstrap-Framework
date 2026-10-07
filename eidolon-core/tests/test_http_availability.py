# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_http_availability.py
# Description : Préconnexions, saturation et lecture lente sur sockets réelles
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core import http_api
from eidolon_core.store import Store

TOKEN = "availability_fixture_" + "x" * 32


class ObservedServer(http_api.ReadServer):
    def __init__(self, *args, **kwargs):
        self.accepted = threading.Condition()
        self.accepted_count = 0
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        with self.accepted:
            self.accepted_count += 1
            self.accepted.notify_all()
        super().process_request(request, address)


class HTTPAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.server = ObservedServer(self.store.directory, TOKEN, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def wait_accepted(self, count):
        with self.server.accepted:
            self.assertTrue(self.server.accepted.wait_for(lambda: self.server.accepted_count >= count, timeout=2))

    def idle(self):
        s = socket.create_connection(self.server.server_address, timeout=1)
        self.addCleanup(s.close)
        return s

    def health(self, *, timeout=.8, token=TOKEN):
        c = HTTPConnection(*self.server.server_address, timeout=timeout)
        try:
            c.request("GET", "/v1/health", headers={"Authorization": "Bearer " + token})
            r = c.getresponse()
            return r.status, json.loads(r.read())
        finally:
            c.close()

    def test_browser_preconnect_does_not_block_health(self):
        idle = self.idle()
        try:
            self.wait_accepted(1)
            status, data = self.health()
            self.assertEqual(status, 200)
            self.assertEqual(data["mode"], "read_only")
        finally:
            idle.close()

    def test_three_idle_connections_leave_a_slot_for_health(self):
        sockets = [self.idle() for _ in range(3)]
        try:
            self.wait_accepted(3)
            self.assertEqual(self.health()[0], 200)
        finally:
            for s in sockets:
                s.close()

    def test_full_capacity_refuses_extra_socket_without_new_worker(self):
        sockets = [self.idle() for _ in range(4)]
        try:
            self.wait_accepted(4)
            status, data = self.health()
            self.assertEqual(status, 503)
            self.assertEqual(data, {"protocol": http_api.PROTOCOL, "error": "BUSY",
                                    "authorizes_execution": False})
            with self.server._worker_lock:
                self.assertEqual(len(self.server._workers), 4)
        finally:
            for s in sockets:
                s.close()

    def test_busy_response_preserves_the_complete_client_csp(self):
        sockets = [self.idle() for _ in range(4)]
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            self.wait_accepted(4)
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertEqual(response.status, 503)
            response.read()
            self.assertEqual(response.getheader("Content-Security-Policy"),
                             "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                             "img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.assertEqual(response.getheader("Referrer-Policy"), "no-referrer")
            self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        finally:
            connection.close()
            for sock in sockets:
                sock.close()

    def test_busy_response_is_fixed_pre_auth_and_service_recovers(self):
        before = self.store.path.read_bytes()
        sockets = [self.idle() for _ in range(4)]
        self.wait_accepted(4)
        with patch.object(self.server.store, "health", side_effect=AssertionError("no state lookup")):
            for token in (TOKEN, "invalid"):
                status, data = self.health(token=token)
                self.assertEqual((status, data["error"]), (503, "BUSY"))
                self.assertNotIn(token, json.dumps(data))
        for s in sockets:
            s.close()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with self.server._worker_lock:
                if not self.server._workers:
                    break
            time.sleep(.01)
        self.assertEqual(self.health()[0], 200)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_unwritable_overload_response_closes_without_worker(self):
        from unittest.mock import Mock
        request = Mock()
        request.sendall.side_effect = TimeoutError("synthetic backpressure")
        with self.server._worker_lock:
            self.server._closing = True
        try:
            with patch.object(self.server, "shutdown_request") as close:
                self.server.process_request(request, ("127.0.0.1", 0))
                close.assert_called_once_with(request)
            request.settimeout.assert_called_once_with(http_api.BUSY_WRITE_TIMEOUT_SECONDS)
        finally:
            with self.server._worker_lock:
                self.server._closing = False
        self.assertEqual(self.health()[0], 200)

    def test_expensive_sql_is_interrupted_without_mutation_and_next_read_recovers(self):
        before = self.store.path.read_bytes()
        self.server.store.query_budget_seconds = .02
        with self.assertRaisesRegex(sqlite3.OperationalError, "interrupted"):
            with self.server.store.connection() as db:
                db.execute("WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n "
                           "WHERE x<1000000000) SELECT sum(x) FROM n").fetchone()
        self.assertEqual(self.health()[0], 200)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_sql_interruption_is_sanitized_at_http_boundary(self):
        with patch.object(self.server.store, "health", side_effect=sqlite3.OperationalError("interrupted private SQL")):
            status, data = self.health()
        self.assertEqual((status, data["error"]), (503, "STATE_UNAVAILABLE"))
        self.assertNotIn("private", json.dumps(data))
        self.assertEqual(self.health()[0], 200)

    def test_shutdown_interrupts_idle_reads_and_joins_workers(self):
        idle = self.idle()
        self.wait_accepted(1)
        self.server.shutdown()
        before = time.monotonic()
        self.server.server_close()
        self.assertLess(time.monotonic() - before, 1)
        with self.server._worker_lock:
            self.assertEqual(len(self.server._workers), 0)
        self.assertEqual(idle.recv(1), b"")

    def test_concurrent_valid_reads_and_authentication_failures(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda i: self.health(token=TOKEN if i % 2 else "invalid"), range(18)))
        self.assertEqual([r[0] for r in results], [401 if i % 2 == 0 else 200 for i in range(18)])
        identities = {r[1]["store_id"] for r in results if r[0] == 200}
        self.assertEqual(len(identities), 1)
        self.assertNotIn(TOKEN, json.dumps(results))

    def test_worker_start_failure_releases_slot_and_closes_socket(self):
        with patch("threading.Thread.start", side_effect=RuntimeError("synthetic thread start failure")):
            s = self.idle()
            self.wait_accepted(1)
            self.assertEqual(s.recv(1), b"")
        with self.server._worker_lock:
            self.assertEqual(len(self.server._workers), 0)
        self.assertEqual(self.health()[0], 200)

    def trickle(self, body):
        # Reduced per-server limits retain the same relationship as production:
        # regular bytes arrive within the idle timeout, but exceed total time.
        self.server.read_deadline_seconds = .45
        self.server.idle_timeout_seconds = .20
        client = self.idle()
        port = self.server.server_port
        if body:
            client.sendall((f"POST /v1/missions HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n"
                            f"Authorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\n"
                            "Content-Length: 8192\r\n\r\n{").encode())
        else:
            client.sendall(b"GET /v1/health HTTP/1.0\r\nX-Slow: ")
        self.wait_accepted(1)
        stop = threading.Event()

        def send():
            while not stop.wait(.04):
                try:
                    client.sendall(b" ")
                except OSError:
                    return

        sender = threading.Thread(target=send)
        sender.start()
        before = time.monotonic()
        received = b""
        try:
            client.settimeout(1.2)
            while chunk := client.recv(4096):
                received += chunk
        finally:
            stop.set()
            sender.join(1)
            client.close()
        self.assertLess(time.monotonic() - before, 1.1)
        self.assertGreater(time.monotonic() - before, .20)
        self.assertEqual(self.health()[0], 200)
        return received

    def test_trickling_headers_have_a_total_read_deadline(self):
        self.trickle(False)

    def test_trickling_body_has_a_total_read_deadline(self):
        response = self.trickle(True)
        self.assertIn(b"408", response.split(b"\r\n", 1)[0])
        self.assertIn(b"REQUEST_TIMEOUT", response)


if __name__ == "__main__":
    unittest.main()
