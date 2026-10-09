# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_http_conversations.py
# Description : Montage des conversations sur le serveur de lecture : désactivé par défaut, jetons distincts (C-TASK-G088)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest

from eidolon_core import http_api
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.store import Store


class MountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        store = Store(self.state)
        ConversationStore(store, create=True)
        self.key = ClientCredentials(store, create=True).pair(client_id="pc", actor="toytoy")["token"]
        self.read = secrets.token_urlsafe(32)
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.tmp.cleanup()

    def start(self, conversations):
        server = http_api.ReadServer(self.state, self.read, port=0, conversations=conversations)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        return server

    def request(self, server, method, path, body=None, token=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        sent = {"Host": f"127.0.0.1:{server.server_port}"}
        if token:
            sent["Authorization"] = "Bearer " + token
        if body is not None:
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        raw = body if isinstance(body, bytes) or body is None else json.dumps(body, ensure_ascii=False).encode()
        connection.request(method, path, body=raw, headers=sent)
        response = connection.getresponse()
        value = json.loads(response.read() or b"null")
        connection.close()
        return response.status, value

    def simulated(self):
        return SimulatedDialogueModel(demo_catalog())

    def test_off_by_default_the_conversation_key_is_just_an_unknown_token(self):
        server = self.start(None)
        status, value = self.request(server, "POST", "/v1/conversations/open", {"client_key": "k"}, self.key)
        self.assertEqual((status, value["error"]), (401, "UNAUTHORIZED"))
        self.assertIsNone(server.conversation_api)

    def test_enabled_routes_use_distinct_credentials_both_ways(self):
        server = self.start(self.simulated)
        status, opened = self.request(server, "POST", "/v1/conversations/open", {"client_key": "k"}, self.key)
        self.assertEqual((status, opened["actor"]), (200, "toytoy"))
        status, turn = self.request(server, "POST", "/v1/conversations/turn",
                                    {"conversation_id": opened["conversation_id"], "client_turn_key": "t1",
                                     "text": "Diagnostique le nas."}, self.key)
        self.assertEqual((status, turn["reply"]["kind"]), (200, "PROPOSAL"))
        # The read token never writes; the conversation key never reads.
        self.assertEqual(self.request(server, "POST", "/v1/conversations/open", {"client_key": "k"}, self.read),
                         (403, {"protocol": "eidolon-conversation-api/1", "error": "READ_TOKEN_NOT_ALLOWED",
                                "authorizes_execution": False}))
        self.assertEqual(self.request(server, "GET", "/v1/health", token=self.key)[0], 401)
        self.assertEqual(self.request(server, "GET", "/v1/health", token=self.read)[0], 200)

    def test_existing_transport_rules_still_apply_before_the_conversation_branch(self):
        server = self.start(self.simulated)
        cases = ((("POST", "/v1/conversations/open", {"client_key": "k"}), {"Host": "evil.example"}, 403, "HOST_REFUSED"),
                 (("POST", "/v1/conversations/open", {"client_key": "k"}), {"Origin": "http://evil.example"}, 403,
                  "ORIGIN_REFUSED"),
                 (("POST", "/v1/conversations/open", {"client_key": "k"}), {"Transfer-Encoding": "chunked"}, 400,
                  "UNSUPPORTED_TRANSFER"))
        for (method, path, body), headers, status, code in cases:
            with self.subTest(code=code):
                self.assertEqual(self.request(server, method, path, body, self.key, headers)[1]["error"], code)
                self.assertEqual(self.request(server, method, path, body, self.key, headers)[0], status)

    def test_body_limits_stay_per_route(self):
        server = self.start(self.simulated)
        big = {"conversation_id": "c-" + "0" * 32, "client_turn_key": "t", "text": "é" * 8000}   # ~16 KB
        self.assertEqual(self.request(server, "POST", "/v1/conversations/turn", big, self.key)[1]["error"],
                         "CONVERSATION_UNKNOWN")                                   # accepted size, then 404
        self.assertEqual(self.request(server, "POST", "/v1/missions", {"limit": 1, "pad": "x" * 9000}, self.read)[0], 413)
        escaped = json.dumps({**big, "text": "\U0001F600" * 8000}).encode()               # worst case: 96 KB
        self.assertEqual(self.request(server, "POST", "/v1/conversations/turn", escaped, self.key)[1]["error"],
                         "CONVERSATION_UNKNOWN")
        self.assertEqual(self.request(server, "POST", "/v1/conversations/turn",
                                      {**big, "text": "é" * 60000}, self.key)[0], 413)

    def test_both_limits_are_the_same_constant(self):
        from eidolon_core import conversation_api
        self.assertEqual(http_api.CONVERSATION_MAX_BODY, conversation_api.MAX_BODY)


if __name__ == "__main__":
    unittest.main()


class ShutdownTests(MountTests):
    def test_g088_r2_server_close_does_not_wait_for_a_blocked_model(self):
        release, started = threading.Event(), threading.Event()

        class Blocked(SimulatedDialogueModel):
            def reply(self, text, history, memory):
                started.set()
                release.wait(20)
                return super().reply(text, history, memory)

        server = http_api.ReadServer(self.state, self.read, port=0, conversations=lambda: Blocked(demo_catalog()))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        status, opened = self.request(server, "POST", "/v1/conversations/open", {"client_key": "k"}, self.key)
        threading.Thread(target=lambda: self.request(server, "POST", "/v1/conversations/turn",
                                                     {"conversation_id": opened["conversation_id"],
                                                      "client_turn_key": "t", "text": "Diagnostique le nas."},
                                                     self.key), daemon=True).start()
        self.assertTrue(started.wait(5))
        began = time.monotonic()
        server.shutdown()
        server.server_close()
        self.assertLess(time.monotonic() - began, 2)
        release.set()
        page = ConversationStore(Store(self.state)).page(opened["conversation_id"])
        self.assertIsNone(page["items"][0]["reply"])          # nothing recorded after shutdown began
