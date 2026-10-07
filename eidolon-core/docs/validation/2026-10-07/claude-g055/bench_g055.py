# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_g055.py
# Description : Frontières réseau de la coquille Tauri : navigation, CSP Core, ACL IPC (C-TASK-G055)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""cd eidolon-core && PYTHONPATH=src xvfb-run -a python3 <this file> <tauri binary>

Loopback only. A probe page (same origin as the window) tries 16 kinds of outbound
requests towards a second loopback server ("other origin"), which records every hit.
Run twice: without any CSP (what the shell alone stops) and with the exact CSP that Core
sends (read from a live Core response, not copied). Then checks the real Core responses.
Only processes started here are stopped, by their own PID."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote

from eidolon_core.beta_fixture import create
from eidolon_core.http_api import ReadServer

BINARY = sys.argv[1]
WEB_ROOT = Path("desktop/connected").resolve()

ATTEMPTS = ["fetch", "xhr", "websocket", "eventsource", "beacon", "img", "script", "stylesheet",
            "css-background", "iframe", "worker", "prefetch", "form-post", "navigation",
            "window-open", "anchor-blank"]

PROBE_JS = r"""
const B = "http://127.0.0.1:%(other)d";
const done = (k, v) => fetch("/report?" + encodeURIComponent(JSON.stringify({k, v}))).catch(() => {});
document.addEventListener("securitypolicyviolation", e => done("csp", e.violatedDirective + " " + e.blockedURI.replace(B, "B")));
const tries = {
  "fetch": () => fetch(B + "/fetch", {mode: "no-cors"}).then(() => "envoyé", e => "erreur"),
  "xhr": () => new Promise(r => { const x = new XMLHttpRequest(); x.onload = () => r("chargé"); x.onerror = () => r("erreur");
                                   try { x.open("GET", B + "/xhr"); x.send(); } catch (e) { r("exception"); } }),
  "websocket": () => new Promise(r => { try { const w = new WebSocket(B.replace("http", "ws") + "/websocket");
                                   w.onopen = () => r("ouvert"); w.onerror = () => r("erreur"); } catch (e) { r("exception"); } }),
  "eventsource": () => new Promise(r => { try { const s = new EventSource(B + "/eventsource"); s.onopen = () => r("ouvert");
                                   s.onerror = () => { s.close(); r("erreur"); }; } catch (e) { r("exception"); } }),
  "beacon": () => { try { return navigator.sendBeacon(B + "/beacon", "x") ? "accepté" : "refusé"; } catch (e) { return "exception"; } },
  "img": () => new Promise(r => { const i = new Image(); i.onload = () => r("chargée"); i.onerror = () => r("erreur"); i.src = B + "/img"; }),
  "script": () => new Promise(r => { const s = document.createElement("script"); s.onload = () => r("chargé");
                                   s.onerror = () => r("erreur"); s.src = B + "/script"; document.head.appendChild(s); }),
  "stylesheet": () => new Promise(r => { const l = document.createElement("link"); l.rel = "stylesheet"; l.onload = () => r("chargée");
                                   l.onerror = () => r("erreur"); l.href = B + "/stylesheet"; document.head.appendChild(l); }),
  "css-background": () => { const d = document.createElement("div"); d.style.backgroundImage = "url(" + B + "/css-background)";
                                   d.style.width = "10px"; d.style.height = "10px"; document.body.appendChild(d); return "posée"; },
  "iframe": () => { const f = document.createElement("iframe"); f.src = B + "/iframe"; document.body.appendChild(f); return "posée"; },
  "worker": () => { try { new Worker(B + "/worker"); return "créé"; } catch (e) { return "exception"; } },
  "prefetch": () => { const l = document.createElement("link"); l.rel = "prefetch"; l.href = B + "/prefetch"; document.head.appendChild(l); return "posée"; },
  "form-post": () => { const f = document.createElement("form"); f.method = "POST"; f.action = B + "/form-post"; f.target = "sink";
                                   const s = document.createElement("iframe"); s.name = "sink"; document.body.appendChild(s);
                                   document.body.appendChild(f); try { f.submit(); return "soumis"; } catch (e) { return "exception"; } },
  "window-open": () => { const w = window.open(B + "/window-open"); return w === null ? "null" : "fenêtre"; },
  "anchor-blank": () => { const a = document.createElement("a"); a.href = B + "/anchor-blank"; a.target = "_blank";
                                   document.body.appendChild(a); a.click(); return "cliqué"; },
};
(async () => {
  for (const k of Object.keys(tries)) { try { done(k, await Promise.race([Promise.resolve(tries[k]()),
      new Promise(r => setTimeout(() => r("délai"), 1500))])); } catch (e) { done(k, "exception"); } }
  done("ipc", typeof window.__TAURI_INTERNALS__);
  setTimeout(() => { location.href = B + "/navigation"; }, 300);
  setTimeout(() => done("après-navigation", location.origin === B ? "AUTRE ORIGINE" : "même origine"), 2500);
})();
"""


class Other(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _hit(self):
        self.server.hits.append(self.path.split("?")[0].lstrip("/"))

    def do_GET(self):
        self._hit()
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.send_response(400)          # never completes a handshake: a hit is enough
            self.end_headers()
            return
        kind = "text/event-stream" if self.path.startswith("/eventsource") else "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        self._hit()
        self.send_response(204)
        self.end_headers()


def serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_window(port, seconds):
    env = {k: v for k, v in os.environ.items() if k != "EIDOLON_CORE_PORT"}
    proc = subprocess.Popen([BINARY, "--port", str(port)], env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    time.sleep(seconds)
    proc.terminate()
    try:
        _, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, err = proc.communicate()
    return [line for line in err.splitlines() if line.startswith("eidolon-consultation")]


def core_csp():
    """Start the real Core read server once and read the CSP it actually sends for / and the API."""
    with tempfile.TemporaryDirectory(prefix="eidolon-g055-") as tmp:
        create(str(Path(tmp) / "demo"))
        token = "".join(random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(43))
        core = serve(ReadServer(str(Path(tmp) / "demo" / "state"), token, port=0, web_root=str(WEB_ROOT)))
        headers = {}
        for path, auth in (("/", False), ("/app.js", False), ("/v1/health", True), ("/v1/nope", True)):
            c = http.client.HTTPConnection("127.0.0.1", core.server_port, timeout=10)
            c.request("GET", path, headers={"Authorization": "Bearer " + token} if auth else {})
            r = c.getresponse()
            r.read()
            headers[path] = (r.status, r.getheader("Content-Security-Policy"))
            c.close()
        core.shutdown()
        core.server_close()
    return headers


def main():
    print("== C. en-têtes réels de Core (serveur de lecture, jeu synthétique)")
    headers = core_csp()
    for path, (status, csp) in headers.items():
        print(f"C {path} : HTTP {status} ; CSP={csp!r}")
    csp = headers["/"][1]
    for mode, policy in (("SANS CSP (coquille seule)", None), ("AVEC la CSP exacte de Core", csp)):
        other = ThreadingHTTPServer(("127.0.0.1", 0), Other)
        other.hits = []
        serve(other)
        reports = []
        js = (PROBE_JS % {"other": other.server_port}).encode()

        class Probe(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/report?"):
                    reports.append(json.loads(unquote(self.path[8:])))
                    body, kind = b"", "text/plain"
                elif self.path == "/probe.js":
                    body, kind = js, "text/javascript"
                else:
                    body, kind = b"<!doctype html><title>sonde G055</title><p>sonde</p><script src=/probe.js></script>", "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                if policy:
                    self.send_header("Content-Security-Policy", policy)
                self.end_headers()
                self.wfile.write(body)

        probe = serve(ThreadingHTTPServer(("127.0.0.1", 0), Probe))
        diagnostics = run_window(probe.server_port, 14)
        probe.shutdown()
        other.shutdown()
        results = {r["k"]: r["v"] for r in reports if r["k"] != "csp"}
        violations = sorted({r["v"].split(" ")[0] for r in reports if r["k"] == "csp"})
        print(f"== {mode}")
        for k in ATTEMPTS:
            reached = k in other.hits
            print(f"  {k:15s} page: {str(results.get(k, '—')):12s} autre origine atteinte : {'OUI' if reached else 'non'}")
        print(f"  IPC (__TAURI_INTERNALS__) : {results.get('ipc')} ; après navigation : {results.get('après-navigation')}")
        print(f"  directives CSP violées : {violations}")
        print(f"  requêtes reçues par l'autre origine : {sorted(set(other.hits))}")
        print(f"  diagnostics de la coquille : {sorted(set(diagnostics))} ×{len(diagnostics)}")


if __name__ == "__main__":
    main()
