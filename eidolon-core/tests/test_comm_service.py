# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_service.py
# Description : Service eidolon-comm : clé appairée, jeton de lecture refusé, hôte et origine, routes bornées (G151)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import base64
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.comm_contract import write_wav
from eidolon_core.comm_service import CommAPI, CommServer, build_engines, load_config
from eidolon_core.comm_stt import SimulatedSTT, SpeechToText
from eidolon_core.comm_tts import SimulatedTTS, TextToSpeech
from eidolon_core.comm_vision import SimulatedVision, Vision
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
from tests.test_comm_stt import tone
from tests.test_comm_vision import png

SRC = str(Path(__file__).resolve().parents[1] / "src")
READ = "r" * 43
ORIGIN = "http://127.0.0.1:8765"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        runtime = synthetic_runtime(Store(self.state))
        ConversationStore(runtime.store, create=True)
        credentials = ClientCredentials(runtime.store, create=True)
        self.key = credentials.pair(client_id="pc-toytoy", actor="toytoy")["token"]
        self.api = CommAPI(credentials, stt=SpeechToText(SimulatedSTT()), tts=TextToSpeech(SimulatedTTS()),
                           vision=Vision(SimulatedVision()), read_token=READ, allowed_hosts={"127.0.0.1:8766"},
                           allowed_origin=ORIGIN)

    def call(self, method, path, body=b"", token=None, origin=None, host="127.0.0.1:8766"):
        headers = {"Host": [host]}
        if token is not False:
            headers["Authorization"] = ["Bearer " + (token or self.key)]
        if origin:
            headers["Origin"] = [origin]
        return self.api.handle(method, path, headers, body)


class AccessTests(Base):
    def test_paired_key_required_and_read_token_refused(self):
        self.assertEqual(self.call("GET", "/v1/comm/status")[0], 200)
        self.assertEqual(self.call("GET", "/v1/comm/status", token=False)[1]["error"], "UNAUTHORIZED")
        self.assertEqual(self.call("GET", "/v1/comm/status", token="ecc_" + "x" * 43)[1]["error"], "UNAUTHORIZED")
        self.assertEqual(self.call("GET", "/v1/comm/status", token=READ)[1]["error"], "READ_TOKEN_NOT_ALLOWED")

    def test_host_and_origin(self):
        self.assertEqual(self.call("GET", "/v1/comm/status", host="evil.example:8766")[1]["error"], "HOST_REFUSED")
        status, body, extra = self.call("GET", "/v1/comm/status", origin=ORIGIN)
        self.assertEqual((status, extra["Access-Control-Allow-Origin"]), (200, ORIGIN))
        self.assertEqual(self.call("GET", "/v1/comm/status", origin="http://evil.example")[1]["error"], "ORIGIN_REFUSED")
        status, body, extra = self.call("OPTIONS", "/v1/comm/stt", token=False, origin=ORIGIN)
        self.assertEqual((status, body, extra["Access-Control-Allow-Headers"]), (204, None, "Authorization, Content-Type"))

    def test_status_says_capture_off_and_unconfigured_engines_unavailable(self):
        body = self.call("GET", "/v1/comm/status")[1]
        self.assertEqual((body["capture_default"], body["stt"]["engine"], body["authorizes_execution"]),
                         ("off", "simulated", False))
        self.api.vision = None
        self.assertEqual(self.call("GET", "/v1/comm/status")[1]["vision"], {"state": "unavailable"})
        self.assertEqual(self.call("POST", "/v1/comm/vision/describe", png(8, 8))[1]["error"], "ENGINE_UNAVAILABLE")


class RouteTests(Base):
    def test_transcription_is_text_only(self):
        status, body, _ = self.call("POST", "/v1/comm/stt", write_wav(tone(1)))
        self.assertEqual((status, body["unverified"], body["authorizes_execution"]), (200, True, False))
        self.assertEqual(self.call("POST", "/v1/comm/stt", b"pas un wav")[1]["error"], "AUDIO_FORMAT_UNSUPPORTED")
        self.assertEqual(self.call("DELETE", "/v1/comm/stt")[1], {"stopped": False})

    def test_synthesis_chunk(self):
        status, body, _ = self.call("POST", "/v1/comm/tts", json.dumps({"text": "Bonjour. Ça va ?", "index": 1}).encode())
        self.assertEqual((status, body["index"], body["chunks"], body["last"]), (200, 1, 2, True))
        self.assertTrue(base64.b64decode(body["wav_base64"]).startswith(b"RIFF"))
        self.assertEqual(self.call("POST", "/v1/comm/tts", json.dumps({"text": "x", "shell": "rm"}).encode())[1]["error"],
                         "INVALID_REQUEST")
        self.assertEqual(self.call("POST", "/v1/comm/tts", b"{")[1]["error"], "INVALID_REQUEST")

    def test_vision_and_unknown_routes(self):
        body = self.call("POST", "/v1/comm/vision/describe?purpose=scene", png(8, 8))[1]
        self.assertEqual((body["purpose"], body["identity"]), ("scene", None))
        self.assertEqual(self.call("POST", "/v1/comm/vision/describe?purpose=identify", png(8, 8))[1]["error"],
                         "INVALID_REQUEST")
        self.assertEqual(self.call("GET", "/v1/comm/stt")[0], 405)
        self.assertEqual(self.call("GET", "/v1/comm/record")[0], 404)
        self.assertEqual(self.call("GET", "/v1/conversations/turn")[0], 404)


class ServerTests(Base):
    def test_real_loopback_server(self):
        self.api.allowed_hosts = None
        server = CommServer(self.api, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_port
        try:
            def request(method, path, body=None, headers=None):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                sent = {"Host": f"127.0.0.1:{port}", "Authorization": "Bearer " + self.key, **(headers or {})}
                conn.request(method, path, body=body, headers=sent)
                response = conn.getresponse()
                raw = response.read()
                conn.close()
                return response.status, (json.loads(raw) if raw else None), response
            status, body, response = request("POST", "/v1/comm/stt", write_wav(tone(1)), {"Content-Type": "audio/wav"})
            self.assertEqual((status, body["engine"]), (200, "simulated"))
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.putrequest("POST", "/v1/comm/stt"); conn.putheader("Host", f"127.0.0.1:{port}"); conn.endheaders()
            self.assertEqual(conn.getresponse().status, 411)
            conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)      # refused before reading
            conn.putrequest("POST", "/v1/comm/stt"); conn.putheader("Host", f"127.0.0.1:{port}")
            conn.putheader("Content-Length", str(3 * 1024 * 1024)); conn.endheaders()
            self.assertEqual(conn.getresponse().status, 413)
            conn.close()
        finally:
            server.shutdown(); server.server_close()
        self.assertEqual(server.server_address[0], "127.0.0.1")


class ConfigTests(Base):
    def write(self, value, mode=0o600):
        path = Path(self.tmp.name) / "comm.json"
        path.write_text(json.dumps(value)); os.chmod(path, mode)
        return str(path)

    def test_private_config_and_engines(self):
        config = {"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"}, "tts": None,
                  "allowed_origin": ORIGIN}
        stt, tts, vision = build_engines(load_config(self.write(config)))
        self.assertEqual((stt.engine.engine, tts, vision), ("simulated", None, None))
        with self.assertRaises(ValueError):
            load_config(self.write(config, 0o644))
        with self.assertRaises(ValueError):
            load_config(self.write({**config, "allowed_origin": "http://evil.example"}))
        with self.assertRaises(ValueError):
            load_config(self.write({**config, "record_everything": True}))

    def test_check_command(self):
        path = self.write({"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"},
                           "tts": {"kind": "simulated"}, "vision": {"kind": "simulated"}})
        done = subprocess.run([sys.executable, "-m", "eidolon_core.comm_service", "--state", str(self.state),
                               "--config", path, "--check"], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["capture_default"], "off")
        bad = self.write({"schema": "eidolon-comm-config/1", "stt": {"kind": "faster-whisper", "model_dir": "small"}})
        done = subprocess.run([sys.executable, "-m", "eidolon_core.comm_service", "--state", str(self.state),
                               "--config", bad, "--check"], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("ENGINE_UNAVAILABLE", done.stderr)


if __name__ == "__main__":
    unittest.main()
