# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_relay.py
# Description : Relais de même origine Core → eidolon-comm : clé appairée vérifiée par le service, CSP inchangée (C147)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import base64
import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import unittest

from eidolon_core import http_api
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.comm_contract import write_wav
from eidolon_core.comm_service import CommAPI, CommServer
from eidolon_core.comm_stt import SimulatedSTT, SpeechToText
from eidolon_core.comm_tts import SimulatedTTS, TextToSpeech
from eidolon_core.comm_vision import SimulatedVision, Vision
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.store import Store
from tests.test_comm_stt import tone


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        store = Store(self.state)
        ConversationStore(store, create=True)
        credentials = ClientCredentials(store, create=True)
        self.key = credentials.pair(client_id="pc", actor="toytoy")["token"]
        self.read = secrets.token_urlsafe(32)
        self.comm = CommServer(CommAPI(credentials, stt=SpeechToText(SimulatedSTT()), tts=TextToSpeech(SimulatedTTS()),
                                       vision=Vision(SimulatedVision()), read_token=self.read), port=0)
        self.servers = [self.comm]
        threading.Thread(target=self.comm.serve_forever, daemon=True).start()
        self.core = self.start(self.comm.server_port)

    def tearDown(self):
        for server in self.servers:
            server.shutdown(); server.server_close()

    def start(self, comm_port):
        server = http_api.ReadServer(self.state, self.read, port=0, comm_port=comm_port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        return server

    def request(self, method, path, body=b"", token="key", ctype="application/json", server=None, origin=None):
        server = server or self.core
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=20)
        headers = {"Host": f"127.0.0.1:{server.server_port}", "Content-Type": ctype}
        if token:
            headers["Authorization"] = "Bearer " + (self.key if token == "key" else token)
        if origin:
            headers["Origin"] = origin
        conn.request(method, path, body=body or None, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw), response

    def test_paired_key_through_core_same_origin(self):
        status, body, response = self.request("POST", "/v1/comm/stt", write_wav(tone(1)), ctype="audio/wav",
                                              origin=f"http://127.0.0.1:{self.core.server_port}")
        self.assertEqual((status, body["engine"], body["authorizes_execution"]), (200, "simulated", False))
        self.assertIn("connect-src 'self'", response.getheader("Content-Security-Policy"))   # CSP unchanged

    def test_read_token_and_missing_key_refused_by_the_service(self):
        self.assertEqual(self.request("GET", "/v1/comm/status", token=self.read)[1]["error"], "READ_TOKEN_NOT_ALLOWED")
        self.assertEqual(self.request("GET", "/v1/comm/status", token=None)[1]["error"], "UNAUTHORIZED")

    def test_core_checks_still_apply(self):
        status, body, _ = self.request("GET", "/v1/comm/status", origin="http://evil.example")
        self.assertEqual((status, body["error"]), (403, "ORIGIN_REFUSED"))
        self.assertEqual(self.request("PUT", "/v1/comm/status")[1]["error"], "METHOD_NOT_ALLOWED")

    def test_a_spoken_sentence_larger_than_core_responses_passes(self):
        text = "Mot " * 70 + "fin."
        status, body, _ = self.request("POST", "/v1/comm/tts", json.dumps({"text": text}).encode())
        self.assertEqual(status, 200)
        self.assertGreater(len(body["wav_base64"]), http_api.MAX_RESPONSE)
        self.assertTrue(base64.b64decode(body["wav_base64"]).startswith(b"RIFF"))

    def test_service_down_and_relay_off(self):
        self.comm.shutdown(); self.comm.server_close(); self.servers.remove(self.comm)
        self.assertEqual(self.request("GET", "/v1/comm/status")[1]["error"], "COMM_UNAVAILABLE")
        plain = self.start(None)                                     # without --comm-port: no relay at all
        status, body, _ = self.request("GET", "/v1/comm/status", server=plain)
        self.assertEqual(body["error"], "UNAUTHORIZED")              # the read API, not the voice service
        with self.assertRaises(ValueError):
            http_api.ReadServer(self.state, self.read, port=0, comm_port=80)


if __name__ == "__main__":
    unittest.main()
