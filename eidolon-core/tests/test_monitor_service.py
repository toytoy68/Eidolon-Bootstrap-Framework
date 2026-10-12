# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_monitor_service.py
# Description : Adaptateur eidolon-monitor : clé appairée, socket DARME en lecture seule, fraîcheur, relais Core (G157)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from collections import namedtuple
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import unittest

from eidolon_core import http_api
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.darme_service import Collector
from eidolon_core.darme_store import DarmeJournal
from eidolon_core.monitor_service import MonitorAPI, MonitorServer, load_config, read_darme, summarize
from eidolon_core.store import Store

Disk = namedtuple("Disk", "total used free")


def darme_status(**changes):
    value = {"service_schema": "eidolon-darme-service/1", "schema": "eidolon-darme-status/1", "badge": "grey",
             "visibility": "partial", "sources": {"eidolon-core-api.service": True, "security-telemetry": False},
             "health_ttl_seconds": 60, "unacknowledged_alerts": 0, "intervention": False,
             "ingestion_paused": False, "scope": "local_service_availability_and_journal_disk",
             "security_telemetry_installed": False, "advisor": "fixed", "authorizes_execution": False,
             "enforcement_enabled": False, "generated_at": datetime.now(timezone.utc).isoformat()}
    value.update(changes)
    return value


class FakeDarme:
    """Unix socket speaking the DARME protocol; records every request it receives."""

    def __init__(self, path, reply):
        self.path, self.reply, self.requests = str(path), reply, []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(8)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            with connection:
                self.requests.append(connection.recv(65))
                reply = self.reply() if callable(self.reply) else self.reply
                if reply is not None:
                    try:
                        connection.sendall(reply)
                    except OSError:                       # the reader already left (refused peer)
                        pass

    def close(self):
        self.server.close()
        os.unlink(self.path)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.state = root / "state"
        store = Store(self.state)
        ConversationStore(store, create=True)
        self.credentials = ClientCredentials(store, create=True)
        self.key = self.credentials.pair(client_id="pc", actor="toytoy")["token"]
        self.read = secrets.token_urlsafe(32)
        self.reply = json.dumps(darme_status()).encode() + b"\n"
        self.darme = FakeDarme(root / "status.sock", lambda: self.reply)
        self.addCleanup(self.darme.close)
        self.machines = [{"id": "core", "label": "Core", "socket": self.darme.path},
                         {"id": "memory", "label": "Memory", "socket": str(root / "absent.sock")}]

    def api(self, **options):
        return MonitorAPI(self.credentials, self.machines, not_covered=["VM101 GPU"], read_token=self.read,
                          allowed_hosts={"127.0.0.1:8768"}, allowed_origin="http://127.0.0.1:8767",
                          cache_seconds=0, **options)

    def get(self, api, token="key", path="/v1/monitor/status", method="GET", origin=None):
        headers = {"Host": ["127.0.0.1:8768"]}
        if token:
            headers["Authorization"] = ["Bearer " + (self.key if token == "key" else token)]
        if origin:
            headers["Origin"] = [origin]
        return api.handle(method, path, headers)

    def test_status_grey_is_never_secure_and_missing_machine_is_explicit(self):
        status, body, _ = self.get(self.api())
        self.assertEqual(status, 200)
        core, memory = body["machines"]
        self.assertEqual((core["state"], core["darme"]["badge"], core["darme"]["secure_claim"]), ("ok", "grey", False))
        self.assertEqual(core["darme"]["scope"], "local_service_availability_and_journal_disk")
        self.assertIsNone(core["machine"])                  # no machine field: nothing invented
        self.assertEqual((memory["state"], memory["error"], memory["darme"]), ("unavailable", "UNAVAILABLE", None))
        self.assertEqual((body["not_covered"], body["gpu_metrics"], body["authorizes_execution"]),
                         (["VM101 GPU"], None, False))
        self.assertEqual(self.darme.requests, [b"STATUS\n"])   # the only bytes ever sent

    def test_refusals_read_token_revoked_unknown_query_method_origin_host(self):
        api = self.api()
        self.assertEqual(self.get(api, token=self.read)[1]["error"], "READ_TOKEN_NOT_ALLOWED")
        self.assertEqual(self.get(api, token=None)[1]["error"], "UNAUTHORIZED")
        self.assertEqual(self.get(api, token="forged")[1]["error"], "UNAUTHORIZED")
        self.assertEqual(self.get(api, path="/v1/monitor/status?socket=/etc")[1]["error"], "INVALID_REQUEST")
        self.assertEqual(self.get(api, method="POST")[0], 405)
        self.assertEqual(self.get(api, path="/v1/monitor/darme")[0], 404)
        self.assertEqual(self.get(api, origin="http://evil.example")[1]["error"], "ORIGIN_REFUSED")
        status, _, extra = self.get(api, origin="http://127.0.0.1:8767")
        self.assertEqual((status, extra["Access-Control-Allow-Origin"]), (200, "http://127.0.0.1:8767"))
        self.assertEqual(api.handle("GET", "/v1/monitor/status", {"Host": ["evil:1"]})[1]["error"], "HOST_REFUSED")
        self.credentials.revoke("pc")
        self.assertEqual(self.get(api)[1]["error"], "UNAUTHORIZED")
        self.assertEqual(len(self.darme.requests), 1)        # refused requests never reach DARME

    def test_stale_skewed_and_invalid_replies(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        self.reply = json.dumps(darme_status(generated_at=old)).encode() + b"\n"
        core = self.get(self.api())[1]["machines"][0]
        self.assertEqual((core["state"], core["darme"]["age_seconds"] >= 299), ("stale", True))
        future = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        self.reply = json.dumps(darme_status(generated_at=future)).encode() + b"\n"
        self.assertEqual(self.get(self.api())[1]["machines"][0]["error"], "CLOCK_SKEW")
        for bad in (darme_status(badge="green"), darme_status(authorizes_execution=True),
                    darme_status(service_schema="other"), darme_status(sources={"a": "yes"}),
                    darme_status(generated_at="2026-10-12T10:00:00")):
            self.reply = json.dumps(bad).encode() + b"\n"
            core = self.get(self.api())[1]["machines"][0]
            self.assertEqual((core["state"], core["darme"]), ("invalid", None), bad)
        for raw in (b"not json\n", b"[1]\n", b'{"error":"read-only protocol"}\n'):
            self.reply = raw
            self.assertEqual(self.get(self.api())[1]["machines"][0]["state"], "invalid")

    def test_no_raw_event_or_unknown_field_is_relayed(self):
        self.reply = json.dumps(darme_status(events=[{"subject": "/home/toytoy/secret"}], token="t0k3n",
                                             badge="red", unacknowledged_alerts=2)).encode() + b"\n"
        body = json.dumps(self.get(self.api())[1])
        self.assertNotIn("secret", body); self.assertNotIn("t0k3n", body); self.assertNotIn("events", body)
        self.assertIn('"unacknowledged_alerts": 2', body)

    def test_machine_field_follows_the_published_contract(self):
        now = datetime.now(timezone.utc)
        machine = {"schema": "eidolon-machine/1", "sampled_at": now.isoformat(), "cpu_count": 8, "cpu_percent": 12.5,
                   "load_1_5_15": [0.4, 0.3, 0.2], "memory": {"total_bytes": 8 << 30, "available_bytes": 6 << 30,
                   "used_bytes": 2 << 30}, "swap": {"total_bytes": 0, "free_bytes": 0, "used_bytes": 0},
                   "disk": {"scope": "journal_filesystem", "total_bytes": 100, "free_bytes": 60, "used_bytes": 40},
                   "gpu": None, "errors": [], "extra": "/home/toytoy/secret"}
        darme, view = summarize(darme_status(machine=machine))[1:3]
        self.assertEqual((view["cpu_percent"], view["load_1_5_15"], view["memory"]["used_bytes"], view["gpu"]),
                         (12.5, [0.4, 0.3, 0.2], 2 << 30, None))
        self.assertEqual((view["stale"], view["disk"]["scope"]), (False, "journal_filesystem"))
        self.assertNotIn("extra", json.dumps(view)); self.assertNotIn("machine_error", darme)
        first = dict(machine, cpu_percent=None, memory=None, errors=["memory_unavailable"])
        self.assertEqual(summarize(darme_status(machine=first))[2]["errors"], ["memory_unavailable"])
        old = dict(machine, sampled_at=(now - timedelta(seconds=120)).isoformat())
        self.assertTrue(summarize(darme_status(machine=old))[2]["stale"])
        future = dict(machine, sampled_at=(now + timedelta(seconds=60)).isoformat())
        self.assertEqual(summarize(darme_status(machine=future))[1]["machine_error"], "MACHINE_CLOCK_SKEW")
        for bad in (dict(machine, schema="x"), dict(machine, cpu_percent=150), dict(machine, load_1_5_15=[1, 2]),
                    dict(machine, memory={"total_bytes": 1, "available_bytes": 2, "used_bytes": 0}),
                    dict(machine, disk=dict(machine["disk"], scope="/mnt/nas")), dict(machine, errors=["Bad Code!"]),
                    dict(machine, cpu_count=0), dict(machine, sampled_at="2026-10-12T10:00:00")):
            state, darme, view, _ = summarize(darme_status(machine=bad))
            self.assertEqual((state, view, darme["machine_error"]), ("ok", None, "MACHINE_INVALID"), bad)

    def test_socket_peer_account_is_checked(self):
        self.assertEqual(read_darme(self.darme.path, peer_uid=os.getuid())[1], None)
        self.assertEqual(read_darme(self.darme.path, peer_uid=os.getuid() + 1), (None, "PEER_REFUSED"))

    def test_bounded_reply_and_silent_socket(self):
        self.reply = b"{" + b" " * (70 * 1024)
        self.assertEqual(read_darme(self.darme.path)[1], "REPLY_TOO_LARGE")
        self.reply = None                                     # accepts, never answers
        self.assertEqual(read_darme(self.darme.path, timeout=0.3)[1], "INVALID_REPLY")

    def test_short_cache_shared_by_tabs(self):
        api = MonitorAPI(self.credentials, self.machines[:1], read_token=self.read, allowed_hosts={"127.0.0.1:8768"})
        for _ in range(5):
            self.get(api)
        self.assertEqual(len(self.darme.requests), 1)

    def test_real_darme_collector_status_is_understood(self):
        journal = DarmeJournal(Path(self.tmp.name) / "journal.sqlite"); self.addCleanup(journal.close)
        collector = Collector(journal, ["eidolon-core-api.service"], self.tmp.name, lambda _: True,
                              lambda _: Disk(10**10, 10**9, 9 * 10**9))
        collector.sample()
        state, darme, _, error = summarize(json.loads(json.dumps(collector.status())))
        self.assertEqual((state, error, darme["badge"], darme["visibility"]), ("ok", None, "grey", "partial"))
        self.assertFalse(darme["security_telemetry_installed"])

    def test_config_private_and_strict(self):
        path = Path(self.tmp.name) / "monitor.json"
        good = {"schema": "eidolon-monitor-config/1", "machines": [{"id": "core", "label": "Core",
                "socket": "/run/eidolon-darme/status.sock"}], "not_covered": ["VM101 GPU"],
                "allowed_origin": "http://127.0.0.1:8767"}
        path.write_text(json.dumps(good)); os.chmod(path, 0o600)
        self.assertEqual(load_config(path)["machines"][0]["id"], "core")
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(ValueError, "NOT_PRIVATE"):
            load_config(path)
        os.chmod(path, 0o600)
        for bad in ({**good, "command": "x"}, {**good, "machines": [{"id": "core", "label": "C", "socket": "rel"}]},
                    {**good, "allowed_origin": "http://evil.example"}, {**good, "machines": []}):
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                load_config(path)


class CoreRelayTests(unittest.TestCase):
    """The page reaches the adapter on its own origin (CSP connect-src 'self'), like /v1/comm/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        store = Store(self.state)
        ConversationStore(store, create=True)
        credentials = ClientCredentials(store, create=True)
        self.key = credentials.pair(client_id="pc", actor="toytoy")["token"]
        self.read = secrets.token_urlsafe(32)
        self.darme = FakeDarme(Path(self.tmp.name) / "s.sock", json.dumps(darme_status()).encode() + b"\n")
        self.addCleanup(self.darme.close)
        self.monitor = MonitorServer(MonitorAPI(credentials, [{"id": "core", "label": "Core",
                                                               "socket": self.darme.path}], read_token=self.read),
                                     port=0)
        self.core = http_api.ReadServer(self.state, self.read, port=0, monitor_port=self.monitor.server_port)
        for server in (self.monitor, self.core):
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)

    def request(self, method, token="key", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.core.server_port, timeout=10)
        headers = {"Host": f"127.0.0.1:{self.core.server_port}",
                   "Origin": f"http://127.0.0.1:{self.core.server_port}"}
        if token:
            headers["Authorization"] = "Bearer " + (self.key if token == "key" else token)
        connection.request(method, "/v1/monitor/status", body=body, headers=headers)
        response = connection.getresponse()
        value = json.loads(response.read())
        connection.close()
        return response.status, value, response

    def test_relayed_with_paired_key_only(self):
        status, body, response = self.request("GET")
        self.assertEqual((status, body["machines"][0]["darme"]["badge"]), (200, "grey"))
        self.assertIn("connect-src 'self'", response.getheader("Content-Security-Policy"))
        self.assertEqual(self.request("GET", token=self.read)[1]["error"], "READ_TOKEN_NOT_ALLOWED")
        self.assertEqual(self.request("POST")[1]["error"], "METHOD_NOT_ALLOWED")
        self.assertEqual(self.request("GET", body=b"x")[0], 413)

    def test_adapter_down_and_port_checks(self):
        self.monitor.shutdown(); self.monitor.server_close()
        self.assertEqual(self.request("GET")[1]["error"], "MONITOR_UNAVAILABLE")
        with self.assertRaises(ValueError):
            http_api.ReadServer(self.state, self.read, port=0, comm_port=8766, monitor_port=8766)


if __name__ == "__main__":
    unittest.main()
