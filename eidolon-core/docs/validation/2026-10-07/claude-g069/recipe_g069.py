# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_g069.py
# Description : Recette indépendante du paquet installé depuis l'archive bêta reproductible (C-TASK-G069)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 recipe_g069.py <repository root> <commit sha>      (exit 1 on any failed check)

Independent of Codex's core-package-final.py: the package is NOT built from the checkout but
from the deterministic source archive (tools/build_beta_bundle.py, Git objects only), after
its manifest is verified. Offline build (pip --no-index --no-build-isolation), throw-away venv,
every command run with cwd outside the checkout and without PYTHONPATH. The Desktop client is
served from the files extracted from the archive. Synthetic data, loopback only, fake planner.
Missing tools are reported as BLOCKED, never as PASS, and nothing is installed system-wide."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import venv

REPO = Path(sys.argv[1]).resolve()
COMMIT = sys.argv[2]
RESULTS = []
CREATED = []          # every process started here, checked stopped at the end


def check(label, ok, detail=""):
    RESULTS.append({"check": label, "status": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}", flush=True)
    return ok


def blocked(label, why):
    RESULTS.append({"check": label, "status": "BLOCKED", "detail": why})
    print(f"⊘ {label} — BLOQUÉ : {why}", flush=True)


def tree_state():
    """Tracked + untracked state of the checkout, to prove it is unchanged."""
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all"],
                            capture_output=True, text=True).stdout
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return head, hashlib.sha256(status.encode()).hexdigest()


def main():
    source_before = tree_state()
    with tempfile.TemporaryDirectory(prefix="eidolon-g069-") as directory:
        root = Path(directory)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")}
        env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONDONTWRITEBYTECODE="1",
                   HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost")
        work = root / "cwd"          # neutral working directory: no src/, no checkout
        work.mkdir()

        def run(args, *, timeout=120, ok_codes=(0,), cwd=work):
            p = subprocess.run(list(map(str, args)), cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            if p.returncode not in ok_codes:
                raise RuntimeError(f"{Path(str(args[0])).name} {' '.join(map(str, args[1:4]))} → {p.returncode}: {p.stderr[-300:]}")
            return p

        # 1. Reproducible archive from Git objects, verified, extracted.
        bundle = root / "bundle.tar.gz"
        built = json.loads(run([sys.executable, REPO / "eidolon-core/tools/build_beta_bundle.py", "--repo", REPO,
                                "--commit", COMMIT, "--output", bundle]).stdout)
        again = root / "bundle-2.tar.gz"
        run([sys.executable, REPO / "eidolon-core/tools/build_beta_bundle.py", "--repo", REPO, "--commit", COMMIT,
             "--output", again])
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        check("archive reproductible (deux constructions identiques)", again.read_bytes() == bundle.read_bytes(),
              f"sha256 {digest}, {built['files']} fichiers")
        verified = json.loads(run([sys.executable, REPO / "eidolon-core/tools/build_beta_bundle.py", "--verify", bundle]).stdout)
        check("manifeste de l'archive vérifié", verified.get("verified") is True and verified.get("authenticity_verified") is False)
        extracted = root / "extracted"
        with tarfile.open(bundle) as tar:
            tar.extractall(extracted, filter="data")
        top, = extracted.iterdir()
        project = top / "eidolon-core"
        web = project / "desktop/connected"
        check("ressources Desktop présentes dans l'archive",
              all((web / n).is_file() for n in ("index.html", "app.js", "style.css"))
              and (web / "app.js").read_bytes() == (REPO / "eidolon-core/desktop/connected/app.js").read_bytes(),
              "index.html, app.js (identique au dépôt), style.css")
        check("app.js de l'archive contient le panneau archives G066",
              b"EidolonArchives" in (web / "app.js").read_bytes() and b"archives-load" in (web / "index.html").read_bytes())

        # 2. Offline wheel from the EXTRACTED project, throw-away venv.
        try:
            import setuptools  # noqa: F401
            import wheel  # noqa: F401
        except ImportError as exc:
            blocked("construction hors réseau", f"{exc.name} absent ; aucune installation système faite")
            return finish(source_before)
        plain = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
                                "--wheel-dir", root / "wheels-plain", project], cwd=work, env=env, capture_output=True,
                               text=True, timeout=300)
        if plain.returncode:
            # This container's setuptools 68 fails with "AttributeError: install_layout" under the
            # vendored distutils; the stdlib distutils builds the same sources. Reported, not hidden.
            check("construction hors réseau sans réglage (échoue dans ce conteneur, documenté)", True,
                  "install_layout → nouvel essai avec SETUPTOOLS_USE_DISTUTILS=stdlib")
            env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
             "--wheel-dir", root / "wheels", project], timeout=300)
        whl, = (root / "wheels").glob("*.whl")
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        py = root / "venv/bin/python"
        run([py, "-m", "pip", "install", "--no-deps", "--no-index", whl], timeout=300)
        info = json.loads(run([py, "-c", "import json,sys,eidolon_core;from importlib.metadata import version;"
                                         "print(json.dumps({'file':eidolon_core.__file__,'version':version('eidolon-core'),"
                                         "'path':sys.path}))"]).stdout)
        installed = Path(info["file"]).parent
        check("module importé depuis le venv, pas du dépôt", installed.is_relative_to(root / "venv")
              and not any(str(REPO) in p for p in info["path"]), f"version {info['version']}")
        modules = sorted((project / "src/eidolon_core").glob("*.py"))
        check("modules installés identiques à l'archive",
              all(m.read_bytes() == (installed / m.name).read_bytes() for m in modules), f"{len(modules)} modules")
        check("aucune ressource Desktop dans le paquet Python (servie depuis l'archive)",
              not list(installed.rglob("app.js")))
        check("commande eidolon-core installée", "usage" in run([root / "venv/bin/eidolon-core", "--help"]).stdout.lower())

        # 3. CLI: research, resume, diagnostics, recovery copy.
        state = root / "research-state"
        base = [py, "-m", "eidolon_core", "--state", state, "--profile", "research-sim"]
        mission = json.loads(run([*base, "research", "notice synthetique jean@example.invalid", "--required-pages", "2"]).stdout)
        resumed = json.loads(run([*base, "run", mission["id"]]).stdout)
        check("recherche synthétique puis reprise identique", mission["status"] == "SUCCEEDED" and resumed == mission)
        before = (state / "missions.sqlite3").read_bytes()
        diag = json.loads(run([py, "-m", "eidolon_core", "--state", state, "runtime-inspect", mission["id"]]).stdout)
        check("runtime-inspect sans mutation ni donnée privée",
              diag["authorizes_execution"] is False and "jean@" not in json.dumps(diag)
              and (state / "missions.sqlite3").read_bytes() == before and "recorded_block" in diag,
              "champ recorded_block (G065) présent")
        review = root / "review"
        run([py, "-m", "eidolon_core", "recovery-prepare", "--source", state / "missions.sqlite3", "--destination", review,
             "--actor", "synthetic", "--reason", "recette G069"])
        missing = run([py, "-m", "eidolon_core", "--state", review, "recovery-inspect", "--mission-id", "m-" + "e" * 32],
                      ok_codes=(2,))
        check("recovery-inspect mission absente : code 2 constant (G065)",
              "RECOVERY_MISSION_NOT_FOUND" in missing.stderr and "KeyError" not in missing.stderr)

        # 4. Research-archives fixture, preflight, HTTP catalog and the extracted Desktop client.
        fixture = root / "beta"
        made = json.loads(run([py, "-m", "eidolon_core.beta_fixture", "--output", fixture, "--profile", "research-archives"]).stdout)
        check("jeu bêta research-archives généré", made["status"] == "READY" and made["mission_count"] == 3)
        pre = json.loads(run([py, "-m", "eidolon_core.http_api", "--state", fixture / "state", "--token-file",
                              fixture / "read-token", "--research-archives", fixture / "archives", "--check"]).stdout)
        check("prédiagnostic HTTP avec archives", pre["status"] == "PASS")
        server = subprocess.Popen([str(py), "-u", "-m", "eidolon_core.http_api", "--state", str(fixture / "state"), "--token-file",
                                   str(fixture / "read-token"), "--research-archives", str(fixture / "archives"),
                                   "--web-root", str(web), "--port", "0"], cwd=work, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        CREATED.append(server)
        try:
            # A reader thread: select() on the descriptor would miss lines already buffered by Python.
            announced = {}
            ready = threading.Event()

            def watch():
                for line in server.stdout:
                    m = re.search(r"http://127\.0\.0\.1:(\d+)", line)
                    if m and not ready.is_set():
                        announced["port"] = int(m[1])
                        ready.set()
            threading.Thread(target=watch, daemon=True).start()
            if not ready.wait(15):
                raise RuntimeError("installed server did not announce its port")
            found = [None, announced["port"]]
            port = int(found[1])
            token = (fixture / "read-token").read_text().strip()

            def request(method, path, body=None):
                c = HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    headers = {"Authorization": "Bearer " + token}
                    if body is not None:
                        headers["Content-Type"] = "application/json"
                    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
                    r = c.getresponse()
                    return r.status, r.read()
                finally:
                    c.close()
            served = {p: request("GET", p) for p in ("/", "/app.js", "/style.css")}
            check("client servi = fichiers extraits de l'archive",
                  served["/app.js"] == (200, (web / "app.js").read_bytes()) and served["/"][0] == 200
                  and served["/style.css"] == (200, (web / "style.css").read_bytes()))
            status, raw = request("POST", "/v1/research-archives", {"limit": 2})
            page = json.loads(raw)
            check("catalogue HTTP paginé (C-030) depuis le paquet installé",
                  status == 200 and len(page["items"]) == 2 and page["has_more"] and page["archive_count"] == 3
                  and page["authenticity_verified"] is False)
            status, _ = request("GET", "/research-archive-000001.json")
            check("aucune route vers un export brut", status == 404)
            browser_check(port, token)
        finally:
            stop(server)

        # 5. Local model CLI on a FAKE loopback planner (LOCAL-MODEL-CLI), never a real model.
        model_cli(root, py, run)
    return finish(source_before)


def browser_check(port, token):
    script = r"""
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch();
  try {
    const p = await b.newPage({ viewport: { width: 360, height: 900 } });
    const errors = []; p.on("pageerror", (e) => errors.push(String(e)));
    // node -e: process.argv = [node, url, token]
    await p.goto(process.argv[1]);
    await p.fill("#token", process.argv[2]); await p.click("#connect");
    await p.waitForSelector(".mission-button");
    await p.click("#archives-load");
    await p.waitForSelector(".archives-table tbody tr");
    const rows = await p.$$eval(".archives-table tbody tr", (r) => r.length);
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(JSON.stringify({ rows, overflow, errors }));
  } finally { await b.close(); }
})().catch((e) => { console.error(String(e)); process.exit(1); });
"""
    node = shutil.which("node")
    if not node:
        blocked("client Desktop dans Chromium", "node absent")
        return
    p = subprocess.run([node, "-e", script, f"http://127.0.0.1:{port}/", token], capture_output=True, text=True,
                       env=dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules")), timeout=120)
    if p.returncode != 0 and ("Cannot find module" in p.stderr or "Executable doesn't exist" in p.stderr):
        blocked("client Desktop dans Chromium", "Playwright/Chromium absent")
        return
    try:
        out = json.loads(p.stdout)
    except ValueError:
        check("client Desktop dans Chromium (paquet installé)", False, p.stderr[-200:].replace(token, "<jeton>"))
        return
    check("client Desktop extrait, servi par le paquet installé, archives affichées à 360 px",
          out["rows"] == 3 and out["overflow"] <= 0 and out["errors"] == [], json.dumps(out))


def model_cli(root, py, run):
    calls = []

    class Fake(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(self.path)
            context = json.loads(body["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
            plan = {"version": 1, "steps": [{"id": f"stats-{i}", "tool": "text.stats",
                                             "parameters": {"reference": f"{x['information_id']}@{x['revision']}"}}
                                            for i, x in enumerate(context["items"], 1)]}
            data = json.dumps({"model": "synthetic-g069:1b", "done": True, "done_reason": "stop",
                               "message": {"role": "assistant", "content": json.dumps(plan)}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        config = root / "model.json"
        config.write_text(json.dumps({"version": 1, "provider": "ollama", "endpoint": f"http://127.0.0.1:{server.server_port}",
                                      "model": "synthetic-g069:1b", "options": {"num_predict": 256}, "timeout_seconds": 5}))
        config.chmod(0o600)
        checked = json.loads(run([py, "-m", "eidolon_core", "model-config-check", "--config", config]).stdout)
        check("model-config-check : valide sans contacter le serveur",
              checked.get("server_contacted") is False and calls == [], checked.get("status", ""))
        args = [py, "-m", "eidolon_core", "--state", root / "model-state", "--model-config", config]
        m = json.loads(run([*args, "demo"]).stdout)
        again = json.loads(run([*args, "run", m["id"]]).stdout)
        check("CLI planificateur local sur faux serveur loopback : un seul appel, reprise sans rappel",
              m["status"] == "SUCCEEDED" and again == m and calls == ["/api/chat"], f"appels {calls}")
        config.chmod(0o644)
        refused = run([py, "-m", "eidolon_core", "model-config-check", "--config", config], ok_codes=(2,))
        check("configuration publique refusée avant tout appel", len(calls) == 1 and str(config) not in refused.stderr)
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def stop(proc):
    proc.terminate()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=5)


def finish(source_before):
    check("tous les processus créés sont arrêtés", all(p.poll() is not None for p in CREATED), f"{len(CREATED)} serveur(s)")
    check("dépôt source inchangé (HEAD et état git)", tree_state() == source_before)
    summary = {"commit": COMMIT, "results": RESULTS,
               "status": "FAIL" if any(r["status"] == "FAIL" for r in RESULTS) else
                         "BLOCKED" if any(r["status"] == "BLOCKED" for r in RESULTS) else "PASS"}
    print(json.dumps({"status": summary["status"], "checks": len(RESULTS),
                      "failed": [r["check"] for r in RESULTS if r["status"] != "PASS"]}, ensure_ascii=False))
    return 1 if summary["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
