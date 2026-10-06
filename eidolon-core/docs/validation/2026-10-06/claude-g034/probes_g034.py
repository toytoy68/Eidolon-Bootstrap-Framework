# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g034.py
# Description : Contre-revue de l'API HTTP C-009a sur sockets loopback réelles (C-TASK-G034)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""PYTHONPATH=<frozen tree>/eidolon-core/src python3 probes_g034.py
Builds synthetic states with the Core CLI of that tree in temporary folders, runs
ReadServer on 127.0.0.1:0, and sends raw HTTP bytes. No other host is contacted.
Every line prints the observed status/code; a final section scans for leaks."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time

from eidolon_core.http_api import ReadServer

PRIVATE = "texte privé synthétique G034 ne-pas-divulguer"
ANSWERS = []          # every raw response, scanned for leaks at the end


def cli(state, *args, profile=None):
    cmd = [sys.executable, "-m", "eidolon_core", "--state", str(state)] + (["--profile", profile] if profile else []) + list(args)
    out = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")).stdout
    return json.loads(out)


def make_state(root):
    state = Path(root) / "state"
    cli(state, "demo")
    fresh = cli(state, "create", PRIVATE)["id"]
    cli(state, "restart", "nas", profile="action-sim")
    return state, fresh


class Server:
    def __init__(self, state, token, web_root=None):
        self.server = ReadServer(state, token, port=0, web_root=web_root)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def raw(port, data, shut=True, timeout=8):
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as c:
        c.sendall(data)
        if shut:
            c.shutdown(socket.SHUT_WR)
        chunks = []
        try:
            while chunk := c.recv(65536):
                chunks.append(chunk)
        except (ConnectionResetError, socket.timeout):
            pass
    answer = b"".join(chunks)
    ANSWERS.append(answer)
    head, _, body = answer.partition(b"\r\n\r\n")
    status = head.split(b" ", 2)[1].decode() if head.startswith(b"HTTP/") else "-"
    try:
        code = json.loads(body).get("error") or "200-json"
    except (ValueError, AttributeError):
        code = f"{len(body)} octets"
    return status, code, head, body


def req(port, method, path, token=None, body=None, headers=None, host=None, version="HTTP/1.0", timeout=8):
    lines = [f"{method} {path} {version}"]
    if host is not False:
        lines.append(f"Host: {host or f'127.0.0.1:{port}'}")
    if token:
        lines.append(f"Authorization: Bearer {token}")
    for h in headers or []:
        lines.append(h)
    data = b""
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        if not any(h.lower().startswith("content-type") for h in headers or []):
            lines.append("Content-Type: application/json")
        if not any(h.lower().startswith("content-length") for h in headers or []):
            lines.append(f"Content-Length: {len(data)}")
    return raw(port, ("\r\n".join(lines) + "\r\n\r\n").encode() + data, timeout=timeout)


def show(label, result):
    print(f"{label}: {result[0]} {result[1]}")
    return result


def digest_tree(state):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(Path(state).iterdir()) if p.is_file()}


def main():
    tmp = tempfile.TemporaryDirectory()
    state, fresh = make_state(tmp.name)
    token = secrets.token_urlsafe(32)
    before = digest_tree(state)
    s = Server(state, token)
    p = s.port
    T = token
    print("== A. jeton")
    show("A1 sans Authorization", req(p, "GET", "/v1/health"))
    show("A2 jeton erroné", req(p, "GET", "/v1/health", token="x" * 43))
    show("A3 Authorization dupliquée (bon + bon)", req(p, "GET", "/v1/health", token=T, headers=[f"Authorization: Bearer {T}"]))
    show("A4 jeton dans l'URL", req(p, "GET", f"/v1/health?token={T}"))
    show("A5 schéma en minuscules 'bearer'", req(p, "GET", "/v1/health", headers=[f"Authorization: bearer {T}"]))
    show("A6 deux espaces après Bearer", req(p, "GET", "/v1/health", headers=[f"Authorization: Bearer  {T}"]))
    show("A7 jeton + octet nul", raw(p, f"GET /v1/health HTTP/1.0\r\nHost: 127.0.0.1:{p}\r\nAuthorization: Bearer {T}\x00\r\n\r\n".encode()))
    show("A8 jeton correct", req(p, "GET", "/v1/health", token=T))
    print("== B. Host / Origin")
    show("B1 sans Host", req(p, "GET", "/v1/health", token=T, host=False))
    show("B2 Host autre", req(p, "GET", "/v1/health", token=T, host="evil.example"))
    show("B3 Host dupliqué", req(p, "GET", "/v1/health", token=T, headers=[f"Host: 127.0.0.1:{p}"]))
    show("B4 Host LOCALHOST majuscules", req(p, "GET", "/v1/health", token=T, host=f"LOCALHOST:{p}"))
    show("B5 Host sans port", req(p, "GET", "/v1/health", token=T, host="127.0.0.1"))
    show("B6 Host [::1]", req(p, "GET", "/v1/health", token=T, host=f"[::1]:{p}"))
    show("B7 Origin null", req(p, "POST", "/v1/missions", token=T, body={}, headers=["Origin: null"]))
    show("B8 Origin autre", req(p, "POST", "/v1/missions", token=T, body={}, headers=["Origin: http://evil.example"]))
    show("B9 Origin https même hôte", req(p, "POST", "/v1/missions", token=T, body={}, headers=[f"Origin: https://127.0.0.1:{p}"]))
    show("B10 Origin dupliqué", req(p, "POST", "/v1/missions", token=T, body={}, headers=[f"Origin: http://127.0.0.1:{p}"] * 2))
    show("B11 Origin exact", req(p, "POST", "/v1/missions", token=T, body={}, headers=[f"Origin: http://127.0.0.1:{p}"]))
    show("B12 Host localhost + Origin 127.0.0.1", req(p, "POST", "/v1/missions", token=T, body={}, host=f"localhost:{p}", headers=[f"Origin: http://127.0.0.1:{p}"]))
    print("== C. URL")
    for path in ("/v1/health?x=1", "/v1/health/", "//v1/health", "/v1/%68ealth", "/../v1/health", "/v1/./health",
                 f"/v1/missions/{fresh.upper()}", f"/v1/missions/{fresh}/", f"http://127.0.0.1:{p}/v1/health", "/v1/health#f"):
        show(f"C GET {path}", req(p, "GET", path, token=T))
    show("C long chemin 70 000", req(p, "GET", "/v1/" + "a" * 70000, token=T))
    print("== D. JSON")
    for label, body in (("UTF-8 invalide", b'{"limit":\xff}'), ("clé dupliquée", b'{"limit":1,"limit":2}'),
                        ("NaN", b'{"limit":NaN}'), ("1e400", b'{"limit":1e400}'), ("profondeur 17", b'{"cursor":' + b'[' * 17 + b']' * 17 + b'}'),
                        ("tableau racine", b'[]'), ("champ inconnu", b'{"x":1}'), ("limit true", b'{"limit":true}'),
                        ("limit 0", b'{"limit":0}'), ("limit 101", b'{"limit":101}'), ("limit texte 5", b'{"limit":"5"}'),
                        ("limit 2.0", b'{"limit":2.0}'), ("surrogate isolé", b'{"limit":"\\ud800"}'), ("vide", b'')):
        show(f"D {label}", req(p, "POST", "/v1/missions", token=T, body=body))
    show("D poll sans curseur", req(p, "POST", f"/v1/missions/{fresh}/poll", token=T, body={}))
    show("D poll curseur d'une autre mission", req(p, "POST", f"/v1/missions/{fresh}/poll", token=T,
                                                    body={"cursor": {"version": 1, "store_id": "s-" + "0" * 32, "mission_id": "m-" + "0" * 32,
                                                                     "sequence": 1, "event_count": 1, "anchor_sha256": "0" * 64}}))
    print("== E. corps")
    t0 = time.monotonic()
    show("E1 tronqué (CL=50, 10 octets, fermeture écriture)", raw(p, f"POST /v1/missions HTTP/1.0\r\nHost: 127.0.0.1:{p}\r\nAuthorization: Bearer {T}\r\nContent-Type: application/json\r\nContent-Length: 50\r\n\r\n{{\"limit\":1".encode()))
    print(f"   durée {time.monotonic() - t0:.2f} s")
    show("E2 8193 octets", req(p, "POST", "/v1/missions", token=T, body=b" " * 8193))
    show("E3 octets en trop après CL", req(p, "POST", "/v1/missions", token=T, body=b'{}', headers=["Content-Length: 2"]))
    raw_extra = raw(p, f"POST /v1/missions HTTP/1.0\r\nHost: 127.0.0.1:{p}\r\nAuthorization: Bearer {T}\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{{}}GET /v1/health HTTP/1.0\r\n\r\n".encode())
    print(f"E4 requête collée après le corps : {raw_extra[0]} {raw_extra[1]} ; réponses HTTP dans le flux = {raw_extra[2].count(b'HTTP/') + raw_extra[3].count(b'HTTP/')}")
    show("E5 Content-Length dupliqué", req(p, "POST", "/v1/missions", token=T, body=b'{}', headers=["Content-Length: 2", "Content-Length: 2"]))
    show("E6 chunked", req(p, "POST", "/v1/missions", token=T, body=b'2\r\n{}\r\n0\r\n\r\n', headers=["Transfer-Encoding: chunked", "Content-Length: 0"]))
    show("E7 GET avec corps", req(p, "GET", "/v1/health", token=T, body=b'{}'))
    show("E8 Content-Length négatif", req(p, "POST", "/v1/missions", token=T, body=b'{}', headers=["Content-Length: -1"]))
    show("E9 type text/plain", req(p, "POST", "/v1/missions", token=T, body=b'{}', headers=["Content-Type: text/plain"]))
    show("E10 type JSON charset latin-1", req(p, "POST", "/v1/missions", token=T, body=b'{}', headers=["Content-Type: application/json; charset=latin-1"]))
    print("== F. méthodes")
    for method in ("PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "HEAD", "FOO", "get", "CONNECT"):
        show(f"F {method} avec jeton", req(p, method, "/v1/health", token=T))
    show("F OPTIONS préflight sans jeton", req(p, "OPTIONS", "/v1/missions", headers=["Origin: http://evil.example", "Access-Control-Request-Method: POST"]))
    print("== G. statique sans --web-root")
    for path in ("/", "/app.js", "/style.css", "/index.html", "/../state/missions.sqlite3"):
        show(f"G GET {path}", req(p, "GET", path))
    print("== H. garde de restauration ajoutée pendant l'exécution")
    marker = state / "RECOVERY-REVIEW-ONLY"
    marker.write_text("")
    show("H1 marqueur présent", req(p, "GET", "/v1/health", token=T))
    marker.unlink()
    show("H2 marqueur retiré", req(p, "GET", "/v1/health", token=T))
    mid = digest_tree(state)
    print(f"J1 fichiers d'état modifiés par les sections A à H (API seule) : {sorted(k for k in set(before) | set(mid) if before.get(k) != mid.get(k))}")
    print("== L. pagination / reset / poll après écriture d'une CLI distincte")
    _, _, _, b1 = req(p, "POST", "/v1/missions", token=T, body={"limit": 2})
    page1 = json.loads(b1)
    print(f"L1 page 1 : {len(page1['items'])} items, has_more={page1['has_more']}")
    _, _, _, snap = req(p, "GET", f"/v1/missions/{fresh}", token=T)
    cursor = json.loads(snap)["cursor"]
    cli(state, "create", "autre mission synthétique G034")
    _, _, _, b2 = req(p, "POST", "/v1/missions", token=T, body={"cursor": page1["next_cursor"], "limit": 2})
    page2 = json.loads(b2)
    print(f"L2 page 2 après création par la CLI : {page2['status']} {page2.get('reason')} items={len(page2['items'])}")
    cli(state, "cancel", fresh)
    _, _, _, b3 = req(p, "POST", f"/v1/missions/{fresh}/poll", token=T, body={"cursor": cursor})
    poll = json.loads(b3)
    print(f"L3 poll après annulation par la CLI : {poll['status']} événements={[e['kind'] for e in poll['events']]} statut={poll['snapshot']['mission']['status']}")
    print("== M. client lent (limite connue : serveur mono-requête)")
    slow = socket.create_connection(("127.0.0.1", p))
    slow.sendall(b"GET /v1/health HTTP/1.0\r\n")
    def trickle():
        for _ in range(4):
            time.sleep(2)
            try:
                slow.sendall(b"X-A: b\r\n")
            except OSError:
                return
    th = threading.Thread(target=trickle)
    th.start()
    time.sleep(0.2)
    t0 = time.monotonic()
    r = req(p, "GET", "/v1/health", token=T)
    print(f"M1 requête légitime pendant un client qui envoie un en-tête toutes les 2 s : {r[0]} après {time.monotonic() - t0:.1f} s")
    th.join()
    slow.close()
    time.sleep(3.5)
    idle = socket.create_connection(("127.0.0.1", p))   # like a browser preconnect: opened, nothing sent
    time.sleep(0.2)
    t0 = time.monotonic()
    r = req(p, "GET", "/v1/health", token=T, timeout=10)
    print(f"M2 requête légitime derrière une connexion ouverte sans rien envoyer : {r[0]} après {time.monotonic() - t0:.1f} s")
    idle.close()
    s.close()
    print("== I. base absente / corrompue")
    for label, prepare in (("absente", lambda d: None), ("corrompue", lambda d: (d / "missions.sqlite3").write_bytes(b"pas une base sqlite" * 10))):
        d = Path(tempfile.mkdtemp(dir=tmp.name))
        prepare(d)
        try:
            ReadServer(d, token, port=0).server_close()
            print(f"I démarrage base {label} : ACCEPTÉ")
        except Exception as exc:
            print(f"I démarrage base {label} : refusé {type(exc).__name__}: {str(exc)[:60]} ; fichiers={sorted(x.name for x in d.iterdir())}")
    s2 = Server(state, token)
    db = state / "missions.sqlite3"
    saved = db.read_bytes()
    db.write_bytes(b"\x00" * 4096)
    show("I3 base remplacée par des zéros pendant l'exécution", req(s2.port, "GET", f"/v1/missions/{fresh}", token=T))
    db.write_bytes(saved)
    s2.close()
    print("== J. mutation")
    after = digest_tree(state)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    print(f"J2 fichiers modifiés au total, CLI de L comprise : {changed}")
    print("== K. fuites dans toutes les réponses")
    blob = b"\n".join(ANSWERS)
    for label, needle in (("jeton", token.encode()), ("chemin d'état", str(state).encode()), ("texte privé de la requête", PRIVATE.encode()),
                          ("Traceback", b"Traceback"), ("sqlite", b"sqlite"), ("SQL", b"SELECT")):
        print(f"K {label} : {'PRÉSENT' if needle in blob else 'absent'}")
    print(f"K réponses examinées : {len(ANSWERS)}")
    print("== N. processus CLI : sorties")
    tokfile = Path(tmp.name) / "tok"
    fd = os.open(tokfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, (token + "\n").encode())
    os.close(fd)
    proc = subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", str(state), "--token-file", str(tokfile), "--port", "0"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.5)
    proc.send_signal(2)
    out, err = proc.communicate(timeout=10)
    print(f"N code={proc.returncode} jeton dans stdout/stderr={'OUI' if token in out + err else 'non'} ; stdout={len(out)} car. stderr={len(err)} car.")
    tmp.cleanup()


if __name__ == "__main__":
    main()
