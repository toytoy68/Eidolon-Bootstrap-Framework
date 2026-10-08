# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_server_logo.py
# Description : Serveur patché (http_api-logo.patch) : logo optionnel, servi à l'identique, borné, lien refusé (C-TASK-G078)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probe_server_logo.py <patched src> <eidolon-core>  — temporary folders, loopback, synthetic Store."""
import hashlib, http.client, os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).resolve())); sys.dont_write_bytecode = True
from eidolon_core import http_api  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

CORE = Path(sys.argv[2]).resolve()
WEB = CORE / "desktop" / "connected"
TOKEN = "t" * 40


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, r.getheader("Content-Type"), body


def case(label, web):
    try:
        with http_api.ReadServer(state, TOKEN, port=0, web_root=web) as server:
            import threading
            t = threading.Thread(target=server.serve_forever, daemon=True); t.start()
            try:
                status, kind, body = get(server.server_address[1], "/eidolon-logo.png")
                index = get(server.server_address[1], "/")[0]
            finally:
                server.shutdown()
        same = hashlib.sha256(body).hexdigest() == hashlib.sha256((WEB / "eidolon-logo.png").read_bytes()).hexdigest()
        print(f"{label} : démarre ; / {index} ; logo {status} {kind} {len(body)} octets ; identique au fichier {same}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label} : {type(exc).__name__} {exc}")


with tempfile.TemporaryDirectory() as tmp:
    state = Path(tmp) / "state"
    Store(state)
    web_files = ("index.html", "app.js", "style.css")

    def root(name, logo=None):
        d = Path(tmp) / name
        d.mkdir()
        for f in web_files:
            shutil.copy(WEB / f, d / f)
        if logo == "copy":
            shutil.copy(WEB / "eidolon-logo.png", d / "eidolon-logo.png")
        elif logo == "symlink":
            os.symlink(WEB / "eidolon-logo.png", d / "eidolon-logo.png")
        elif logo == "dir":
            (d / "eidolon-logo.png").mkdir()
        elif logo == "large":
            (d / "eidolon-logo.png").write_bytes(b"\x89PNG" + b"0" * http_api.MAX_ASSET)
        elif logo == "dangling":
            os.symlink(d / "absent.png", d / "eidolon-logo.png")
        return d

    case("1 dossier du client (logo présent)", WEB)
    case("2 ancien dossier sans logo (comme l'archive bêta actuelle)", root("sans"))
    case("3 logo remplacé par un lien symbolique", root("lien", "symlink"))
    case("4 lien symbolique cassé", root("casse", "dangling"))
    case("5 logo remplacé par un dossier", root("dossier", "dir"))
    case("6 logo au-delà de MAX_ASSET", root("gros", "large"))
    case("7 sans --web-root", None)
