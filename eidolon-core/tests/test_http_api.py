# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_http_api.py
# Description : Consultation réelle HTTP, frontières et absence de mutation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core import http_api
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

TOKEN = "synthetic_test_token_" + "x" * 32


class HTTPReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state")
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create(DEMO_REQUEST)
        self.server = http_api.ReadServer(self.store.directory, TOKEN, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def request(self, path, *, method="GET", data=None, body=None, headers=None, auth=True):
        fields = {"Authorization": "Bearer " + TOKEN} if auth else {}
        if data is not None:
            body = json.dumps(data).encode()
        if body is not None:
            fields["Content-Type"] = "application/json"
        fields.update(headers or {})
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(conn.close)
        conn.request(method, path, body=body, headers=fields)
        response = conn.getresponse()
        raw = response.read()
        return response.status, dict(response.getheaders()), raw

    def json(self, path, **kwargs):
        status, headers, raw = self.request(path, **kwargs)
        return status, headers, json.loads(raw)

    def post(self, data=None, **kwargs):
        return self.json("/v1/missions", method="POST", data={} if data is None else data, **kwargs)

    def raw(self, data):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5) as connection:
            connection.sendall(data)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := connection.recv(65536):
                chunks.append(chunk)
        return b"".join(chunks)

    def test_locked_storage_is_busy_and_recovers_after_explicit_read(self):
        lock = sqlite3.connect(self.store.path)
        lock.execute("BEGIN EXCLUSIVE")
        try:
            status, _, body = self.json("/v1/health")
            self.assertEqual((status, body["error"]), (503, "STATE_BUSY"))
            self.assertFalse(body["authorizes_execution"])
            self.assertNotIn(str(self.store.path), json.dumps(body))
        finally:
            lock.rollback(); lock.close()
        self.assertEqual(self.json("/v1/health")[0], 200)

    def test_authenticated_health_and_loopback_only(self):
        status, headers, result = self.json("/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(result["mode"], "read_only")
        self.assertFalse(result["authorizes_execution"])
        self.assertRegex(result["store_id"], r"^s-[a-f0-9]{32}$")
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Connection"], "close")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_absent_wrong_duplicate_or_query_token_never_reads(self):
        with patch.object(self.server.store, "health", side_effect=AssertionError("must authenticate first")):
            for extra in ({"auth": False}, {"headers": {"Authorization": "Bearer wrong"}},
                          {"headers": {"Authorization": TOKEN}}):
                self.assertEqual(self.json("/v1/health", **extra)[0], 401)
            self.assertEqual(self.json("/v1/health?token=" + TOKEN, auth=False)[0], 401)
            host = f"127.0.0.1:{self.server.server_port}"
            response = self.raw((f"GET /v1/health HTTP/1.1\r\nHost: {host}\r\n"
                                 f"Authorization: Bearer {TOKEN}\r\nAuthorization: Bearer {TOKEN}\r\n\r\n").encode())
            self.assertIn(b"401 Unauthorized", response)
            self.assertNotIn(TOKEN.encode(), response)

    def test_host_origin_and_duplicate_host_are_refused(self):
        host = f"127.0.0.1:{self.server.server_port}"
        for headers in ({"Host": "evil.example"}, {"Host": "127.0.0.1"},
                        {"Origin": "null"}, {"Origin": "https://evil.example"},
                        {"Origin": "http://localhost:1"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.json("/v1/health", headers=headers)[0], 403)
        self.assertEqual(self.json("/v1/health", headers={"Origin": "http://" + host})[0], 200)
        raw = self.raw((f"GET /v1/health HTTP/1.1\r\nHost: {host}\r\nHost: evil.example\r\n\r\n").encode())
        self.assertIn(b"400 Bad Request", raw)

    def test_listing_snapshot_poll_observe_external_writer_without_mutation(self):
        status, _, page = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(page["items"][0]["mission"]["id"], self.mission["id"])
        path = "/v1/missions/" + self.mission["id"]
        status, _, snapshot = self.json(path)
        self.assertEqual(snapshot["status"], "SNAPSHOT")
        self.store.request_cancel(self.mission["id"])
        before = self.store.path.read_bytes()
        with patch("eidolon_core.worker.invoke", side_effect=AssertionError("no tools")):
            status, _, delta = self.json(path + "/poll", method="POST", data={"cursor": snapshot["cursor"]})
        self.assertEqual(status, 200)
        self.assertEqual(delta["status"], "DELTA")
        self.assertTrue(delta["snapshot"]["mission"]["cancel_requested"])
        self.assertEqual(len(delta["events"]), 1)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_list_reset_after_concurrent_creation(self):
        self.runtime.create(DEMO_REQUEST)
        _, _, first = self.post({"limit": 1})
        self.assertTrue(first["has_more"])
        self.runtime.create(DEMO_REQUEST)
        status, _, result = self.post({"cursor": first["next_cursor"], "limit": 1})
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "RESET_REQUIRED")
        self.assertEqual(result["items"], [])

    def test_pagination_covers_all_missions_once(self):
        expected = {self.mission["id"]}
        expected.update(self.runtime.create(DEMO_REQUEST)["id"] for _ in range(4))
        result, cursor = [], None
        for _ in range(3):
            status, _, page = self.post({"limit": 2, "cursor": cursor})
            self.assertEqual(status, 200)
            result.extend(x["mission"]["id"] for x in page["items"])
            cursor = page["next_cursor"]
        self.assertIsNone(cursor)
        self.assertEqual(result, sorted(expected))

    def test_bad_json_duplicate_fields_and_numbers_are_rejected(self):
        for body in (b'{"limit":1,"limit":2}', b'[]', b'null', b'{', b'\xff',
                     b'{"limit":NaN}', b'{"limit":1e9999}', b'{"cursor":"\\ud800"}',
                     b'{"cursor":' + b'[' * 1500 + b']' * 1500 + b'}'):
            with self.subTest(body=body[:30]):
                status, _, result = self.json("/v1/missions", method="POST", body=body)
                self.assertEqual(status, 400)
                self.assertEqual(result["error"], "INVALID_JSON")

    def test_bad_cursor_unknown_keys_and_limits(self):
        for value in ({"limit": True}, {"limit": 101}, {"cursor": {}}, {"extra": "private"}):
            self.assertEqual(self.post(value)[0], 400)
        path = "/v1/missions/" + self.mission["id"] + "/poll"
        for value in ({}, {"cursor": None}, {"cursor": []}):
            self.assertEqual(self.json(path, method="POST", data=value)[0], 400)

    def test_body_type_and_size_are_bounded(self):
        self.assertEqual(self.request("/v1/missions", method="POST", body=b"{}",
                                      headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/v1/missions", method="POST", body=b"x" * 8193)[0], 413)
        self.assertEqual(self.json("/v1/health", body=b"private")[0], 400)
        status = self.request("/v1/missions", method="POST", body=b"{}",
                              headers={"Content-Type": "application/json; charset=utf-8"})[0]
        self.assertEqual(status, 200)

    def test_truncated_and_ambiguous_http_bodies(self):
        prefix = (f"POST /v1/missions HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n"
                  f"Authorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\n")
        for headers in ("Content-Length: 99", "Content-Length: -1", "Content-Length: 2\r\nContent-Length: 2",
                        "Transfer-Encoding: chunked", "Expect: 100-continue"):
            with self.subTest(headers=headers):
                result = self.raw((prefix + headers + "\r\n\r\n{}").encode())
                self.assertIn(b"400 Bad Request", result)

    def test_no_command_routes_or_paths(self):
        before = self.store.path.read_bytes()
        for path in ("/v1/run", "/v1/commands", "/v1/missions/../../etc/passwd", "/v1/health?x=1"):
            self.assertEqual(self.json(path)[0], 404)
        for method in ("PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "UNKNOWN"):
            self.assertEqual(self.request("/v1/missions", method=method)[0], 405)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_unknown_mission_is_distinct_from_corrupt_mission(self):
        self.assertEqual(self.json("/v1/missions/m-" + "0" * 32)[0], 404)
        with self.store.connection() as db:
            db.execute("UPDATE missions SET body='{}'")
        status, _, result = self.json("/v1/missions/" + self.mission["id"])
        self.assertEqual((status, result["error"]), (503, "STATE_UNAVAILABLE"))

    def test_g125_real_lock_is_state_busy_with_retry_after_and_nothing_is_written(self):
        holder = sqlite3.connect(self.store.path, isolation_level=None, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN EXCLUSIVE")
        before = time.monotonic()
        status, headers, result = self.json("/v1/missions/" + self.mission["id"])
        waited = time.monotonic() - before
        holder.execute("ROLLBACK")
        self.assertEqual((status, result["error"], headers.get("Retry-After")), (503, "STATE_BUSY", "2"))
        self.assertLess(waited, 6)
        self.assertEqual(self.json("/v1/missions/" + self.mission["id"])[0], 200)   # explicit retry served
        self.assertEqual(http_api.storage_busy(sqlite3.OperationalError("interrupted")), False)
        self.assertEqual(http_api.storage_busy(sqlite3.OperationalError("database disk image is malformed")), False)
        self.assertEqual(http_api.storage_busy(sqlite3.OperationalError("unable to open database file")), False)

    def test_g125_corrupt_or_missing_base_stays_state_unavailable(self):
        self.store.path.write_bytes(b"not a database" + self.store.path.read_bytes()[14:])
        status, headers, result = self.json("/v1/missions/" + self.mission["id"])
        self.assertEqual((status, result["error"], headers.get("Retry-After")), (503, "STATE_UNAVAILABLE", None))
        self.store.path.unlink()
        self.assertEqual(self.json("/v1/missions/" + self.mission["id"])[2]["error"], "STATE_UNAVAILABLE")
        self.assertFalse(self.store.path.exists())

    def test_recovery_marker_added_after_start_blocks_reads(self):
        (self.store.directory / "RECOVERY-REVIEW-ONLY").write_text("test")
        self.assertEqual(self.json("/v1/health")[0], 503)
        self.assertEqual(self.post()[0], 503)

    def test_pending_recovery_and_database_guard_refused(self):
        marker = self.store.directory / "review.pending.sqlite3"
        marker.write_bytes(b"")
        with self.assertRaises(ContractError):
            http_api.ReadOnlyStore(self.store.directory)
        marker.unlink()
        with self.store.connection() as db:
            db.execute("INSERT INTO sync_metadata VALUES ('recovery_mode', 'REVIEW_ONLY')")
        self.assertEqual(self.json("/v1/health")[0], 503)

    def test_missing_database_is_never_recreated(self):
        self.store.path.unlink()
        self.assertEqual(self.post()[0], 503)
        self.assertFalse(self.store.path.exists())
        absent = self.root / "not-created"
        with self.assertRaises(FileNotFoundError):
            http_api.ReadOnlyStore(absent)
        self.assertFalse(absent.exists())

    def test_no_migration_and_sql_write_forbidden(self):
        read = http_api.ReadOnlyStore(self.store.directory)
        before = self.store.path.read_bytes()
        with read.connection() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM missions")
        self.assertEqual(before, self.store.path.read_bytes())
        with self.store.connection() as db:
            db.execute("PRAGMA user_version=2")
        with self.assertRaises(ContractError):
            http_api.ReadOnlyStore(self.store.directory)

    def test_request_private_text_and_storage_errors_do_not_leak(self):
        self.runtime.create("PRIVATE-request-DO-NOT-EXPOSE")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            _, _, page = self.post()
            with patch.object(self.server.store, "health", side_effect=sqlite3.OperationalError("PRIVATE SQL")):
                status, _, result = self.json("/v1/health")
        self.assertEqual(status, 503)
        all_text = json.dumps([page, result]) + out.getvalue() + err.getvalue()
        self.assertNotIn("PRIVATE", all_text)
        self.assertNotIn(TOKEN, all_text)

    def test_response_limit_is_explicit_and_server_remains_usable(self):
        with patch.object(self.server.store, "health", return_value={"x": "x" * 262145}):
            status, _, result = self.json("/v1/health")
        self.assertEqual((status, result["error"]), (503, "RESPONSE_TOO_LARGE"))
        self.assertEqual(self.json("/v1/health")[0], 200)

    def test_assets_are_explicit_public_bounded_and_same_origin(self):
        web = self.root / "web"
        web.mkdir()
        for name in ("index.html", "app.js", "style.css"):
            (web / name).write_text("asset " + name)
        (web / "secret.txt").write_text("NEVER")
        with http_api.ReadServer(self.store.directory, TOKEN, port=0, web_root=web) as server:
            self.assertEqual(set(server.assets), {"/", "/app.js", "/style.css"})
            self.server.assets = server.assets
        status, headers, body = self.request("/", auth=False)
        self.assertEqual((status, body), (200, b"asset index.html"))
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        for url in ("/../secret.txt", "/%2e%2e/secret.txt", "/secret.txt"):
            self.assertEqual(self.request(url, auth=True)[0], 404)
        (web / "app.js").unlink()
        (web / "app.js").symlink_to(web / "secret.txt")
        with self.assertRaisesRegex(ValueError, "INVALID_WEB_ROOT"):
            http_api.ReadServer(self.store.directory, TOKEN, port=0, web_root=web)

    def test_complete_csp_is_present_on_assets_api_and_error_paths(self):
        expected = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.server.assets = {"/": b"<h1>fixture</h1>", "/app.js": b"// fixture", "/style.css": b"body{}"}
        cases = [("/", {}, 200), ("/app.js", {}, 200), ("/style.css", {}, 200),
                 ("/v1/health", {}, 200), ("/v1/health", {"auth": False}, 401),
                 ("/missing", {}, 404), ("/v1/health", {"method": "PUT"}, 405),
                 ("/v1/health", {"headers": {"Origin": "https://foreign.invalid"}}, 403),
                 ("/v1/missions", {"method": "POST", "body": b"{"}, 400)]
        for path, options, expected_status in cases:
            with self.subTest(path=path, options=options):
                status, headers, _ = self.request(path, **options)
                self.assertEqual(status, expected_status)
                self.assertEqual(headers.get("Content-Security-Policy"), expected)
                self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
                self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        with patch.object(self.server.store, "health", side_effect=sqlite3.OperationalError("private")):
            status, headers, _ = self.request("/v1/health")
        self.assertEqual(status, 503)
        self.assertEqual(headers.get("Content-Security-Policy"), expected)

    def test_unconfigured_static_route_never_exposes_cwd(self):
        self.assertEqual(self.request("/", auth=False)[0], 404)

    def test_cli_process_reads_existing_state_and_prints_no_token(self):
        token_file = self.root / "api-token"
        token_file.write_text(TOKEN + "\n")
        token_file.chmod(0o600)
        output = self.root / "cli-output"
        before = self.store.path.read_bytes()
        with output.open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "eidolon_core.http_api", "--state", str(self.store.directory),
                 "--token-file", str(token_file), "--port", "0"],
                stdout=log, stderr=log, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            try:
                deadline = time.monotonic() + 10
                found = None
                while time.monotonic() < deadline:
                    found = re.search(r"http://127\.0\.0\.1:(\d+)", output.read_text())
                    if found or process.poll() is not None:
                        break
                    time.sleep(.02)
                self.assertIsNotNone(found, "CLI did not start")
                conn = HTTPConnection("127.0.0.1", int(found[1]), timeout=5)
                try:
                    conn.request("GET", "/v1/health", headers={"Authorization": "Bearer " + TOKEN})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["mode"], "read_only")
                finally:
                    conn.close()
            finally:
                process.terminate()
                process.wait(timeout=5)
        self.assertNotIn(TOKEN, output.read_text())
        self.assertEqual(before, self.store.path.read_bytes())


class TokenFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "token"
        self.path.write_text(TOKEN + "\n")
        self.path.chmod(0o600)

    def test_private_valid_token(self):
        self.assertEqual(http_api.read_token(self.path), TOKEN)

    def test_public_or_symlink_token_refused(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "TOKEN_FILE_NOT_PRIVATE"):
            http_api.read_token(self.path)
        self.path.chmod(0o600)
        link = self.root / "link"
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            http_api.read_token(link)

    def test_empty_short_large_unicode_and_multiline_refused(self):
        for token in ("", "short", "x" * 129, "é" * 40, TOKEN + "\nextra", TOKEN + "\n\n"):
            self.path.write_text(token)
            with self.subTest(token=token[:6]), self.assertRaises(ValueError):
                http_api.read_token(self.path)

    def test_startup_error_is_sanitized_and_creates_no_state(self):
        target = self.root / "state"
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = http_api.main(["--state", str(target), "--token-file", str(self.path)])
        self.assertEqual(code, 2)
        self.assertIn("API_STARTUP_REFUSED", err.getvalue())
        self.assertNotIn(TOKEN, err.getvalue())
        self.assertNotIn(str(self.root), err.getvalue())
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
