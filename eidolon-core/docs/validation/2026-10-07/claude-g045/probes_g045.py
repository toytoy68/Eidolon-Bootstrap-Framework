# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g045.py
# Description : Contre-revue saturation (503 BUSY) et budget SQL sur cible figée (C-TASK-G045)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""PYTHONPATH=<frozen d9265fa>/eidolon-core/src python3 probes_g045.py
Synthetic state (C-009g fixture, created with the frozen code), server in a separate process on
127.0.0.1:0, raw sockets. Nothing else is contacted; everything temporary is removed."""
import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from eidolon_core.http_api import ReadOnlyStore, ReadServer

HERE = Path(__file__).resolve().parent
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def start(state, token_file, variant="original"):
    proc = subprocess.Popen([sys.executable, str(HERE / "variant_server.py"), str(state), str(token_file), variant],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=ENV)
    port = int(proc.stdout.readline().split()[1])
    return proc, port


def get(port, token, path, timeout=10, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        headers = {"Authorization": "Bearer " + token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request("POST" if body is not None else "GET", path, body=body, headers=headers)
        r = c.getresponse()
        return r.status, r.read()
    except (ConnectionError, OSError) as exc:
        return type(exc).__name__, b""
    finally:
        c.close()


def slots(port, token, path, clients, n=100):
    def worker(_):
        return [get(port, token, path)[0] for _ in range(n)]
    with concurrent.futures.ThreadPoolExecutor(clients) as pool:
        statuses = [s for batch in pool.map(worker, range(clients)) for s in batch]
    kinds = {}
    for s in statuses:
        kinds[str(s)] = kinds.get(str(s), 0) + 1
    return kinds


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g045-") as root:
        fx = Path(root) / "fx"
        subprocess.run([sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(fx)], check=True, env=ENV, capture_output=True)
        token = (fx / "read-token").read_text().strip()
        manifest = json.loads((fx / "manifest.json").read_text())
        mission = manifest["scenarios"][0]["mission_id"]
        path = f"/v1/missions/{mission}"
        proc, port = start(fx / "state", fx / "read-token")
        try:
            print("== S1 clients séquentiels et simultanés (100 snapshots chacun)")
            for clients in (1, 2, 3, 4, 5):
                print(f"S1 {clients} client(s) : {slots(port, token, path, clients)}")
            print("== S2 réponse BUSY : identique quelle que soit la requête, avant authentification")
            idle = [socket.create_connection(("127.0.0.1", port)) for _ in range(4)]
            time.sleep(0.2)
            bodies = set()
            for req in (b"GET /v1/health HTTP/1.0\r\n\r\n", b"GET / HTTP/1.0\r\nAuthorization: Bearer " + token.encode() + b"\r\n\r\n",
                        b"\x00\x01garbage", b""):
                with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
                    try:
                        s.sendall(req)
                        data = b""
                        while chunk := s.recv(4096):
                            data += chunk
                    except ConnectionError as exc:
                        data = type(exc).__name__.encode()
                bodies.add(data)
            print(f"S2 réponses distinctes : {len(bodies)} ; jeton présent : {any(token.encode() in b for b in bodies)}")
            print("S2 réponse : " + next(iter(bodies)).decode(errors="replace").replace("\r\n", " | "))
            print("== S3 POST de 8 Ko pendant la saturation (corps non lu par le serveur)")
            big = json.dumps({"limit": 20, "pad": "x" * 8000})
            kinds = {}
            for _ in range(50):
                st, _ = get(port, token, "/v1/missions", body=big)
                kinds[str(st)] = kinds.get(str(st), 0) + 1
            print(f"S3 résultats : {kinds}")
            print("== S4 retour au service après libération")
            for s in idle:
                s.close()
            t0 = time.perf_counter()
            st, _ = get(port, token, "/v1/health")
            print(f"S4 première requête après fermeture des 4 connexions : {st} en {1000 * (time.perf_counter() - t0):.0f} ms")
            idle = [socket.create_connection(("127.0.0.1", port)) for _ in range(4)]
            t0 = time.perf_counter()
            while get(port, token, "/v1/health")[0] != 200:
                time.sleep(0.1)
            print(f"S4 connexions muettes laissées ouvertes : service revenu après {time.perf_counter() - t0:.1f} s (délai d'inactivité 3 s)")
            for s in idle:
                s.close()
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        print("== S5 budget SQL (2 s, gestionnaire de progression SQLite)")
        store = ReadOnlyStore(fx / "state")
        t0 = time.perf_counter()
        try:
            with store.connection() as db:
                db.execute("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c").fetchone()
            print("S5 requête sans fin : NON interrompue")
        except sqlite3.OperationalError as exc:
            print(f"S5 requête sans fin interrompue : {exc} après {time.perf_counter() - t0:.2f} s")
        t0 = time.perf_counter()
        try:
            with store.connection() as db:
                time.sleep(2.2)                      # Python work inside the connection: not counted by SQLite
                db.execute("SELECT count(*) FROM missions").fetchone()
            print(f"S5 travail Python de 2,2 s puis requête courte : interrompue ? non ({time.perf_counter() - t0:.2f} s)")
        except sqlite3.OperationalError as exc:
            print(f"S5 travail Python de 2,2 s puis requête courte : refusée ({exc}) après {time.perf_counter() - t0:.2f} s")
        hold = sqlite3.connect(fx / "state" / "missions.sqlite3", isolation_level=None, check_same_thread=False)
        hold.execute("BEGIN EXCLUSIVE")
        threading.Timer(1.5, lambda: (hold.execute("ROLLBACK"), hold.close())).start()
        t0 = time.perf_counter()
        try:
            with store.connection() as db:
                db.execute("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c").fetchone()
        except sqlite3.OperationalError as exc:
            print(f"S5 verrou 1,5 s puis requête sans fin : {exc} après {time.perf_counter() - t0:.2f} s (attente du verrou + budget)")
        counts = {"n": 0}
        original = ReadOnlyStore.connection

        def counting(self):
            counts["n"] += 1
            return original(self)
        ReadOnlyStore.connection = counting
        server = ReadServer(fx / "state", token, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for label, p, body in (("health", "/v1/health", None), ("liste", "/v1/missions", "{}"), ("snapshot", path, None),
                               ("reçu", "/v1/command-receipt", json.dumps(manifest["receipt_queries"][0]))):
            counts["n"] = 0
            get(server.server_port, token, p, body=body)
            print(f"S5 connexions SQLite (donc budgets de 2 s) par requête {label} : {counts['n']}")
        server.shutdown()
        server.server_close()
        ReadOnlyStore.connection = original
        print("== S6 variante proposée : libérer la place AVANT de fermer la connexion")
        for variant in ("original", "release-first"):
            proc, port = start(fx / "state", fx / "read-token", variant)
            try:
                print(f"S6 {variant} : " + " ; ".join(f"{c} clients {slots(port, token, path, c)}" for c in (3, 4, 5)))
            finally:
                proc.terminate()
                proc.wait(timeout=10)


if __name__ == "__main__":
    main()
