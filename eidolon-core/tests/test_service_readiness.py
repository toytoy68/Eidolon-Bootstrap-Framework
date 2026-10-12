# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_service_readiness.py
# Description : Disponibilité réelle (Type=notify), révocation pendant une requête, reprise après arrêt (G167)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.comm_contract import write_wav
from eidolon_core.comm_credentials import ReadOnlyClientCredentials, ReadOnlyCredentialStore
from eidolon_core.comm_service import CommAPI
from eidolon_core.comm_stt import SimulatedSTT, SpeechToText
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.sd_notify import notify
from eidolon_core.store import Store
from tests.test_comm_stt import tone

SRC = str(Path(__file__).resolve().parents[1] / "src")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class NotifyTests(unittest.TestCase):
    def test_ready_datagram_then_variable_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "notify")
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
                receiver.bind(path)
                os.environ["NOTIFY_SOCKET"] = path
                self.assertTrue(notify())
                self.assertEqual(receiver.recv(64), b"READY=1")
        self.assertNotIn("NOTIFY_SOCKET", os.environ)
        self.assertFalse(notify())                        # outside systemd: nothing, no error
        os.environ["NOTIFY_SOCKET"] = "relative/path"
        self.assertFalse(notify())

    def test_services_signal_ready_only_when_the_port_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            store = Store(tmp / "state")
            ConversationStore(store, create=True)
            ClientCredentials(store, create=True)
            read = tmp / "read-token"; read.write_text(secrets.token_urlsafe(32) + "\n"); os.chmod(read, 0o600)
            comm = tmp / "comm.json"
            comm.write_text(json.dumps({"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"}}))
            monitor = tmp / "monitor.json"
            monitor.write_text(json.dumps({"schema": "eidolon-monitor-config/1",
                                           "machines": [{"id": "core", "label": "Core", "socket": str(tmp / "absent.sock")}]}))
            os.chmod(comm, 0o600); os.chmod(monitor, 0o600)
            for module, config in (("eidolon_core.comm_service", comm), ("eidolon_core.monitor_service", monitor)):
                with self.subTest(module), socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
                    receiver.bind(str(tmp / (module + ".notify"))); receiver.settimeout(20)
                    port = free_port()
                    process = subprocess.Popen(
                        [sys.executable, "-m", module, "--state", str(tmp / "state"), "--config", str(config),
                         "--port", str(port), "--read-token-file", str(read)],
                        env={"PYTHONPATH": SRC, "PYTHONDONTWRITEBYTECODE": "1",
                             "NOTIFY_SOCKET": str(tmp / (module + ".notify"))},
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        self.assertEqual(receiver.recv(64), b"READY=1")
                        with socket.create_connection(("127.0.0.1", port), timeout=1):   # open at once
                            pass
                    finally:
                        process.terminate(); process.wait(10)


class RevocationDuringRequestTests(unittest.TestCase):
    """A key revoked while a transcription runs gets no transcript (read-only view, as deployed)."""

    def test_result_discarded_when_key_revoked_meanwhile(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state")
            ConversationStore(store, create=True)
            writer = ClientCredentials(store, create=True)
            key = writer.pair(client_id="pc", actor="toytoy")["token"]
            other = writer.pair(client_id="tablet", actor="toytoy")["token"]
            started, release = threading.Event(), threading.Event()

            class Slow(SimulatedSTT):
                def transcribe(self, pcm, duration, cancel, deadline):
                    started.set(); release.wait(10)
                    return super().transcribe(pcm, duration, cancel, deadline)
            reader = ReadOnlyClientCredentials(ReadOnlyCredentialStore(Path(tmp) / "state"))
            api = CommAPI(reader, stt=SpeechToText(Slow()))
            outcome = {}

            def call(token, name):
                outcome[name] = api.handle("POST", "/v1/comm/stt", {"Authorization": ["Bearer " + token]},
                                           write_wav(tone(1)))
            first = threading.Thread(target=call, args=(key, "revoked")); first.start()
            self.assertTrue(started.wait(10))
            writer.revoke("pc")
            release.set(); first.join(10)
            status, body, _ = outcome["revoked"]
            self.assertEqual((status, body["error"]), (401, "UNAUTHORIZED"))
            self.assertNotIn("text", body)
            call(other, "kept")                              # another client is not affected
            self.assertEqual(outcome["kept"][0], 200)


if __name__ == "__main__":
    unittest.main()
