# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g071.py
# Description : Contre-revue de POST /v1/research-archives sur l'API réelle en loopback (C-TASK-G071)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g071.py <frozen eidolon-core/src>      (exit 1 if an assertion fails)

Real ReadServer on 127.0.0.1 (ephemeral port), Codex's research-archives beta fixture, raw
sockets where http.client would normalise headers. Every response body is collected and
scanned for private values (query texts, guard id, mission ids, local paths, raw export
fields). archive_page.read_catalog is wrapped only to COUNT catalog reads (authentication before read)."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True

from eidolon_core import archive_page  # noqa: E402
from eidolon_core.http_api import ReadServer, read_token  # noqa: E402

FAILED, BODIES = [], []
AUTHORITY = ("authenticity_verified", "live_journal_checked", "committed_status_known", "authorizes_execution",
             "request_sent")


def check(label, ok, detail=""):
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}", flush=True)
    if not ok:
        FAILED.append(label)


def fingerprint(root):
    out = []
    for p in sorted(Path(root).rglob("*")):
        st = p.lstat()
        out.append((str(p.relative_to(root)), st.st_size, oct(st.st_mode & 0o7777), st.st_mtime_ns,
                    hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.is_file() and not p.is_symlink() else "-"))
    return out


class Api:
    def __init__(self, fixture, archives=True):
        self.token = read_token(fixture / "read-token")
        self.server = ReadServer(fixture / "state", self.token, port=0,
                                 research_archives=fixture / "archives" if archives else None)
        self.port = self.server.server_address[1]
        self.reads = 0
        # Count real catalog reads (files opened), not calls to page(): page() validates its
        # arguments before reading anything.
        real = archive_page.read_catalog

        def counted(*a, **k):
            self.reads += 1
            return real(*a, **k)
        archive_page.read_catalog = counted
        self._restore = real
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def close(self):
        archive_page.read_catalog = self._restore
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def post(self, body, *, token=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else json.dumps(body).encode()
        h = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}
        if token is not False:
            h["Authorization"] = "Bearer " + (token or self.token)
        h.update(headers or {})
        try:
            c.request("POST", "/v1/research-archives", body=data, headers=h)
            r = c.getresponse()
            payload = r.read()
            BODIES.append(payload)
            return r.status, json.loads(payload), dict(r.getheaders())
        finally:
            c.close()

    def raw(self, request):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            s.sendall(request)
            chunks = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                chunks.append(b)
        finally:
            s.close()
        data = b"".join(chunks)
        head, _, body = data.partition(b"\r\n\r\n")
        BODIES.append(body)
        status = int(head.split()[1]) if head else 0
        return status, json.loads(body) if body else None


def code(result):
    status, body = result[0], result[1]
    return f"{status} {body.get('error') or body.get('status')}" if body else str(status)


def fixture(root, name):
    out = root / name
    r = subprocess.run([sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(out), "--profile",
                        "research-archives"], env=dict(os.environ, PYTHONPATH=SRC), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out


def private_values(fx):
    out = [str(fx), str(fx / "archives")]
    out += [s["mission_id"] for s in json.loads((fx / "manifest.json").read_text())["scenarios"]]
    for p in (fx / "archives").glob("research-archive-*.json"):
        meta = json.loads(p.read_bytes())
        out.append(meta["guard_id"])
        for run in meta["runs"]:
            if run["cleaned_query"]:
                out.append(json.loads(run["cleaned_query"])["text"])
            out.append(run["id"])
    return out


def auth_and_headers(api, fx):
    print("== 1. authentification avant lecture, Host/Origin, corps strict")
    before = api.reads
    cases = [("sans Authorization", dict(token=False)), ("mauvais jeton", dict(token="x" * 43)),
             ("schéma « bearer » en minuscules", dict(token=False, headers={"Authorization": "bearer " + api.token}))]
    for name, kw in cases:
        r = api.post({"limit": 1}, **kw)
        check(f"{name} → 401, catalogue non lu", r[0] == 401 and api.reads == before, code(r))
    r = api.raw(b"POST /v1/research-archives HTTP/1.0\r\nHost: 127.0.0.1:%d\r\nAuthorization: Bearer %s\r\n"
                b"Authorization: Bearer %s\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
                % (api.port, api.token.encode(), api.token.encode()))
    check("deux en-têtes Authorization → 401", r[0] == 401 and api.reads == before, code(r))
    big = b"{" + b" " * 9000 + b"}"
    r = api.post(None, token=False, raw=big)
    check("corps de 9 Kio sans jeton → refusé avant lecture", r[0] in (401, 413) and api.reads == before, code(r))
    for name, headers, want in (("Host étranger", {"Host": "evil.example:80"}, 403),
                                ("Origin étrangère", {"Origin": "http://evil.example"}, 403),
                                ("Origin null", {"Origin": "null"}, 403),
                                ("Host localhost du même port", {"Host": f"localhost:{api.port}"}, 200)):
        r = api.post({"limit": 1}, headers=headers)
        check(f"{name} → {want}", r[0] == want, code(r))
    r = api.raw(b"POST /v1/research-archives HTTP/1.0\r\nAuthorization: Bearer %s\r\nContent-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}" % api.token.encode())
    check("Host absent → 403", r[0] == 403, code(r))
    reads = api.reads
    for name, raw, want in (("JSON invalide", b"{", "INVALID_JSON"), ("clé dupliquée", b'{"limit":1,"limit":2}', "INVALID_JSON"),
                            ("tableau", b"[]", "INVALID_JSON"), ("limit 0", b'{"limit":0}', "INVALID_PAGE_LIMIT"),
                            ("limit 101", b'{"limit":101}', "INVALID_PAGE_LIMIT"), ("limit true", b'{"limit":true}', "INVALID_PAGE_LIMIT"),
                            ("limit \"5\"", b'{"limit":"5"}', "INVALID_PAGE_LIMIT"), ("limit 1.0", b'{"limit":1.0}', "INVALID_PAGE_LIMIT"),
                            ("champ inconnu", b'{"limit":1,"path":"/etc"}', "UNKNOWN_FIELD"),
                            ("curseur chaîne", b'{"cursor":"x"}', "INVALID_ARCHIVE_CURSOR"),
                            ("curseur after_index 0", json.dumps({"cursor": {"version": 1, "store_id": "s-" + "0" * 32,
                             "catalog_sha256": "0" * 64, "after_index": 0}}).encode(), "INVALID_ARCHIVE_CURSOR")):
        r = api.post(None, raw=raw)
        check(f"{name} → 400 {want}, catalogue non lu", r[0] == 400 and r[1]["error"] == want and api.reads == reads, code(r))
    r = api.post({"limit": 1}, headers={"Content-Type": "text/plain"})
    check("Content-Type text/plain → 415", r[0] == 415, code(r))
    r = api.raw(b"POST /v1/research-archives HTTP/1.0\r\nHost: 127.0.0.1:%d\r\nAuthorization: Bearer %s\r\n"
                b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n" % (api.port, api.token.encode()))
    check("Transfer-Encoding chunked → 400", r[0] == 400, code(r))
    t0 = time.monotonic()
    r = api.raw(b"POST /v1/research-archives HTTP/1.0\r\nHost: 127.0.0.1:%d\r\nAuthorization: Bearer %s\r\n"
                b"Content-Type: application/json\r\nContent-Length: 50\r\n\r\n{\"limit\":1}" % (api.port, api.token.encode()))
    check("corps plus court qu'annoncé → refus borné", r[0] in (400, 408), f"{code(r)} en {time.monotonic() - t0:.1f} s")
    r = api.raw(b"GET /v1/research-archives HTTP/1.0\r\nHost: 127.0.0.1:%d\r\nAuthorization: Bearer %s\r\n\r\n"
                % (api.port, api.token.encode()))
    check("GET sur la route → 404 (aucune lecture par GET)", r[0] == 404, code(r))
    r = api.raw(b"GET /research-archive-000001.json HTTP/1.0\r\nHost: 127.0.0.1:%d\r\nAuthorization: Bearer %s\r\n\r\n"
                % (api.port, api.token.encode()))
    check("export brut par son nom → 404", r[0] == 404, code(r))


def pagination(api, fx):
    print("== 2. pagination exhaustive, curseurs périmés ou d'un autre Store")
    for limit in (1, 2, 100):
        seen, cursor, pages = [], None, 0
        while True:
            body = {"limit": limit} if cursor is None else {"limit": limit, "cursor": cursor}
            status, page, headers = api.post(body)
            pages += 1
            if status != 200 or pages > 10:
                break
            seen += [i["index"] for i in page["items"]]
            if not page["has_more"]:
                break
            cursor = page["next_cursor"]
        check(f"limit {limit} : toutes les archives une fois, dans l'ordre", seen == [1, 2, 3] and status == 200,
              f"{pages} page(s) ; indices {seen}")
    status, page, headers = api.post({"limit": 1})
    check("garanties : cohérence vraie, champs d'autorité faux, en-têtes de sécurité",
          page["consistency_verified"] is True and all(page[k] is False for k in AUTHORITY)
          and headers.get("Cache-Control") == "no-store" and "default-src 'none'" in headers.get("Content-Security-Policy", ""))
    first = page["next_cursor"]
    other = dict(first, store_id="s-" + "f" * 32)
    r = api.post({"limit": 1, "cursor": other})
    check("curseur d'un autre Store → RESET STORE_CHANGED, aucun élément", r[0] == 200 and r[1]["status"] == "RESET_REQUIRED"
          and r[1]["reason"] == "STORE_CHANGED" and r[1]["items"] == [] and r[1]["next_cursor"] is None, code(r))
    forged = dict(first, catalog_sha256="e" * 64)
    r = api.post({"limit": 1, "cursor": forged})
    check("curseur d'un catalogue inventé → RESET CATALOG_CHANGED", r[1].get("reason") == "CATALOG_CHANGED", code(r))
    r = api.post({"limit": 1, "cursor": dict(first, after_index=3)})
    check("curseur au-delà de la fin → 400", r[0] == 400 and r[1]["error"] == "INVALID_ARCHIVE_CURSOR", code(r))
    archives = fx / "archives"
    moved = fx / "moved.json"
    os.rename(archives / "research-archive-000003.json", moved)
    r = api.post({"limit": 1, "cursor": first})
    check("catalogue changé entre deux pages → RESET CATALOG_CHANGED, aucun mélange",
          r[1].get("status") == "RESET_REQUIRED" and r[1].get("reason") == "CATALOG_CHANGED" and r[1]["items"] == [], code(r))
    os.rename(moved, archives / "research-archive-000003.json")
    r = api.post({"limit": 1, "cursor": first})
    check("catalogue restauré à l'identique → le curseur redevient valide (même empreinte)",
          r[0] == 200 and [i["index"] for i in r[1]["items"]] == [2], code(r))


def files(api, fx):
    print("== 3. fichiers privés, liens, FIFO, bornes de lecture")
    archives = fx / "archives"
    first = archives / "research-archive-000001.json"

    def attempt(name, damage, repair, want="ARCHIVES_UNAVAILABLE"):
        damage()
        t0 = time.monotonic()
        try:
            r = api.post({"limit": 3})
        finally:
            repair()
        check(f"{name} → 503 {want}, aucune page", r[0] == 503 and r[1]["error"] == want and "items" not in r[1],
              f"{code(r)} en {time.monotonic() - t0:.2f} s")
    attempt("export en 0644", lambda: first.chmod(0o644), lambda: first.chmod(0o600))
    saved = fx / "saved.json"
    attempt("export remplacé par un lien symbolique", lambda: (os.rename(first, saved), os.symlink(saved, first)),
            lambda: (os.unlink(first), os.rename(saved, first)))
    fifo = archives / "research-archive-000004.json"
    attempt("FIFO research-archive-000004.json (sans blocage)", lambda: os.mkfifo(fifo, 0o600), lambda: os.unlink(fifo))
    partial = archives / "x.partial"
    attempt(".partial présent", lambda: partial.write_bytes(b""), lambda: partial.unlink())
    attempt("dossier en 0755", lambda: archives.chmod(0o755), lambda: archives.chmod(0o700))
    big = archives / "research-archive-000004.json"

    def sparse():
        with open(big, "wb") as f:
            f.truncate(16 * 1024 * 1024 + 1)
        big.chmod(0o600)
    attempt("export creux de 16 Mio + 1", sparse, lambda: big.unlink())
    with patch.object(archive_page, "READ_BUDGET_SECONDS", 1e-9):
        r = api.post({"limit": 1})
    check("budget de lecture épuisé → 503 ARCHIVES_UNAVAILABLE", r[0] == 503 and r[1]["error"] == "ARCHIVES_UNAVAILABLE", code(r))
    hidden = fx / "hidden-archives"
    os.rename(archives, hidden)
    r = api.post({"limit": 1})
    exists = archives.exists()
    os.rename(hidden, archives)
    check("dossier supprimé après démarrage → 503, non recréé", r[0] == 503 and not exists, code(r))


def capacity(api, fx):
    print("== 4. capacité saturée et lecture exclusive du catalogue")
    real = archive_page.read_catalog
    gate = threading.Event()

    def slow(*a, **k):
        gate.wait(5)
        return real(*a, **k)
    results = []
    with patch.object(archive_page, "read_catalog", slow):
        t = threading.Thread(target=lambda: results.append(api.post({"limit": 1})))
        t.start()
        time.sleep(0.3)
        second = api.post({"limit": 1})
        gate.set()
        t.join(10)
    check("deux lectures simultanées → la seconde reçoit 503 ARCHIVES_BUSY sans attendre",
          second[0] == 503 and second[1]["error"] == "ARCHIVES_BUSY" and results and results[0][0] == 200,
          f"{code(second)} ; première {code(results[0]) if results else '?'}")
    socks = []
    for _ in range(4):        # four connections that never finish their headers occupy every worker
        s = socket.create_connection(("127.0.0.1", api.port), timeout=10)
        s.sendall(b"POST /v1/research-archives HTTP/1.0\r\nHost: 127.0.0.1:%d\r\n" % api.port)
        socks.append(s)
    time.sleep(0.2)
    t0 = time.monotonic()
    r = api.post({"limit": 1})
    elapsed = time.monotonic() - t0
    for s in socks:
        s.close()
    check("serveur saturé (4 connexions lentes) → 503 BUSY immédiat", r[0] == 503 and r[1]["error"] == "BUSY",
          f"{code(r)} en {elapsed:.2f} s")
    time.sleep(3.5)
    check("après expiration des connexions lentes, le service reprend", api.post({"limit": 1})[0] == 200)


def main():
    print(f"Sources examinées : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g071-") as tmp:
        root = Path(tmp)
        fx = fixture(root, "fx")
        secrets = private_values(fx)
        api = Api(fx)
        try:
            state_before = fingerprint(fx / "state")
            archives_before = fingerprint(fx / "archives")
            auth_and_headers(api, fx)
            pagination(api, fx)
            check("aucune mutation du Store ni des archives par les lectures (sections 1–2)",
                  fingerprint(fx / "state") == state_before and fingerprint(fx / "archives") == archives_before)
            files(api, fx)
            check("archives remises à l'identique après chaque essai destructif (section 3)",
                  fingerprint(fx / "archives") == archives_before)
            capacity(api, fx)
        finally:
            api.close()
        off = Api(fixture(root, "fx2"), archives=False)
        try:
            r = off.post({"limit": 1})
            check("serveur sans --research-archives → 404 ARCHIVES_NOT_CONFIGURED", r[0] == 404
                  and r[1]["error"] == "ARCHIVES_NOT_CONFIGURED", code(r))
        finally:
            off.close()
        blob = b"\n".join(BODIES).decode("utf-8", "replace")
        leaks = [s[:12] for s in secrets if s and s in blob]
        check(f"aucune valeur privée dans les {len(BODIES)} réponses (requêtes, guard_id, missions, chemins, runs)",
              not leaks and '"runs"' not in blob and '"cleaned_query"' not in blob, str(leaks))
        bad = []
        for raw in BODIES:
            try:
                value = json.loads(raw)
            except ValueError:
                continue
            bad += [k for k in AUTHORITY if value.get(k) not in (None, False)]
        check("aucun champ d'autorité vrai dans aucune réponse", not bad, str(bad))
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
