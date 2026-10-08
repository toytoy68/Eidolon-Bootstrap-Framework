# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g072.py
# Description : Réponses HTTP hostiles aux deux adaptateurs de planificateur, sur sockets loopback réels (C-TASK-G072)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g072.py <frozen eidolon-core/src>      (exit 1 if an expectation fails)

A raw TCP server on 127.0.0.1 answers each request with scripted BYTES (optionally trickled),
counts requests and records whether the synthetic secret or a remote text reaches the error.
The adapters are used unchanged with their real stdlib transports. No model, no engine:
nothing here validates a real Ollama or llama.cpp server."""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True

from eidolon_core.ollama_model import OllamaConfig, OllamaError, OllamaModel  # noqa: E402
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatError, OpenAIChatModel  # noqa: E402

SECRET = "sk-synthetique-G072-ne-doit-pas-sortir"
REMOTE = "TEXTE-DISTANT-G072"
MODEL = "synthetic-g072:1b"
PLAN = json.dumps({"version": 1, "steps": []})
FAILED = []


class RawServer:
    """One scripted answer per connection: list of (bytes, delay_before_seconds)."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.script = []
        self.requests = []
        self.stop = False
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while not self.stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        try:
            conn.settimeout(10)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                data += chunk
            head, _, body = data.partition(b"\r\n\r\n")
            length = next((int(line.split(b":")[1]) for line in head.split(b"\r\n")
                           if line.lower().startswith(b"content-length:")), 0)
            while len(body) < length:
                body += conn.recv(65536)
            self.requests.append(head)
            for payload, delay in self.script:
                if delay:
                    time.sleep(delay)
                conn.sendall(payload)
        except OSError:
            pass
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()

    def close(self):
        self.stop = True
        self.sock.close()


def http(status, body, headers=(), *, reason=b"OK"):
    lines = [b"HTTP/1.1 %d %s" % (status, reason)] + list(headers)
    return b"\r\n".join(lines) + b"\r\n\r\n" + body


def ollama_ok():
    return json.dumps({"model": MODEL, "done": True, "done_reason": "stop",
                       "message": {"role": "assistant", "content": PLAN}}).encode()


def openai_ok():
    return json.dumps({"object": "chat.completion", "model": MODEL, "choices": [
        {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": PLAN}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()


def adapters(port, timeout=1.0):
    os.environ["G072_KEY"] = SECRET
    o = OllamaModel(OllamaConfig(endpoint=f"http://127.0.0.1:{port}", model=MODEL, options={"num_predict": 64},
                                 timeout_seconds=timeout, max_response_bytes=4096))
    c = OpenAIChatModel(OpenAIChatConfig(endpoint=f"http://127.0.0.1:{port}", model=MODEL, options={"max_tokens": 64},
                                         timeout_seconds=timeout, max_response_bytes=4096, api_key_env="G072_KEY"))
    return {"ollama": (o, ollama_ok()), "openai": (c, openai_ok())}


def call(model):
    t0 = time.monotonic()
    try:
        out = model.propose("compter les mots", {"items": []})
        result = "OK" if out == PLAN else f"OK inattendu {out!r:.40}"
    except (OllamaError, OpenAIChatError) as exc:
        result = f"{getattr(exc, 'code', '?')}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- any other type is itself a finding
        result = f"BRUT {type(exc).__name__}: {exc}"
    return result, time.monotonic() - t0


def expect(label, result, want, server, before, extra=""):
    leaked = [s for s in (SECRET, REMOTE) if s in result]
    calls = len(server.requests) - before
    ok = result.split(":")[0] in want and not leaked and calls == 1
    print(f"{'✓' if ok else '✗'} {label} : {result[:90]} ; appels {calls}{' ; FUITE ' + str(leaked) if leaked else ''}{extra}")
    if not ok:
        FAILED.append(label)


def cases(ok_body):
    big = b'{"pad":"' + b"x" * 5000 + b'"}'
    ct = b"Content-Type: application/json"
    return [
        ("réponse nominale", [(http(200, ok_body, [ct, b"Content-Length: %d" % len(ok_body)]), 0)], {"OK"}),
        ("EOF avant tout octet", [(b"", 0)], {"TRANSPORT"}),
        # http.client takes EOF inside the header block as its end: the refusal is BAD_RESPONSE (G072-1).
        ("EOF au milieu des en-têtes", [(b"HTTP/1.1 200 OK\r\nContent-Ty", 0)], {"TRANSPORT", "BAD_RESPONSE"}),
        ("corps sans longueur tronqué puis EOF", [(http(200, ok_body[:-5], [ct]), 0)], {"BAD_RESPONSE"}),
        ("Content-Length plus grand que le corps puis EOF",
         [(http(200, ok_body[:20], [ct, b"Content-Length: %d" % len(ok_body)]), 0)], {"INCOMPLETE_HTTP", "TRANSPORT"}),
        ("Content-Length dupliqué identique",
         [(http(200, ok_body, [ct, b"Content-Length: %d" % len(ok_body)] * 1 + [b"Content-Length: %d" % len(ok_body)]), 0)],
         {"BAD_HTTP_FRAMING", "TRANSPORT"}),
        ("Content-Length contradictoires",
         [(http(200, ok_body, [ct, b"Content-Length: %d" % len(ok_body), b"Content-Length: 3"]), 0)],
         {"BAD_HTTP_FRAMING", "TRANSPORT"}),
        ("Content-Length négatif", [(http(200, ok_body, [ct, b"Content-Length: -1"]), 0)], {"BAD_HTTP_FRAMING", "TRANSPORT"}),
        ("Content-Length + chunked", [(http(200, b"%x\r\n" % len(ok_body) + ok_body + b"\r\n0\r\n\r\n",
                                             [ct, b"Content-Length: 5", b"Transfer-Encoding: chunked"]), 0)],
         {"BAD_HTTP_FRAMING", "TRANSPORT"}),
        ("Transfer-Encoding gzip", [(http(200, ok_body, [ct, b"Transfer-Encoding: gzip"]), 0)], {"BAD_HTTP_FRAMING", "TRANSPORT"}),
        ("chunked valide", [(http(200, b"%x\r\n" % len(ok_body) + ok_body + b"\r\n0\r\n\r\n",
                                  [ct, b"Transfer-Encoding: chunked"]), 0)], {"OK"}),
        ("chunk incomplet puis EOF", [(http(200, b"%x\r\n" % len(ok_body) + ok_body[:10], [ct, b"Transfer-Encoding: chunked"]), 0)],
         {"TRANSPORT"}),
        ("taille de chunk invalide", [(http(200, b"zz\r\n" + ok_body, [ct, b"Transfer-Encoding: chunked"]), 0)], {"TRANSPORT"}),
        ("corps absent (fermeture)", [(http(200, b"", [ct]), 0)], {"BAD_RESPONSE"}),
        ("corps trop grand déclaré", [(http(200, big, [ct, b"Content-Length: %d" % len(big)]), 0)], {"RESPONSE_TOO_LARGE"}),
        ("corps trop grand sans longueur", [(http(200, big, [ct]), 0)], {"RESPONSE_TOO_LARGE"}),
        ("corps trop grand en chunked", [(http(200, b"%x\r\n" % len(big) + big + b"\r\n0\r\n\r\n",
                                               [ct, b"Transfer-Encoding: chunked"]), 0)], {"RESPONSE_TOO_LARGE"}),
        ("statut 500 avec texte distant", [(http(500, json.dumps({"error": REMOTE}).encode(), [ct], reason=b"ERR"), 0)],
         {"HTTP_STATUS"}),
        ("statut 401 reflétant la clé", [(http(401, json.dumps({"error": {"message": SECRET}}).encode(), [ct],
                                               reason=b"NO"), 0)], {"HTTP_STATUS", "AUTHENTICATION"}),
        ("statut 200, enveloppe d'erreur distante", [(http(200, json.dumps({"error": REMOTE}).encode(), [ct]), 0)],
         {"MODEL_ERROR", "BAD_RESPONSE"}),
        ("ligne de statut invalide", [(b"HTTP/9 OK\r\n\r\n", 0)], {"TRANSPORT"}),
        ("en-tête de 70 000 octets", [(b"HTTP/1.1 200 OK\r\nX: " + b"a" * 70000 + b"\r\n\r\n", 0)], {"TRANSPORT"}),
    ]


RUNTIME = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import OllamaConfig, OllamaModel
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
model = OllamaModel(OllamaConfig(endpoint="http://127.0.0.1:" + sys.argv[2], model=sys.argv[3],
                                 options={"num_predict": 64}, timeout_seconds=1.0, max_response_bytes=4096))
rt = Runtime(Store(sys.argv[4]), model=model, limits=Limits(call_seconds=3))
t0 = time.monotonic()
m = rt.run(rt.create(DEMO_REQUEST)["id"])
print(json.dumps({"status": m["status"], "code": m["error"]["code"], "message": m["error"]["message"],
                  "seconds": round(time.monotonic() - t0, 2)}))
"""


def runtime_deadline():
    """The outer limit is the runtime worker's call_seconds, not the adapter's socket timeout."""
    import subprocess
    import tempfile
    print("== borne totale par le runtime (call_seconds = 3, timeout_seconds = 1, 1 octet / 0,6 s)")
    server = RawServer()
    body = ollama_ok()
    frame = http(200, body, [b"Content-Type: application/json", b"Content-Length: %d" % len(body)])
    server.script = [(frame[:len(frame) - len(body)], 0)] + [(body[i:i + 1], 0.6) for i in range(len(body))]
    try:
        with tempfile.TemporaryDirectory() as state:
            p = subprocess.run([sys.executable, "-c", RUNTIME, SRC, str(server.port), MODEL, state],
                               capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout)
    finally:
        server.close()
    ok = (out["status"] in ("BLOCKED", "FAILED") and out["code"] == "MODEL_UNAVAILABLE" and out["seconds"] < 6
          and len(server.requests) == 1 and REMOTE not in out["message"])
    print(f"{'✓' if ok else '✗'} mission arrêtée par le délai de l'exécutant : {out} ; appels {len(server.requests)}")
    if not ok:
        FAILED.append("borne totale runtime")


def main():
    print(f"Sources examinées : {SRC}")
    server = RawServer()
    other = RawServer()            # redirect target: must never be contacted
    other.script = [(http(200, b"{}", [b"Content-Type: application/json"]), 0)]
    try:
        for name, (model, ok_body) in adapters(server.port).items():
            print(f"== {name}")
            for label, script, want in cases(ok_body):
                server.script = script
                before = len(server.requests)
                result, _ = call(model)
                expect(label, result, want, server, before)
            server.script = [(http(302, b"", [b"Location: http://127.0.0.1:%d/v1/chat/completions" % other.port,
                                              b"Content-Length: 0"], reason=b"Found"), 0)]
            before, hits = len(server.requests), len(other.requests)
            result, _ = call(model)
            expect("redirection 302 vers un autre port", result, {"HTTP_STATUS", "BAD_RESPONSE"}, server, before,
                   f" ; cible de la redirection contactée {len(other.requests) - hits} fois")
            if len(other.requests) != hits:
                FAILED.append(name + " redirection suivie")
            os.environ["HTTP_PROXY"] = os.environ["http_proxy"] = f"http://127.0.0.1:{other.port}"
            server.script = cases(ok_body)[0][1]
            before, hits = len(server.requests), len(other.requests)
            result, _ = call(model)
            for k in ("HTTP_PROXY", "http_proxy"):
                os.environ.pop(k, None)
            expect("variable HTTP_PROXY pointant ailleurs (ignorée)", result, {"OK"}, server, before,
                   f" ; proxy contacté {len(other.requests) - hits} fois")
            sent = server.requests[-1]
            if name == "openai":
                print(f"   en-tête Authorization envoyé au point configuré seulement : {SECRET.encode() in sent}")

        print("== durées : délai de socket ≠ durée totale (adaptateur seul, timeout_seconds = 1)")
        for name, (model, ok_body) in adapters(server.port, timeout=1.0).items():
            frame = http(200, ok_body, [b"Content-Type: application/json", b"Content-Length: %d" % len(ok_body)])
            head, body = frame[:len(frame) - len(ok_body)], ok_body
            # 1 byte every 0.6 s (< 1 s socket timeout) for the first 12 body bytes, then the rest.
            server.script = [(head, 0)] + [(body[i:i + 1], 0.6) for i in range(12)] + [(body[12:], 0.6)]
            before = len(server.requests)
            result, elapsed = call(model)
            print(f"   {name} : corps distillé (1 octet / 0,6 s) → {result[:40]} en {elapsed:.1f} s "
                  f"(> timeout_seconds=1 : aucune borne de durée totale dans l'adaptateur)")
            server.script = [(head, 0), (body, 1.5)]
            result, elapsed = call(model)
            ok = result.startswith("TRANSPORT") and elapsed < 1.4
            print(f"{'✓' if ok else '✗'} {name} : silence de 1,5 s → {result[:40]} en {elapsed:.1f} s (délai de socket)")
            if not ok:
                FAILED.append(name + " délai de socket")
    finally:
        server.close()
        other.close()
    runtime_deadline()
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
