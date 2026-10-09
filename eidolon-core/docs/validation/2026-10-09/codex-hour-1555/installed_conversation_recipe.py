# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed_conversation_recipe.py
# Description : Recette du parcours conversation → mission → résultat depuis le paquet installé (C-TASK-G089)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""env -u PYTHONPATH <venv>/bin/python installed_conversation_recipe.py <web root of the extracted bundle>

Uses the INSTALLED eidolon_core only (refuses to run from a source checkout), synthetic state in a
temporary folder, the simulated dialogue model and loopback servers started from the installed
package. Missions are run by the installed synthetic runtime, as an operator would; never by the API.
Not a VM, Windows or GPU test, and no real model is qualified."""
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import eidolon_core
from eidolon_core.contracts import digest
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store

WEB = str(Path(sys.argv[1]).resolve())
if "site-packages" not in eidolon_core.__file__:
    sys.exit("REFUSED: run with the installed package (env -u PYTHONPATH <venv>/bin/python)")
checks = []


def check(name, condition, detail=""):
    checks.append({"check": name, "ok": bool(condition), "detail": detail})


def start(state, token_file, conversations):
    p = subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", state, "--token-file", token_file,
                          "--port", "0", "--web-root", WEB, "--conversations", conversations],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        line = p.stdout.readline()
        m = re.search(r"http://127\.0\.0\.1:(\d+)", line)
        if m:
            return p, int(m.group(1))
    p.kill()
    raise SystemExit("server did not start: " + p.stderr.read()[-300:])


def call(port, route, body, token, method="POST"):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    headers = {"Host": f"127.0.0.1:{port}", "Authorization": "Bearer " + token}
    raw = None
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    c.request(method, route, body=raw, headers=headers)
    r = c.getresponse()
    value = json.loads(r.read() or b"null")
    c.close()
    return r.status, value


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g089-") as tmp:
        state = os.path.join(tmp, "state")
        Store(state)
        runtime = synthetic_runtime(Store(state))
        read = secrets.token_urlsafe(32)
        token_file = os.path.join(tmp, "read-token")
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, (read + "\n").encode()); os.close(fd)
        paired = json.loads(subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", state,
                                            "pair", "--client-id", "pc-recette", "--actor", "toytoy"],
                                           capture_output=True, text=True, check=True).stdout)
        key = paired["token"]
        server, port = start(state, token_file, "simulated")
        try:
            conv = lambda route, body, token=key: call(port, "/v1/conversations/" + route, body, token)
            s, opened = conv("open", {"client_key": "recette"})
            cid = opened["conversation_id"]
            check("ouverture avec la clé de conversation", s == 200 and opened["actor"] == "toytoy")
            say = lambda key_, text: conv("turn", {"conversation_id": cid, "client_turn_key": key_, "text": text})[1]
            check("réponse", say("t1", "Bonjour")["reply"]["kind"] == "ANSWER")
            clar = say("t2", "Peux-tu vérifier l'état du service ?")["reply"]
            check("clarification avec candidats du catalogue", clar["kind"] == "CLARIFICATION"
                  and clar["candidates"] == ["sim-memory", "sim-nas"], clar["core_note"])
            prop = say("t3", "Diagnostique le nas.")["reply"]
            check("proposition figée", prop["kind"] == "PROPOSAL" and prop["proposal"]["target_id"] == "sim-nas")
            check("hors capacités expliqué", say("t4", "Redémarre le nas.")["reply"]["core_note"] == "TEMPLATE_UNSUPPORTED")
            p = prop["proposal"]

            def submission(key_, **changes):
                v = {"protocol": "eidolon-proposal-submission/1", "store_id": opened["store_id"],
                     "client_id": opened["client_id"], "command_key": key_, "conversation_id": cid,
                     "proposal_id": p["proposal_id"], "proposal_version": p["version"],
                     "proposal_sha256": digest(p), "actor": opened["actor"], "reason": "recette G089"}
                v.update(changes)
                return v
            check("lecteur refusé en écriture", conv("submit", submission("s1"), read)[1]["error"] == "READ_TOKEN_NOT_ALLOWED")
            check("proposition modifiée refusée", conv("submit", submission("s0", proposal_sha256="0" * 64))[1]["error"]
                  == "PROPOSAL_CHANGED")
            # Lost response: the client vanishes after sending; the receipt is found and a resend adds nothing.
            body = json.dumps(submission("s1"), ensure_ascii=False).encode()
            with socket.create_connection(("127.0.0.1", port), timeout=20) as raw:
                raw.sendall((f"POST /v1/conversations/submit HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n"
                             f"Authorization: Bearer {key}\r\nContent-Type: application/json\r\n"
                             f"Content-Length: {len(body)}\r\n\r\n").encode() + body)
                raw.recv(1)
            s, found = conv("receipt", {"command_key": "s1"})
            check("réponse perdue : reçu retrouvé", found["status"] == "FOUND"
                  and found["receipt"]["status"] == "MISSION_CREATED")
            mission = found["receipt"]["mission_id"]
            again = conv("submit", submission("s1"))[1]
            check("doublon : même reçu", again["mission_id"] == mission)
            check("autre clé pour la même proposition refusée",
                  conv("submit", submission("s2"))[1]["error"] == "PROPOSAL_ALREADY_SUBMITTED")
            with runtime.store.connection() as db:
                count = db.execute("SELECT count(*) FROM missions").fetchone()[0]
            check("une seule mission créée", count == 1)
            check("soumission ne lance rien", runtime.store.get(mission)["status"] == "NEW")
            finished = runtime.run(mission)
            s, snap = call(port, f"/v1/missions/{mission}", None, read, "GET")
            m = snap["snapshot"]["mission"]
            check("résultat lu par l'API de lecture", finished["status"] == "SUCCEEDED" and m["status"] == "SUCCEEDED"
                  and m["outcome_status"] == "ACHIEVED", m["objective_kind"])
            link = found["receipt"]["link"]
            check("références du résultat : lien vérifié", link["mission_id"] == mission
                  and link["proposal_sha256"] == digest(p) and link["mission_request_sha256"] == digest(p["request"]))
            check("la clé de conversation ne lit pas", call(port, f"/v1/missions/{mission}", None, key, "GET")[0] == 401)
            # Cancellation of a second proposal: a recorded request, then the runtime's confirmed stop.
            prop2 = say("t5", "Diagnostique la mémoire.")["reply"]["proposal"]
            p = prop2
            second = conv("submit", submission("s3"))[1]["mission_id"]
            cp_status, cp = conv("cancel_proposal", {"conversation_id": cid, "mission_id": second})
            assert cp_status == 200 and cp["kind"] == "PROPOSAL"
            assert digest(cp["proposal"]) == cp["proposal_sha256"]
            s, cancel = conv("cancel", {"command_key": "c1", "conversation_id": cid,
                                       "proposal_sha256": cp["proposal_sha256"],
                                       "mission_id": second, "reason": "plus utile"})
            check("annulation demandée, non confirmée", cancel["meaning"] == "CANCELLATION_REQUESTED_NOT_CONFIRMED"
                  and runtime.store.get(second)["status"] == "NEW")
            check("arrêt confirmé par le runtime", runtime.run(second)["status"] == "CANCELLED")
        finally:
            server.terminate(); server.wait(timeout=10)
        # Unavailable model: same state, a private config pointing to a closed local port.
        config = os.path.join(tmp, "model.json")
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, json.dumps({"version": 1, "provider": "llama-server", "endpoint": "http://127.0.0.1:9",
                                 "model": "absent", "options": {"max_tokens": 64}, "timeout_seconds": 2}).encode())
        os.close(fd)
        server, port = start(state, token_file, config)
        try:
            s, opened = call(port, "/v1/conversations/open", {"client_key": "panne"}, key)
            s, turn = call(port, "/v1/conversations/turn", {"conversation_id": opened["conversation_id"],
                                                            "client_turn_key": "p1", "text": "Diagnostique le nas."}, key)
            check("modèle indisponible : rien de deviné", turn["reply"]["kind"] == "UNAVAILABLE"
                  and turn["reply"]["proposal"] is None, turn["reply"]["core_note"])
        finally:
            server.terminate(); server.wait(timeout=10)
    print(json.dumps({"recipe": "G089 adapted by Codex to G100 cancellation contract", "installed_module": eidolon_core.__file__.split("site-packages")[-1],
                      "web_root_files": sorted(os.listdir(WEB)), "passed": sum(c["ok"] for c in checks),
                      "total": len(checks), "checks": checks}, ensure_ascii=False, indent=1))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
