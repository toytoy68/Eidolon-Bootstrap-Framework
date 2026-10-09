# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g083.py
# Description : Recette du logo et des assets du paquet bêta : présence, empreintes, absence, taille, lien (C-TASK-G083)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with the INSTALLED package (env -u PYTHONPATH <venv>/bin/python, from /):
    python probes_g083.py <archive.tar.gz> <extracted archive root> <repository root> <browser script>

Loopback and temporary copies only; the archive and the repository are only read. Prints one JSON report."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ARCHIVE, ROOT, REPO, BROWSER = (Path(a) for a in sys.argv[1:5])
PY = sys.executable
LOGO = "eidolon-core/desktop/connected/eidolon-logo.png"
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})


def sha(data):
    return hashlib.sha256(data).hexdigest()


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        c.close()


def start(web, token_file, state):
    p = subprocess.Popen([PY, "-m", "eidolon_core.http_api", "--state", str(state), "--token-file", str(token_file),
                          "--port", "0", "--web-root", str(web)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        line = p.stdout.readline()
        m = re.search(r"http://127\.0\.0\.1:(\d+)", line)
        if m:
            return p, int(m.group(1))
        if p.poll() is not None:
            break
    p.kill()
    return p, None


def preflight(web, token_file, state):
    done = subprocess.run([PY, "-m", "eidolon_core.http_api", "--state", str(state), "--token-file", str(token_file),
                           "--port", "8765", "--web-root", str(web), "--check"], capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout


def main():
    # 1. In the archive, byte for byte the committed file, and listed in the manifest.
    manifest = json.loads((ROOT / "MANIFEST.json").read_text())
    commit = manifest["commit"]
    blob = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{LOGO}"], capture_output=True, check=True).stdout
    packed = (ROOT / LOGO).read_bytes()
    entry = next((f for f in manifest["files"] if f["path"] == LOGO), None)
    check("logo client présent dans l'archive, identique au commit", sha(packed) == sha(blob), sha(packed))
    check("logo listé au manifeste avec la même empreinte", entry is not None and entry["sha256"] == sha(blob), entry)
    with tarfile.open(ARCHIVE) as tar:
        names = tar.getnames()
    absent = [p for p in ("eidolon-core/assets/branding/eidolon-logo.png", "eidolon-core/assets/branding/LOGO.md",
                          "eidolon-core/desktop/tauri/icons/icon.ico") if not any(n.endswith(p) for n in names)]
    check("originaux canoniques et icône Windows hors de l'archive (constat)", len(absent) == 3, absent)
    web_files = (ROOT / "eidolon-core/desktop/connected")
    external = [m for f in ("index.html", "app.js", "style.css")
                for m in re.findall(r"https?://(?!127\.0\.0\.1)[A-Za-z0-9.-]+", (web_files / f).read_text())]
    check("aucune adresse distante dans la page", not external, external)

    with tempfile.TemporaryDirectory(prefix="eidolon-g083-") as tmp:
        tmp = Path(tmp)
        state, token_file = tmp / "state", tmp / "read-token"
        subprocess.run([PY, "-m", "eidolon_core", "--state", str(state), "demo"], capture_output=True, check=True)
        subprocess.run([PY, "-m", "eidolon_core.access_token", "--output", str(token_file)], capture_output=True, check=True)

        # 2. Served from the installed package with the archive's web root.
        server, port = start(web_files, token_file, state)
        try:
            status, headers, body = get(port, "/eidolon-logo.png")
            check("logo servi après installation, même empreinte", status == 200 and sha(body) == sha(blob)
                  and headers.get("Content-Type") == "image/png", status)
            check("logo servi sans cache ni interprétation", headers.get("Cache-Control") == "no-store"
                  and headers.get("X-Content-Type-Options") == "nosniff"
                  and "img-src 'self'" in headers.get("Content-Security-Policy", ""))
            browser = subprocess.run(["node", str(BROWSER), f"http://127.0.0.1:{port}/", "present"],
                                     capture_output=True, text=True, timeout=120)
            check("Chromium : logo affiché, nom texte masqué", browser.returncode == 0, browser.stdout.strip()[-200:])
        finally:
            server.terminate(); server.wait(10)

        # 3. Missing logo: a minimal web root stays valid, the text name stays.
        missing = tmp / "web-missing"
        shutil.copytree(web_files, missing)
        (missing / "eidolon-logo.png").unlink()
        code, _ = preflight(missing, token_file, state)
        server, port = start(missing, token_file, state)
        try:
            check("logo absent : diagnostic et démarrage acceptés", code == 0 and port is not None, code)
            check("logo absent : 404, page servie", get(port, "/eidolon-logo.png")[0] == 404 and get(port, "/")[0] == 200)
            browser = subprocess.run(["node", str(BROWSER), f"http://127.0.0.1:{port}/", "missing"],
                                     capture_output=True, text=True, timeout=120)
            check("Chromium : logo absent, nom texte visible", browser.returncode == 0, browser.stdout.strip()[-200:])
        finally:
            if port:
                server.terminate(); server.wait(10)

        # 4. Size bound: exactly MAX_ASSET accepted, one byte more refused before serving anything.
        from eidolon_core.http_api import MAX_ASSET
        for label, size, expected in (("= borne", MAX_ASSET, True), ("borne + 1", MAX_ASSET + 1, False)):
            web = tmp / f"web-{size}"
            shutil.copytree(web_files, web)
            (web / "eidolon-logo.png").write_bytes(blob + b"\0" * (size - len(blob)))
            code, out = preflight(web, token_file, state)
            server, port = start(web, token_file, state)
            if port:
                server.terminate(); server.wait(10)
            check(f"logo de taille {label} : {'accepté' if expected else 'refusé au démarrage'}",
                  (code == 0 and port is not None) if expected else (code != 0 and port is None), f"{code} {size}")

        # 5. A link instead of the file is refused.
        linked = tmp / "web-link"
        shutil.copytree(web_files, linked)
        (linked / "eidolon-logo.png").unlink()
        os.symlink(web_files / "eidolon-logo.png", linked / "eidolon-logo.png")
        code, _ = preflight(linked, token_file, state)
        server, port = start(linked, token_file, state)
        if port:
            server.terminate(); server.wait(10)
        check("logo en lien symbolique : refusé", code != 0 and port is None, code)

    passed = sum(c["ok"] for c in CHECKS)
    print(json.dumps({"commit": commit, "passed": passed, "total": len(CHECKS), "checks": CHECKS},
                     ensure_ascii=False, indent=1))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
