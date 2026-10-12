# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_comm.py
# Description : Recette conteneur du service eidolon-comm : vrai processus, adaptateurs Piper/Ollama sur moteurs factices (G151)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/validation/2026-10-12/claude-g146-g151/recipe_comm.py

CONTAINER ONLY. No microphone, camera, real Whisper/Piper voice or vision model: STT is the simulator,
Piper and Ollama are local FAKES reached through the REAL adapters. Measures here say nothing about the
VM or Windows. Prints one JSON report; exit 0 only if every check passed."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "src"))
sys.path.insert(0, str(HERE.parents[3]))
from eidolon_core.client_credentials import ClientCredentials          # noqa: E402
from eidolon_core.comm_contract import write_wav                       # noqa: E402
from eidolon_core.conversation_store import ConversationStore          # noqa: E402
from eidolon_core.diagnostics import synthetic_runtime                 # noqa: E402
from eidolon_core.store import Store                                   # noqa: E402
from tests.test_comm_stt import tone                                    # noqa: E402
from tests.test_comm_vision import jpeg                                 # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:200]})


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def listing(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-comm-") as tmp:
        tmp = Path(tmp)
        runtime = synthetic_runtime(Store(tmp / "state"))
        ConversationStore(runtime.store, create=True)
        key = ClientCredentials(runtime.store, create=True).pair(client_id="pc-toytoy", actor="toytoy")["token"]
        read = "r" * 43
        (tmp / "read-token").write_text(read + "\n"); os.chmod(tmp / "read-token", 0o600)
        voices = tmp / "voices"; voices.mkdir()
        (voices / "fr_FR-siwis-medium.onnx").write_bytes(b"")
        (voices / "fr_FR-siwis-medium.onnx.json").write_text(json.dumps({"audio": {"sample_rate": 22050}, "language": {"code": "fr_FR"}}))
        piper = tmp / "piper"
        piper.write_text(f"#!{sys.executable}\nimport sys\nt=sys.stdin.read()\nsys.stdout.buffer.write(b'\\x10\\x00'*len(t)*200)\n")
        os.chmod(piper, 0o755)

        class Ollama(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                raw = json.dumps({"message": {"content": json.dumps({"present": True, "people_count": 1,
                                                                     "description": "Une personne devant l'écran."})}}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        ollama = ThreadingHTTPServer(("127.0.0.1", 0), Ollama)
        threading.Thread(target=ollama.serve_forever, daemon=True).start()
        config = tmp / "comm.json"
        config.write_text(json.dumps({"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"},
                                      "tts": {"kind": "piper", "executable": str(piper), "voice_dir": str(voices),
                                              "default_voice": "fr_FR-siwis-medium"},
                                      "vision": {"kind": "ollama", "endpoint": f"http://127.0.0.1:{ollama.server_port}",
                                                 "model": "vision-factice"},
                                      "allowed_origin": "http://127.0.0.1:8765"}))
        os.chmod(config, 0o600)
        port = free_port()
        before = listing(tmp / "state")
        env = dict(os.environ, PYTHONPATH=str(HERE.parents[3] / "src"), PYTHONDONTWRITEBYTECODE="1")
        service = subprocess.Popen([sys.executable, "-m", "eidolon_core.comm_service", "--state", str(tmp / "state"),
                                    "--config", str(config), "--port", str(port), "--read-token-file", str(tmp / "read-token")],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            banner = service.stdout.readline()
            check("service démarré en boucle locale, capture désactivée par défaut", "127.0.0.1" in banner
                  and "désactivée par défaut" in banner, banner.strip())

            def call(method, path, body=None, token=key, ctype="application/json", origin=None):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                headers = {"Host": f"127.0.0.1:{port}", "Content-Type": ctype}
                if token:
                    headers["Authorization"] = "Bearer " + token
                if origin:
                    headers["Origin"] = origin
                started = time.monotonic()
                conn.request(method, path, body=body, headers=headers)
                r = conn.getresponse(); raw = r.read(); conn.close()
                return r.status, (json.loads(raw) if raw else None), round(time.monotonic() - started, 4), r

            status, body, _, _ = call("GET", "/v1/comm/status")
            check("statut : 3 moteurs annoncés, capture off", status == 200 and body["capture_default"] == "off"
                  and body["tts"]["default_voice"] == "fr_FR-siwis-medium", body["tts"].get("engine"))
            check("jeton de lecture refusé", call("GET", "/v1/comm/status", token=read)[1]["error"] == "READ_TOKEN_NOT_ALLOWED")
            check("sans clé : refusé", call("GET", "/v1/comm/status", token=None)[0] == 401)
            check("autre origine refusée", call("GET", "/v1/comm/status", origin="http://evil.example")[1]["error"] == "ORIGIN_REFUSED")
            status, body, t_stt, _ = call("POST", "/v1/comm/stt", write_wav(tone(2.0)), ctype="audio/wav")
            check("transcription : texte non vérifié, sans permission", status == 200 and body["unverified"]
                  and body["authorizes_execution"] is False, body.get("text"))
            check("audio refusé hors format", call("POST", "/v1/comm/stt", b"ID3", ctype="audio/wav")[1]["error"] == "AUDIO_FORMAT_UNSUPPORTED")
            text = "Bonjour toytoy. Le NAS répond normalement. Veux-tu un diagnostic ?"
            first, t_first = None, None
            timings = []
            for index in range(3):
                status, body, t, _ = call("POST", "/v1/comm/tts", json.dumps({"text": text, "index": index}).encode())
                timings.append(t)
                if index == 0:
                    first = body
                ok_chunk = status == 200 and base64.b64decode(body["wav_base64"]).startswith(b"RIFF")
            check("synthèse Piper (exécutable factice) phrase par phrase", first["chunks"] == 3 and body["last"] and ok_chunk,
                  {"voice": first["voice"], "engine": first["engine"]})
            status, body, t_vision, _ = call("POST", "/v1/comm/vision/describe?purpose=presence", jpeg(640, 480), ctype="image/jpeg")
            check("vision Ollama (factice) : présence, sans identité, image non gardée", status == 200 and body["present"]
                  and body["identity"] is None and body["image"]["kept"] is False and body["authenticates"] is False,
                  body.get("event"))
            check("aucun fichier audio ou image laissé dans l'état", listing(tmp / "state") == before,
                  len(listing(tmp / "state")) - len(before))
            rss = int(Path(f"/proc/{service.pid}/status").read_text().split("VmRSS:")[1].split()[0])
            measures = {"stt_s": t_stt, "tts_chunk_s": timings, "vision_s": t_vision, "service_rss_kib": rss,
                        "note": "moteurs simulés ou factices : ne qualifie ni la VM ni Windows"}
        finally:
            service.terminate()
            try:
                service.wait(10)
            except subprocess.TimeoutExpired:
                service.kill()
            ollama.shutdown(); ollama.server_close()
        check("arrêt propre sur SIGTERM", service.returncode is not None, service.returncode)
    passed = sum(c["ok"] for c in CHECKS)
    print(json.dumps({"passed": passed, "total": len(CHECKS), "measures": measures, "checks": CHECKS},
                     ensure_ascii=False, indent=1))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
