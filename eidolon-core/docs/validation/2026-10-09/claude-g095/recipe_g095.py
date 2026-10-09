# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_g095.py
# Description : Recette indépendante du parcours complet depuis le paquet installé, pannes incluses (C-TASK-G095)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""env -u PYTHONPATH <venv>/bin/python recipe_g095.py <web root of the extracted bundle>

INSTALLED package only (refuses a source checkout). Replays the unchanged G089 recipe, then adds:
partial context, resume, busy storage, a server killed during a model call, export/inspection, a
rejected artifact and the media contract. Synthetic data, simulated or fake loopback engines; no VM,
Windows, GPU or real model. A model reply or a queue/engine receipt is never counted as an objective."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

import eidolon_core
from eidolon_core.contracts import digest

HERE = Path(__file__).resolve().parent
WEB = str(Path(sys.argv[1]).resolve())
BIN = Path(sys.executable).parent
if "site-packages" not in eidolon_core.__file__:
    sys.exit("REFUSED: run with the installed package (env -u PYTHONPATH <venv>/bin/python)")
sys.path.insert(0, str(HERE.parent / "claude-g089"))
import recipe_g089 as g089  # noqa: E402  (start/call helpers of the original recipe)

checks = []


def check(section, name, condition, detail=""):
    checks.append({"section": section, "check": name, "ok": bool(condition), "detail": detail})


class Hanging(BaseHTTPRequestHandler):
    """A local 'engine' that accepts the request and never answers in time."""
    hits = 0

    def log_message(self, *_):
        pass

    def do_POST(self):
        Hanging.hits += 1
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(30)


def private_file(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, content.encode()); os.close(fd)


def main():
    # A. The original G089 recipe, unchanged, from this installed package.
    g = subprocess.run([sys.executable, str(HERE.parent / "claude-g089" / "recipe_g089.py"), WEB],
                       capture_output=True, text=True, timeout=600)
    original = json.loads(g.stdout)
    check("A", "recette G089 d'origine rejouée", g.returncode == 0 and original["passed"] == original["total"],
          f"{original['passed']}/{original['total']}")

    with tempfile.TemporaryDirectory(prefix="eidolon-g095-") as tmp:
        state = os.path.join(tmp, "state")
        from eidolon_core.store import Store
        Store(state)
        read = secrets.token_urlsafe(32)
        token_file = os.path.join(tmp, "read-token")
        private_file(token_file, read + "\n")
        key = json.loads(subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", state, "pair",
                                         "--client-id", "pc-g095", "--actor", "toytoy"], capture_output=True,
                                        text=True, check=True).stdout)["token"]
        server, port = g089.start(state, token_file, "simulated")
        conv = lambda route, body: g089.call(port, "/v1/conversations/" + route, body, key)
        try:
            # B. Partial context is announced; resume lists the conversation.
            opened = conv("open", {"client_key": "g095"})[1]
            cid = opened["conversation_id"]
            for n in range(22):
                conv("turn", {"conversation_id": cid, "client_turn_key": f"h{n}", "text": f"message {n}"})
            reply = conv("turn", {"conversation_id": cid, "client_turn_key": "last", "text": "Diagnostique le nas."})[1]["reply"]
            check("B", "contexte partiel annoncé", reply["context"]["partial"] and reply["context"]["history_excluded"] == 2,
                  json.dumps(reply["context"]))
            recent = conv("recent", {})[1]["conversations"]
            check("B", "reprise : conversation listée", [c["conversation_id"] for c in recent] == [cid])
            # C. Busy storage: a writer holds the conversation database.
            holder = sqlite3.connect(os.path.join(state, "conversations", "conversations.sqlite3"), isolation_level=None)
            holder.execute("BEGIN IMMEDIATE")
            began = time.monotonic()
            status, busy = conv("turn", {"conversation_id": cid, "client_turn_key": "busy", "text": "Bonjour"})
            waited = time.monotonic() - began
            holder.rollback(); holder.close()
            check("C", "stockage occupé : 503 explicite, borné", status == 503 and busy["error"] == "CONVERSATION_STORE_BUSY"
                  and waited < 5, f"{status} {busy.get('error')} en {waited:.1f} s")
            again = conv("turn", {"conversation_id": cid, "client_turn_key": "busy", "text": "Bonjour"})[1]
            check("C", "après libération : le même tour aboutit", again["reply"]["kind"] == "ANSWER")
        finally:
            server.terminate(); server.wait(timeout=10)

        # D. Server killed during a model call, then restarted: no second model call.
        engine = ThreadingHTTPServer(("127.0.0.1", 0), Hanging)
        threading.Thread(target=engine.serve_forever, daemon=True).start()
        config = os.path.join(tmp, "hanging-model.json")
        private_file(config, json.dumps({"version": 1, "provider": "llama-server",
                                         "endpoint": f"http://127.0.0.1:{engine.server_address[1]}", "model": "lent",
                                         "options": {"max_tokens": 64}, "timeout_seconds": 2}))
        server, port = g089.start(state, token_file, config)
        body = {"conversation_id": cid, "client_turn_key": "cut", "text": "Diagnostique le nas."}
        threading.Thread(target=lambda: g089.call(port, "/v1/conversations/turn", body, key), daemon=True).start()
        deadline = time.monotonic() + 10
        while Hanging.hits == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        os.kill(server.pid, signal.SIGKILL); server.wait(timeout=10)
        claimed_at = time.monotonic()
        server, port = g089.start(state, token_file, "simulated")
        try:
            right_after = g089.call(port, "/v1/conversations/turn", body, key)[1]
            # Dead attempt's admission deadline: attempt budget (2 s timeout + 5 s) plus the 5 s claim margin.
            time.sleep(max(0, 12.5 - (time.monotonic() - claimed_at)))
            later = g089.call(port, "/v1/conversations/turn", body, key)[1]
        finally:
            server.terminate(); server.wait(timeout=10)
            engine.shutdown(); engine.server_close()
        check("D", "processus tué : tentative en cours, pas de réponse inventée", right_after.get("pending") is True,
              json.dumps({k: right_after.get(k) for k in ("pending", "model_called")}))
        check("D", "après l'échéance : interrompu, jamais relancé", (later["reply"] or {}).get("core_note")
              == "MODEL_ATTEMPT_INTERRUPTED" and later["model_called"] is False and Hanging.hits == 1,
              f"appels moteur {Hanging.hits}")

        # E. Export and offline inspection.
        out = os.path.join(tmp, "export.json")
        e = subprocess.run([sys.executable, "-m", "eidolon_core.conversation_export", "export", "--state", state,
                            "--client-id", "pc-g095", "--conversation-id", cid, "--output", out], capture_output=True, text=True)
        i = subprocess.run([sys.executable, "-m", "eidolon_core.conversation_export", "inspect", out],
                           capture_output=True, text=True)
        exported = json.loads(open(out).read())
        check("E", "export : cohérent, historique, sans clé", e.returncode == 0 and json.loads(i.stdout)["status"]
              == "CONSISTENT" and key not in open(out).read() and exported["import_supported"] is False)
        exported["turns"][0]["turn"]["text"] = "falsifié"
        tampered = os.path.join(tmp, "falsifie.json")
        private_file(tampered, json.dumps(exported))
        t = subprocess.run([sys.executable, "-m", "eidolon_core.conversation_export", "inspect", tampered],
                           capture_output=True, text=True)
        check("E", "export falsifié détecté", t.returncode == 2 and json.loads(t.stdout)["status"] == "INCONSISTENT")

        # F. Rejected artifact (Codex's store) and the media contract (G094).
        media = os.path.join(tmp, "medias")
        store_id = json.loads(subprocess.run([str(BIN / "eidolon-media"), "artifact-init", "--root", media],
                                             capture_output=True, text=True, check=True).stdout)["store_id"]
        fake = os.path.join(tmp, "faux.png")
        private_file(fake, "pas une image")
        rejected = subprocess.run([str(BIN / "eidolon-media"), "artifact-import", "--root", media, "--store-id", store_id,
                                   "--source", fake], capture_output=True, text=True)
        # The store reports its refusal on standard error, with a non-zero exit code.
        check("F", "artefact rejeté par le magasin", rejected.returncode != 0
              and "UNSUPPORTED_MEDIA_HEADER" in rejected.stdout + rejected.stderr,
              (rejected.stdout + rejected.stderr).strip()[-160:])
        import struct, zlib
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        png = os.path.join(tmp, "vrai.png")
        with open(png, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                         + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")) + chunk(b"IEND", b""))
        reference = json.loads(subprocess.run([str(BIN / "eidolon-media"), "artifact-import", "--root", media,
                                               "--store-id", store_id, "--source", png], capture_output=True, text=True,
                                              check=True).stdout)["reference"]
        from eidolon_core import conversation as cv, conversation_media as cm
        turn = {"protocol": cv.TURN_PROTOCOL, "store_id": opened["store_id"], "conversation_id": cid,
                "turn_id": "t-" + "1" * 32, "sequence": 1, "role": "user", "text": "Retouche la photo", "client_id": "pc-g095",
                "client_turn_key": "m", "previous_turn_sha256": None}
        mine = cm.attachment(store_id=opened["store_id"], owner_client_id="pc-g095", conversation_id=cid, reference=reference)
        suggestion = {"template": "media.image.edit", "parameters": {"prompt": "Plus chaud", "artifact_id": reference["artifact_id"],
                                                                     "format": "square"}}
        kind, proposal = cm.freeze(turn, suggestion, [mine], owner_client_id="pc-g095")
        foreign = cm.freeze(turn, suggestion, [mine], owner_client_id="pc-autre")
        check("F", "proposition média : référence rattachée, jamais un chemin",
              kind == "PROPOSAL" and proposal["artifact"] == reference and "source" not in cm.media_request(proposal))
        check("F", "artefact d'un autre propriétaire refusé", foreign == ("CLARIFICATION", "MEDIA_ARTIFACT_NOT_ATTACHED"))
        check("F", "aucun état média ne vaut succès", all(cm.stage(s) not in ("result", "SUCCEEDED") for s in cm.STAGES))

    print(json.dumps({"recipe": "G095", "installed_module": eidolon_core.__file__.split("site-packages")[-1],
                      "passed": sum(c["ok"] for c in checks), "total": len(checks), "checks": checks,
                      "g089": original["checks"]}, ensure_ascii=False, indent=1))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
