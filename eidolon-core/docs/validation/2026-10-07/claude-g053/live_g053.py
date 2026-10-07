# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : live_g053.py
# Description : Lancement Linux de la coquille Tauri sous Xvfb, loopback seulement (C-TASK-G053)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""cd eidolon-core && PYTHONPATH=src xvfb-run -a python3 <this file> <binary> <output dir>

L1: the real Core read server (synthetic beta fixture) on 127.0.0.1; the shell must load the
Core-served client. L2: a probe page on 127.0.0.1 that tries IPC, navigation, window.open,
an iframe and a cross-origin fetch towards a second loopback server, which records any hit.
Only processes started here are stopped, by their own PID."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import random
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote

from eidolon_core.beta_fixture import create
from eidolon_core.http_api import ReadServer

BINARY, OUT = Path(sys.argv[1]), Path(sys.argv[2])
WEB_ROOT = Path("desktop/connected").resolve()


def serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def launch(port, extra_env=None, seconds=8.0, shot=None, token=None):
    env = dict(os.environ, **(extra_env or {}))
    proc = subprocess.Popen([str(BINARY), "--port", str(port)], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    time.sleep(seconds)
    if token:
        # Type the synthetic token like an operator would (field, then the "Se connecter" button).
        for cmd in (["mousemove", "300", "80", "click", "1"], ["type", "--delay", "5", token],
                    ["mousemove", "510", "80", "click", "1"]):
            subprocess.run(["xdotool", *cmd], check=False, timeout=60)
        time.sleep(4)
        subprocess.run(["xdotool", "mousemove", "230", "330", "click", "1"], check=False, timeout=30)
        time.sleep(3)
    if shot:
        subprocess.run(["import", "-window", "root", str(shot)], check=False, timeout=30)
    alive = proc.poll() is None
    proc.terminate()
    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return alive, err


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("== L0. arguments refusés avant toute fenêtre")
    for args in (["--port", "80"], ["--port", "abc"], ["--url", "http://evil.example/"]):
        p = subprocess.run([str(BINARY), *args], capture_output=True, text=True, timeout=30)
        print(f"L0 {' '.join(args)} : code {p.returncode} ; {p.stderr.strip()}")

    with tempfile.TemporaryDirectory(prefix="eidolon-g053-") as tmp:
        print("== L1. vrai serveur Core (jeu bêta synthétique) sur 127.0.0.1")
        report = create(str(Path(tmp) / "demo"))
        state = Path(tmp) / "demo" / "state"
        # The server accepts any valid token; lowercase + digits only, because typing through
        # xdotool on a bare Xvfb keymap mangles upper case and "_"/"-" (seen on the first run).
        token = "".join(random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(43))
        hits = []
        core = ReadServer(str(state), token, port=0, web_root=str(WEB_ROOT))
        core.RequestHandlerClass.log_message = lambda self, fmt, *a: hits.append(
            (self.requestline.split(" ")[1], self.headers.get("Host"), self.headers.get("Origin")))
        serve(core)
        port = core.server_port
        alive, err = launch(port, shot=OUT / "l1-core-client.png", token=token)
        core.shutdown()
        core.server_close()
        print(f"L1 fixture {report['status']} ; fenêtre vivante après 8 s : {alive} ; requêtes reçues par Core : "
              f"{sorted({h[0] for h in hits})}")
        print(f"L1 Host vus : {sorted({h[1] for h in hits})} ; Origin vus : {sorted({str(h[2]) for h in hits})}")
        print(f"L1 jeton présent dans une URL demandée : {any(token in h[0] for h in hits)} ; stderr : {err.strip()[:200]!r}")

        print("== L2. page sonde : IPC, navigation, nouvelle fenêtre, iframe, fetch croisé")
        other_hits, reports = [], []

        class Other(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                other_hits.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"<p>autre origine</p>")

        other = serve(ThreadingHTTPServer(("127.0.0.1", 0), Other))
        page = """<!doctype html><title>sonde G053</title><p id=s>sonde</p><script>
const B = "http://127.0.0.1:%d";
const r = {internals: typeof window.__TAURI_INTERNALS__, tauri: typeof window.__TAURI__,
  ipc: typeof window.ipc, webkit_ipc: typeof (window.webkit && window.webkit.messageHandlers
  && window.webkit.messageHandlers.ipc), origin: location.origin};
const send = (k, v) => fetch("/report?" + encodeURIComponent(JSON.stringify({k, v})));
send("globals", r);
if (window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke) {
  window.__TAURI_INTERNALS__.invoke("plugin:app|version").then(v => send("invoke", "OK " + v),
    e => send("invoke", "REFUSÉ " + String(e).slice(0, 160)));
}
fetch(B + "/fetched").then(() => send("fetch", "envoyé"), e => send("fetch", "erreur " + e));
const f = document.createElement("iframe"); f.src = B + "/iframe"; document.body.appendChild(f);
const w = window.open(B + "/opened"); send("open", w === null ? "null" : typeof w);
setTimeout(() => { location.href = B + "/navigated"; }, 1500);
setTimeout(() => send("still-here", location.href), 3500);
</script>""" % other.server_port

        class Probe(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/report?"):
                    reports.append(json.loads(unquote(self.path[8:])))
                    body, kind = b"ok", "text/plain"
                else:
                    body, kind = page.encode(), "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.end_headers()
                self.wfile.write(body)

        probe = serve(ThreadingHTTPServer(("127.0.0.1", 0), Probe))
        alive, err = launch(probe.server_port, seconds=7, shot=OUT / "l2-probe.png")
        for r in reports:
            print(f"L2 page : {r['k']} = {json.dumps(r['v'], ensure_ascii=False)}")
        print(f"L2 requêtes reçues par l'autre origine : {other_hits}")
        print(f"L2 fenêtre vivante : {alive} ; stderr : {err.strip()!r}")
        probe.shutdown()
        other.shutdown()

        data = Path.home() / ".local" / "share" / "local.eidolon.consultation"
        files = sorted(str(p.relative_to(data)) for p in data.rglob("*")) if data.exists() else []
        print(f"== D. données laissées par la webview : {data} → {len(files)} entrées ; "
              f"jeton présent dans ces fichiers : {any(token.encode() in p.read_bytes() for p in data.rglob('*') if p.is_file()) if data.exists() else False}")


if __name__ == "__main__":
    main()
