# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_g082.py
# Description : Recette opérateur synthétique serveur/PC depuis le paquet installé, tunnel simulé (C-TASK-G082)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with the INSTALLED package (env -u PYTHONPATH <venv>/bin/python, from /):
    python recipe_g082.py <archive>/eidolon-core/desktop/connected

Loopback and synthetic data only. The SSH tunnel is replaced by a local TCP relay with the same
shape (PC port -> server 127.0.0.1 port); a real `ssh -L` is qualified on VM100/Windows, not here.
Prints one JSON report; exit code 0 only if every check passed."""
import http.client
import json
import os
import re
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

WEB = sys.argv[1]
PY = sys.executable
CHECKS = []


def check(step, name, ok, detail=""):
    CHECKS.append({"step": step, "check": name, "ok": bool(ok), "detail": str(detail)[:300]})


def cli(*args, ok=True):
    done = subprocess.run([PY, *args], capture_output=True, text=True, timeout=120)
    if ok and done.returncode != 0:
        raise SystemExit(f"command failed: {args[:3]} {done.stdout[-200:]} {done.stderr[-200:]}")
    return done


class Relay:
    """Stand-in for `ssh -L 127.0.0.1:<pc>:127.0.0.1:<server>`: closing it is a tunnel loss."""

    def __init__(self, target):
        self.target = target
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.open = True
        self.links = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.open:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(("127.0.0.1", self.target))
            self.links += [client, upstream]
            for a, b in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pump, args=(a, b), daemon=True).start()

    @staticmethod
    def _pump(a, b):
        try:
            while True:
                data = a.recv(65536)
                if not data:
                    break
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        self.open = False
        try:
            self.listener.shutdown(socket.SHUT_RDWR)        # wakes the blocked accept()
        except OSError:
            pass
        self.listener.close()
        for s in self.links:
            try:
                s.close()
            except OSError:
                pass


SERVER_PORT = {}


def request(port, method, path, body=None, token=None, host_port=None):
    """host_port: the port the browser shows in Host. With `ssh -L 8765:127.0.0.1:8765` it is the
    server's own port (same number on both ends); the relay here listens elsewhere, so it is set."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    headers = {"Host": f"127.0.0.1:{host_port or SERVER_PORT.get('port', port)}"}
    if token:
        headers["Authorization"] = "Bearer " + token
    raw = None
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    try:
        c.request(method, path, body=raw, headers=headers)
        r = c.getresponse()
        data = r.read()
    finally:
        c.close()
    try:
        return r.status, json.loads(data)
    except ValueError:
        return r.status, data


def start(state, token_file, profiles, relay_port_hint=None):
    p = subprocess.Popen([PY, "-m", "eidolon_core.http_api", "--state", state, "--token-file", token_file,
                          "--port", "0", "--web-root", WEB, "--conversations", "profiles",
                          "--dialogue-profiles", profiles], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        m = re.search(r"http://127\.0\.0\.1:(\d+)", p.stdout.readline())
        if m:
            return p, int(m.group(1))
    p.kill()
    raise SystemExit("server did not start: " + p.stderr.read()[-300:])


def private(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, content.encode()); os.close(fd)


def missions_now(state):
    db = sqlite3.connect(os.path.join(state, "missions.sqlite3"))
    try:
        return {i: (json.loads(b)["status"], c) for i, b, c in db.execute("SELECT id, body, cancel_requested FROM missions")}
    finally:
        db.close()


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g082-") as beta:
        state, token_file = os.path.join(beta, "state"), os.path.join(beta, "read-token")
        # S2: synthetic state (demo mission with simulated memory recall) and a private read token.
        demo = json.loads(cli("-m", "eidolon_core", "--state", state, "demo").stdout)
        recalled = [f"{i['information_id']}@{i['revision']}" for i in demo["context"]["items"]]
        check("S2", "mission de démonstration avec rappel mémoire simulé", demo["status"] == "SUCCEEDED"
              and recalled == ["synthetic-note@1"] and demo["context"]["items"][0]["epistemic_status"] == "UNVERIFIED",
              recalled)
        made = cli("-m", "eidolon_core.access_token", "--output", token_file, "--format", "human")
        token = open(token_file).read().strip()
        check("S2", "jeton privé créé, jamais affiché", oct(os.stat(token_file).st_mode & 0o777) == "0o600"
              and token not in made.stdout + made.stderr)
        # Conversation side, operator commands on the server (G087/G098/G099).
        key = json.loads(cli("-m", "eidolon_core.conversation_api", "--state", state, "pair", "--client-id", "pc-toytoy",
                             "--actor", "toytoy").stdout)["token"]
        profiles = os.path.join(beta, "profiles.json")
        private(profiles, json.dumps({"schema": "eidolon-dialogue-profiles/1", "profiles": {"recette": {"kind": "simulated"}}}))
        chosen = json.loads(cli("-m", "eidolon_core.conversation_api", "--state", state, "profile", "select",
                                "--name", "recette", "--actor", "toytoy", "--profiles", profiles).stdout)
        check("S2", "profil de dialogue choisi explicitement", chosen["status"] == "SELECTED")
        inspected = cli("-m", "eidolon_core.conversation_api", "--state", state, "inspect-store", ok=False)
        check("S2", "dépôt des conversations à jour (lecture seule)", inspected.returncode == 0
              and json.loads(inspected.stdout)["state"] == "CURRENT")
        saved = json.loads(cli("-m", "eidolon_core.conversation_api", "--state", state, "backup", "--output",
                               os.path.join(beta, "conversations-backup.sqlite3")).stdout)
        check("S2", "sauvegarde vérifiée avant ouverture", len(saved["file_sha256"]) == 64)
        # S3: diagnostic without starting.
        diag = cli("-m", "eidolon_core.http_api", "--state", state, "--token-file", token_file, "--web-root", WEB,
                   "--port", "8765", "--check", "--format", "human", ok=False)
        check("S3", "diagnostic sans démarrage", diag.returncode == 0, diag.stdout.strip().splitlines()[-1:])

        # S4 + W1: server started, PC reaches it through the tunnel stand-in.
        server, port = start(state, token_file, profiles)
        SERVER_PORT["port"] = port
        relay = Relay(port)
        try:
            pc = relay.port
            check("W", "tunnel vers un AUTRE port local : conversation refusée (Host)",
                  request(pc, "POST", "/v1/conversations/open", {"client_key": "x"}, token=key, host_port=pc)[1]
                  .get("error") == "HOST_REFUSED")
            check("W", "page servie à travers le tunnel", request(pc, "GET", "/")[0] == 200)
            status, health = request(pc, "GET", "/v1/health", token=token)
            check("W", "santé en lecture seule", status == 200 and health["authorizes_execution"] is False, health.get("mode"))
            check("W", "sans jeton : 401", request(pc, "GET", "/v1/health")[0] == 401)
            status, page = request(pc, "POST", "/v1/missions", {}, token=token)
            listed = page.get("missions", page.get("items", []))
            check("W", "missions listées", status == 200 and demo["id"] in json.dumps(page), len(listed))
            status, snap = request(pc, "GET", "/v1/missions/" + demo["id"], token=token)
            # Observed: the read API gives status and history, never the recalled memory text itself.
            check("W", "mission lue à distance ; contenu mémoire non exposé par l'API de lecture",
                  status == 200 and snap["snapshot"]["mission"]["status"] == "SUCCEEDED" and "Ceci est une donn" not in json.dumps(snap, ensure_ascii=False),
                  snap["snapshot"]["mission"]["objective_kind"])
            check("W", "jeton de lecture refusé sur la conversation",
                  request(pc, "POST", "/v1/conversations/open", {"client_key": "x"}, token=token)[0] == 403)
            # Conversation through the tunnel.
            conv = lambda route, body: request(pc, "POST", "/v1/conversations/" + route, body, token=key)
            opened = conv("open", {"client_key": "recette"})[1]
            if "conversation_id" not in opened:
                raise SystemExit("open refused: " + json.dumps(opened))
            cid = opened["conversation_id"]
            reply = conv("turn", {"conversation_id": cid, "client_turn_key": "t1", "text": "Diagnostique le nas."})[1]["reply"]
            check("C", "proposition, modèle nommé", reply["kind"] == "PROPOSAL" and reply["model"]["profile"] == "recette",
                  reply["model"])
            p = reply["proposal"]
            sub = {"protocol": "eidolon-proposal-submission/1", "store_id": opened["store_id"], "client_id": "pc-toytoy",
                   "command_key": "valider-1", "conversation_id": cid, "proposal_id": p["proposal_id"],
                   "proposal_version": p["version"], "proposal_sha256": reply["proposal_sha256"], "actor": "toytoy",
                   "reason": "recette G082"}
            receipt = conv("submit", sub)[1]
            mission = receipt["mission_id"]
            check("C", "mission créée, non lancée", receipt["status"] == "MISSION_CREATED"
                  and missions_now(state)[mission][0] == "NEW")
            frozen = conv("cancel_proposal", {"conversation_id": cid, "mission_id": mission})[1]
            cancel = conv("cancel", {"command_key": "annuler-1", "conversation_id": cid, "mission_id": mission,
                                     "proposal_sha256": frozen["proposal_sha256"], "reason": "recette"})[1]
            check("C", "annulation demandée, non confirmée", cancel["stage"] == "request_received", cancel["stage"])

            # Tunnel loss: nothing changes on the server by itself; operator changes are seen after.
            before = missions_now(state)
            relay.close()
            try:
                request(pc, "GET", "/v1/health", token=token)
                lost = False
            except OSError:
                lost = True
            check("L", "coupure du tunnel : plus de réponse côté PC", lost)
            time.sleep(1)
            check("L", "aucune mission changée par la coupure", missions_now(state) == before)
            created = cli("-m", "eidolon_core", "--state", state, "create", "mission de recette synthétique")
            new_id = re.search(r"m-[0-9a-f]{32}", created.stdout).group(0)
            relay = Relay(port)
            pc = relay.port
            status, page = request(pc, "POST", "/v1/missions", {}, token=token)
            check("L", "retour du tunnel : état neuf, mission opérateur visible", status == 200 and new_id in json.dumps(page))
            after = missions_now(state)
            check("L", "seule la mission de l'opérateur s'ajoute", set(after) - set(before) == {new_id}
                  and {k: after[k] for k in before} == before)
        finally:
            relay.close()
            server.send_signal(signal.SIGTERM)
            code = server.wait(timeout=10)
        check("S7", "arrêt du serveur sur SIGTERM", code in (0, -signal.SIGTERM), code)

        # S7: restart; old receipts are found, never resent.
        server, port = start(state, token_file, profiles)
        SERVER_PORT["port"] = port
        relay = Relay(port)
        try:
            pc = relay.port
            conv = lambda route, body: request(pc, "POST", "/v1/conversations/" + route, body, token=key)
            old = conv("receipt", {"command_key": "valider-1"})[1]
            check("R", "reçu ancien de validation retrouvé", old["status"] == "FOUND"
                  and old["receipt"]["mission_id"] == mission)
            old_cancel = conv("cancel_receipt", {"command_key": "annuler-1", "conversation_id": cid, "mission_id": mission})[1]
            check("R", "reçu ancien d'annulation retrouvé, sans renvoi", old_cancel["status"] == "FOUND"
                  and old_cancel["authorizes_resend"] is False, old_cancel["stage"])
            status, looked = request(pc, "POST", "/v1/command-receipt",
                                     {"store_id": opened["store_id"], "client_id": "pc-toytoy",
                                      "command_key": "annuler-1", "mission_id": mission}, token=token)
            check("R", "même reçu lisible par l'API de lecture", status == 200 and json.dumps(looked).count("annuler-1") >= 1,
                  status)
            again = conv("submit", sub)[1]
            check("R", "même validation renvoyée : même reçu, aucune 2e mission", again.get("mission_id") == mission
                  and len(missions_now(state)) == len(after))
        finally:
            relay.close()
            server.send_signal(signal.SIGTERM)
            code = server.wait(timeout=10)
        # S8: stop; nothing left listening, storage intact.
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            closed = False
        except OSError:
            closed = True
        check("S8", "arrêt : port fermé", code in (0, -signal.SIGTERM) and closed, code)
        db = sqlite3.connect(os.path.join(state, "missions.sqlite3"))
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        db.close()
        store_state = json.loads(cli("-m", "eidolon_core.conversation_api", "--state", state, "inspect-store",
                                     ok=False).stdout)
        check("S8", "bases intactes après arrêt", integrity == "ok" and store_state["integrity"] == "ok"
              and store_state["state"] == "CURRENT")
        check("S8", "aucune clé ni jeton dans les sorties", key not in json.dumps(CHECKS) and token not in json.dumps(CHECKS))

    passed = sum(c["ok"] for c in CHECKS)
    print(json.dumps({"passed": passed, "total": len(CHECKS), "checks": CHECKS}, ensure_ascii=False, indent=1))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
