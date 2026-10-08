# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_g075.py
# Description : Recette des planificateurs (C-034–C-041) depuis le paquet installé, faux serveur loopback (C-TASK-G075)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 recipe_g075.py <repository root> <commit sha>      (exit 1 on any failed check)

Complements G069 (server/client recipe not repeated). Package built offline from the
deterministic source archive of <commit>, installed in a throw-away venv; every command runs
from a neutral folder without PYTHONPATH. One fake planner on 127.0.0.1 serves both
candidates (Ollama /api/chat, llama-server /v1/chat/completions) and counts the requests it
RECEIVES; expectations come from mission records and probe documents, never from model text.
No real model, no download, no client activation, no deployment."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import venv

REPO = Path(sys.argv[1]).resolve()
COMMIT = sys.argv[2]
SECRET = "sk-g075-synthetique"
RESULTS = []
MODEL = "synthetic-g075"


def check(label, ok, detail=""):
    RESULTS.append({"check": label, "status": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}", flush=True)
    return ok


class Planner:
    """Fake planner: a correct text.stats plan per recalled reference, or a scripted fault."""

    def __init__(self):
        self.mode = "valid"
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append((self.path, self.headers.get("Authorization")))
                if owner.mode == "slow":
                    time.sleep(30)
                context = json.loads(body["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
                steps = [{"id": f"stats-{i}", "tool": "text.stats",
                          "parameters": {"reference": f"{x['information_id']}@{x['revision']}"}}
                         for i, x in enumerate(context["items"])]
                if owner.mode == "outside-catalog":
                    steps = [{"id": "bad", "tool": "shell.execute", "parameters": {"command": "id"}}]
                content = json.dumps({"version": 1, "steps": steps})
                stop = "length" if owner.mode == "truncated" else "stop"
                if self.path == "/api/chat":
                    payload = {"model": MODEL, "done": True, "done_reason": stop,
                               "message": {"role": "assistant", "content": content}}
                else:
                    payload = {"model": MODEL, "object": "chat.completion",
                               "usage": {"prompt_tokens": 300, "completion_tokens": 30, "total_tokens": 330},
                               "choices": [{"index": 0, "finish_reason": stop,
                                            "message": {"role": "assistant", "content": content}}]}
                status = 503 if owner.mode == "unavailable" else 200
                raw = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g075-") as directory:
        root = Path(directory)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update(PIP_NO_INDEX="1", PYTHONDONTWRITEBYTECODE="1", SETUPTOOLS_USE_DISTUTILS="stdlib",
                   HTTP_PROXY="http://127.0.0.1:9", NO_PROXY="")
        work = root / "cwd"
        work.mkdir()

        def run(args, *, ok=(0,), timeout=180, extra_env=None, drop=()):
            e = {**env, **(extra_env or {})}
            for k in drop:
                e.pop(k, None)
            p = subprocess.run(list(map(str, args)), cwd=work, env=e, capture_output=True, text=True, timeout=timeout)
            if p.returncode not in ok:
                raise RuntimeError(f"{' '.join(map(str, args[1:5]))} → {p.returncode}: {p.stderr[-300:]}")
            return p

        bundle = root / "bundle.tar.gz"
        built = json.loads(run([sys.executable, REPO / "eidolon-core/tools/build_beta_bundle.py", "--repo", REPO,
                                "--commit", COMMIT, "--output", bundle]).stdout)
        with tarfile.open(bundle) as tar:
            tar.extractall(root / "x", filter="data")
        project = next((root / "x").iterdir()) / "eidolon-core"
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
             "--wheel-dir", root / "w", project], timeout=300)
        whl = next((root / "w").glob("*.whl"))
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        py = root / "venv/bin/python"
        run([py, "-m", "pip", "install", "--no-deps", "--no-index", whl], timeout=300)
        where = run([py, "-c", "import eidolon_core,sys;print(eidolon_core.__file__);print(sys.version.split()[0])"]).stdout.split()
        check("paquet installé hors réseau depuis l'archive, importé du venv",
              Path(where[0]).is_relative_to(root / "venv"),
              f"Python {where[1]} ; commit {COMMIT[:12]} ; archive {built['sha256'][:16]}… ; roue "
              f"{hashlib.sha256(whl.read_bytes()).hexdigest()[:16]}…")
        planner = Planner()
        core = [py, "-m", "eidolon_core"]
        try:
            for provider in ("ollama", "llama-server"):
                print(f"== {provider}")
                config = root / f"{provider}.json"
                base = {"version": 1, "provider": provider, "endpoint": f"http://127.0.0.1:{planner.port}", "model": MODEL,
                        "timeout_seconds": 5}
                base.update({"options": {"num_predict": 512}} if provider == "ollama" else
                            {"options": {"max_tokens": 512}, "api_key_env": "G075_KEY"})
                keyenv = {"G075_KEY": SECRET}

                def write(value, path=config):
                    path.write_text(json.dumps(value))
                    path.chmod(0o600)
                    return path
                write(base)
                n = len(planner.requests)
                manifest = json.loads(run([*core, "model-config-check", "--config", config]).stdout)["manifest"]
                check("model-config-check : manifeste sans appel", len(planner.requests) == n,
                      f"adaptateur {manifest.get('adapter')}")

                state = root / f"state-{provider}"
                args = [*core, "--state", state, "--model-config", config]
                planner.mode = "valid"
                n = len(planner.requests)
                m = json.loads(run([*args, "demo"], ok=(0,), extra_env=keyenv).stdout)
                first = len(planner.requests) - n
                again = json.loads(run([*args, "run", m["id"]], extra_env=keyenv).stdout)
                check("plan valide : SUCCEEDED, 1 requête ; reprise terminée : 0 requête, mission identique",
                      m["status"] == "SUCCEEDED" and first == 1 and again == m and len(planner.requests) - n == 1
                      and all(c["status"] == "VERIFIED" for c in m["calls"]),
                      f"{len(m['calls'])} appel(s) vérifié(s)")
                if provider == "llama-server":
                    check("clé envoyée au faux serveur seulement en Bearer", planner.requests[-1][1] == "Bearer " + SECRET)

                created = json.loads(run([*args, "create"], extra_env=keyenv).stdout)
                changed = write({**base, "options": {**base["options"], **({"num_predict": 513} if provider == "ollama"
                                                                           else {"max_tokens": 513})}},
                                root / f"{provider}-changed.json")
                n = len(planner.requests)
                r = json.loads(run([*core, "--state", state, "--model-config", changed, "run", created["id"]],
                                   ok=(2,), extra_env=keyenv).stdout)
                check("configuration changée : mission refusée sans requête",
                      (r["status"], r["error"]["code"]) == ("BLOCKED", "CONFIGURATION_CHANGED") and len(planner.requests) == n)

                if provider == "llama-server":
                    n = len(planner.requests)
                    r = json.loads(run([*core, "--state", root / "state-nokey", "--model-config", config, "demo"],
                                       ok=(2, 3), drop=("G075_KEY",)).stdout)
                    check("clé absente : mission bloquée avant envoi (0 requête)",
                          r["status"] == "BLOCKED" and r["error"]["code"] == "MODEL_UNAVAILABLE" and len(planner.requests) == n
                          and SECRET not in json.dumps(r), f"{r['status']} / {r['error']['code']}")

                for mode, label, want in (("outside-catalog", "plan hors catalogue (shell.execute)", ("BLOCKED", "PREFLIGHT_REFUSED")),
                                          ("truncated", "sortie tronquée (arrêt « length »)", None)):
                    planner.mode = mode
                    n = len(planner.requests)
                    r = json.loads(run([*core, "--state", root / f"state-{provider}-{mode}", "--model-config", config,
                                        "demo"], ok=(2, 3), extra_env=keyenv).stdout)
                    ok = len(planner.requests) - n == 1 and not r["calls"] and r["status"] in ("BLOCKED", "FAILED")
                    if want:
                        ok = ok and (r["status"], r["error"]["code"]) == want
                    check(f"{label} : 1 requête, aucun outil exécuté, aucune relance", ok,
                          f"{r['status']} / {r['error']['code']}")
                planner.mode = "valid"

                print(f"-- model-probe ({provider})")
                n = len(planner.requests)
                plan = run([*core, "model-probe", "--config", config, "--plan-only"], drop=("G075_KEY",))
                planned = json.loads(plan.stdout)
                check("--plan-only : PLANNED, 4 cas, 3 tentatives max, 0 requête, sans clé",
                      planned["status"] == "PLANNED" and planned["expected_cases"] == 4
                      and planned["max_planner_attempts"] == 3 and len(planner.requests) == n
                      and planned["hardware_qualified"] is False and planned["authorizes_execution"] is False)

                def probe(name, mode, codes):
                    planner.mode = mode
                    out = root / f"probe-{provider}-{name}"
                    n0 = len(planner.requests)
                    p = run([*core, "--timeout", "10", "model-probe", "--config", config, "--output", out],
                            ok=codes, extra_env=keyenv, timeout=240)
                    planner.mode = "valid"
                    return out, json.loads(p.stdout) if p.stdout.strip() else None, len(planner.requests) - n0, p.returncode

                def inspect(out, codes=(0,)):
                    p = run([*core, "model-probe-inspect", "--directory", out], ok=codes, drop=("G075_KEY",))
                    return p.returncode, json.loads(p.stdout) if p.stdout.strip() else json.loads(p.stderr.strip().splitlines()[-1])

                out, rep, reqs, code = probe("ok", "valid", (0,))
                check("essai valide : COMPLETE / PASSED_CASES, 3 requêtes reçues (mémoire vide : aucune)",
                      (rep["status"], rep["verdict"], reqs, code) == ("COMPLETE", "PASSED_CASES", 3, 0),
                      f"planner_attempts {[c.get('planner_attempts') for c in rep['results']]}")
                ic, ins = inspect(out)
                check("inspection : CONSISTENT, verdict consigné PASSED_CASES", ic == 0 and ins["status"] == "CONSISTENT"
                      and ins["reported_verdict"] == "PASSED_CASES")
                marked = root / f"marked-{provider}"
                subprocess.run(["cp", "-a", str(out), str(marked)], check=True)
                (marked / "MODEL-PROBE-INCOMPLETE").write_text(json.dumps({"status": "INCOMPLETE", "resume_allowed": False},
                                                                          separators=(",", ":")))
                (marked / "MODEL-PROBE-INCOMPLETE").chmod(0o600)
                ic, ins = inspect(marked, (0, 2))
                check("marqueur présent malgré un rapport PASSED_CASES → INCOMPLETE (2)", ic == 2
                      and ins.get("status") == "INCOMPLETE", str(ins.get("status") or ins.get("error")))
                discord = root / f"discord-{provider}"
                subprocess.run(["cp", "-a", str(out), str(discord)], check=True)
                case = sorted(discord.glob("case-*.json"))[0]
                value = json.loads(case.read_text())
                value["elapsed_ms"] = value.get("elapsed_ms", 0) + 1
                case.write_text(json.dumps(value))
                ic, ins = inspect(discord, (0, 2))
                check("bilan de cas modifié après coup → diagnostic constant (2)", ic == 2 and "error" in ins, str(ins.get("error")))
                n = len(planner.requests)
                p = run([*core, "model-probe", "--config", config, "--output", out], ok=(2,), extra_env=keyenv)
                check("dossier existant refusé avant tout appel", len(planner.requests) == n and not p.stdout.strip())

                out, rep, reqs, code = probe("stop", "unavailable", (3,))
                ic, ins = inspect(out)
                check("arrêt technique (503) : STOPPED, 1 requête, cas suivants non lancés",
                      (rep["status"], rep["verdict"], reqs, code) == ("STOPPED", "FAILED_CASES", 1, 3)
                      and rep["not_started_cases"] == 3 and rep["started_cases"] == rep["recorded_cases"] == 1
                      and ic == 0 and ins["run_status"] == "STOPPED",
                      f"started {rep['started_cases']} / recorded {rep['recorded_cases']} / non lancés {rep['not_started_cases']}")
                out, rep, reqs, code = probe("fail", "outside-catalog", (3,))
                check("plans refusés (FAIL) : COMPLETE / FAILED_CASES, les cas indépendants continuent",
                      (rep["status"], rep["verdict"], reqs, code) == ("COMPLETE", "FAILED_CASES", 3, 3))

                planner.mode = "slow"
                out = root / f"probe-{provider}-killed"
                n = len(planner.requests)
                child = subprocess.Popen(list(map(str, [*core, "--timeout", "60", "model-probe", "--config", config,
                                                        "--output", out])), cwd=work, env={**env, **keyenv},
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                deadline = time.monotonic() + 30
                while len(planner.requests) == n and time.monotonic() < deadline:
                    time.sleep(0.05)
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate(timeout=10)
                planner.mode = "valid"
                ic, ins = inspect(out, (0, 2))
                check("essai tué pendant le 1er cas : INCOMPLETE, cas commencés inconnus (null), bilans 0",
                      ic == 2 and ins.get("status") == "INCOMPLETE" and ins.get("started_cases") is None
                      and ins.get("recorded_cases") == 0 and ins.get("unrecorded_cases_may_have_started") is True,
                      f"requêtes reçues {len(planner.requests) - n}")
        finally:
            planner.close()

        audit = r"""
import json, os, sys
events = []
class Spy(dict):
    def get(self, k, d=None):
        if k == "G075_KEY": events.append("clé lue")
        return dict.get(self, k, d)
    def __getitem__(self, k):
        if k == "G075_KEY": events.append("clé lue")
        return dict.__getitem__(self, k)
os.environ = Spy(os.environ)
sys.addaudithook(lambda e, a: events.append(e) if e in ("socket.connect", "socket.bind", "sqlite3.connect") else None)
from eidolon_core.cli import main
code = main(sys.argv[1:])
print("@@" + json.dumps(events), file=sys.stderr)
sys.exit(code)
"""
        p = subprocess.run([str(py), "-c", audit, "model-probe-inspect", "--directory",
                            str(root / "probe-ollama-ok")], cwd=work, env={**env, "G075_KEY": SECRET},
                           capture_output=True, text=True, timeout=60)
        events = json.loads(p.stderr.rsplit("@@", 1)[1])
        check("inspection sans socket, sans SQLite (ni Store ni Runtime), sans lecture de clé",
              p.returncode == 0 and events == [], str(events))
    failed = [r["check"] for r in RESULTS if r["status"] != "PASS"]
    print(json.dumps({"status": "FAIL" if failed else "PASS", "checks": len(RESULTS), "failed": failed,
                      "python": platform.python_version()}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
