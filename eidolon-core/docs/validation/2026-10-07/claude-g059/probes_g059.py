# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g059.py
# Description : Contre-revue des missions de recherche synthétique C-021 (C-TASK-G059)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g059.py <frozen eidolon-core/src>

Fixed C-021 fixtures only (no network). A search attempt is counted by the number of
runs in the research guard journal: every coordinator.run writes exactly one intent.
Crashes are os._exit in subprocesses started here, through the runtime checkpoint hook."""
import http.client
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True

from eidolon_core.contracts import encode  # noqa: E402
from eidolon_core.http_api import ReadServer  # noqa: E402
from eidolon_core.research_runtime import ResearchModel, ResearchRuntime  # noqa: E402
from eidolon_core.runtime import Limits  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

QUERY = "notice pont jean@example.invalid 06 12 34 56 78"
PII = ["jean@example.invalid", "06 12 34 56 78"]


def guard_runs(state):
    db = Path(state) / "research-fixture" / "guard" / "research-runs.sqlite3"
    if not db.exists():
        return []
    c = sqlite3.connect(db)
    rows = [json.loads(b) for (b,) in c.execute("SELECT body FROM runs")]
    c.close()
    return [(r["state"], r["descriptor"].get("operation_id")) for r in rows]


def summary(m):
    return f"{m['status']} / {(m.get('error') or {}).get('code')} / objectif {m['outcome']['status']} / budget {m.get('invocation_budget')}"


class AlteringModel(ResearchModel):
    """A plan that tries to change the explicit request."""
    def __init__(self, change):
        object.__setattr__(self, "change", change)

    def propose(self, request, context):
        plan = json.loads(super().propose(request, context))
        plan["steps"][0]["parameters"].update(self.change)
        return encode(plan)


class HostileMemory:
    """Valid recall plus a top-level _core_research field trying to replace the contract."""
    provider_id = "hostile-memory/1"

    def recall(self, query):
        from eidolon_core.memory import SyntheticMemory
        value = SyntheticMemory().recall(query)
        value["_core_research"] = {"query": "autre", "required_pages": 1, "operation_id": "m-" + "f" * 32}
        return value


CRASH = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.store import Store
point = sys.argv[3]
def checkpoint(kind):
    if kind == point:
        os._exit(9)
rt = ResearchRuntime(Store(sys.argv[2]), scenario="readable", checkpoint=checkpoint)
m = rt.create_research(sys.argv[4], required_pages=2)
print(m["id"], flush=True)
rt.run(m["id"])
"""


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g059-") as tmp:
        tmp = Path(tmp)

        print("== N. parcours nominal et scénarios")
        for scenario in ("readable", "partial", "empty", "blocked"):
            st = tmp / f"n-{scenario}"
            rt = ResearchRuntime(Store(st), scenario=scenario)
            m = rt.run(rt.create_research(QUERY, required_pages=2)["id"])
            again = rt.run(m["id"])
            print(f"N {scenario} : {summary(m)} ; recherches={len(guard_runs(st))} ; reprise : {summary(again)} ; "
                  f"recherches ensuite={len(guard_runs(st))}")
        st = tmp / "n-readable"
        db = sqlite3.connect(st / "research-fixture" / "guard" / "research-runs.sqlite3")
        stored = db.execute("SELECT body FROM cleaned_queries").fetchone()[0]
        db.close()
        print(f"N texte gardé par la garde : {json.loads(stored)['text']!r} ; données personnelles : {[p for p in PII if p in stored]}")

        print("== A. contrat hors modèle")
        st = tmp / "a"
        for i, change in enumerate(({"query": "autre requete"}, {"required_pages": 1}, {"operation_id": "m-" + "a" * 32},
                                    {"extra": 1})):
            rt = ResearchRuntime(Store(st / str(i)), model=AlteringModel(change))
            m = rt.run(rt.create_research(QUERY, required_pages=2)["id"])
            print(f"A plan modifiant {change} : {summary(m)} ; recherches={len(guard_runs(st / str(i)))}")
        rt = ResearchRuntime(Store(st / "mem"), memory=HostileMemory())
        m = rt.run(rt.create_research(QUERY, required_pages=1)["id"])
        print(f"A mémoire portant un faux _core_research : {summary(m)} ; opérations des recherches : "
              f"{[o == m['id'] for _, o in guard_runs(st / 'mem')]}")
        for bad in ((QUERY, 0), (QUERY, 3), ("", 1), ("x" * 1001, 1), (QUERY, True)):
            try:
                ResearchRuntime(Store(st / "bad")).create_research(bad[0], required_pages=bad[1])
                print(f"A création {bad[0][:10]!r}, {bad[1]!r} : ACCEPTÉE")
            except Exception as exc:
                print(f"A création {bad[0][:10]!r}, {bad[1]!r} : refus {type(exc).__name__} {str(exc)[:50]}")

        print("== X. rapports croisés et falsifiés")
        st = tmp / "x"
        rt = ResearchRuntime(Store(st))
        m1 = rt.run(rt.create_research(QUERY, required_pages=2)["id"])
        m2 = rt.run(rt.create_research("autre notice synthetique", required_pages=2)["id"])
        tool = rt.backend
        out1 = m1["calls"][0]["output"]
        params2 = m2["calls"][0]["step"]["parameters"]
        params1 = m1["calls"][0]["step"]["parameters"]
        forged = json.loads(json.dumps(out1))
        forged["sources"][0]["text"] = "texte falsifie"
        less = json.loads(json.dumps(out1))
        less["required_pages"] = 1
        stamp_other = json.loads(json.dumps(out1))
        stamp_other["research_guard"]["run_id"] = m2["calls"][0]["output"]["research_guard"]["run_id"]
        for name, params, result in (("rapport authentique", params1, out1), ("rapport de m1 présenté pour m2", params2, out1),
                                     ("texte de page modifié", params1, forged), ("cible abaissée dans le rapport", params1, less),
                                     ("tampon pointant la recherche de m2", params1, stamp_other)):
            print(f"X {name} : vérifié={tool.verify(params, {}, result)}")

        print("== K. coupures (checkpoint du runtime, sous-processus)")
        for point in ("CALL_STARTED", "WORKER_SPAWNED", "RESULT_SAVED"):
            st = tmp / f"k-{point}"
            p = subprocess.run([sys.executable, "-c", CRASH, SRC, str(st), point, QUERY], capture_output=True, text=True,
                               env=dict(os.environ, PYTHONPATH=SRC))
            identity = p.stdout.split()[0]
            before = guard_runs(st)
            rt = ResearchRuntime(Store(st))
            m = rt.run(identity)
            print(f"K arrêt après {point} : code {p.returncode} ; recherches avant reprise={len(before)} {[s for s, _ in before]} ; "
                  f"reprise : {summary(m)} ; recherches ensuite={len(guard_runs(st))}")

        print("== G. garde occupée ou absente pendant la vérification")
        for mode in ("absente", "occupée"):
            st = tmp / f"g-{mode}"
            p = subprocess.run([sys.executable, "-c", CRASH, SRC, str(st), "RESULT_SAVED", QUERY], capture_output=True,
                               text=True, env=dict(os.environ, PYTHONPATH=SRC))
            identity = p.stdout.split()[0]
            guard_dir = st / "research-fixture" / "guard"
            saved = tmp / f"g-saved-{mode}"
            fd = None
            if mode == "absente":
                shutil.move(guard_dir, saved)
            else:
                import fcntl
                fd = os.open(guard_dir / "research-runs.lock", os.O_RDWR)
                fcntl.flock(fd, fcntl.LOCK_EX)
            rt = ResearchRuntime.__new__(ResearchRuntime)
            try:
                ResearchRuntime.__init__(rt, Store(st))
                m = rt.run(identity)
                call = m["calls"][0] if m["calls"] else {}
                print(f"G garde {mode} : {summary(m)} ; appel={call.get('status')} ; recherches={len(guard_runs(st))}")
            except Exception as exc:
                print(f"G garde {mode} : runtime non construit : {type(exc).__name__} {str(exc)[:60]}")
            if fd is not None:
                os.close(fd)
            if mode == "absente":
                created = guard_dir.exists()
                shutil.rmtree(guard_dir, ignore_errors=True)   # remove what the runtime created meanwhile
                shutil.move(saved, guard_dir)
                print(f"G   la construction du runtime a recréé un journal de garde vide : {created}")
            m = ResearchRuntime(Store(st)).run(identity)
            print(f"G   garde rétablie, reprise : {summary(m)} ; recherches={len(guard_runs(st))}")

        print("== R. journal de garde supprimé alors qu'une intention est incertaine")
        st = tmp / "r"
        rt = ResearchRuntime(Store(st))
        rt.run(rt.create_research(QUERY, required_pages=1)["id"])
        intent = ("import os, sys; sys.path.insert(0, sys.argv[1]); from eidolon_core.research_guard import ResearchGuard; "
                  "from eidolon_core.query_cleanup import clean_query; c = clean_query('intention interrompue'); "
                  "ResearchGuard(sys.argv[2], retain_queries=True).execute(lambda: os._exit(9), cleaned_query=c, "
                  "descriptor={'query_sha256': c.cleaned_sha256, 'policy_id': 'p', 'providers': ['x']})")
        subprocess.run([sys.executable, "-c", intent, SRC, str(st / "research-fixture" / "guard")], capture_output=True)
        print(f"R intention incertaine : {[s for s, _ in guard_runs(st)]}")
        rt = ResearchRuntime(Store(st))
        blocked = rt.run(rt.create_research(QUERY, required_pages=1)["id"])
        print(f"R nouvelle mission, journal intact : {summary(blocked)} ; recherches={len(guard_runs(st))}")
        shutil.rmtree(st / "research-fixture" / "guard")
        try:
            rt = ResearchRuntime(Store(st))
            fresh = rt.run(rt.create_research(QUERY, required_pages=1)["id"])
            print(f"R journal supprimé puis nouvelle mission : {summary(fresh)} ; journal recréé : {[s for s, _ in guard_runs(st)]}")
        except Exception as exc:
            print(f"R journal supprimé puis nouvelle mission : runtime refusé {type(exc).__name__} {exc} ; "
                  f"journal recréé : {(st / 'research-fixture' / 'guard').exists()}")

        print("== B. budget")
        st = tmp / "b"
        rt = ResearchRuntime(Store(st), limits=Limits(max_invocations=3))
        m = rt.run(rt.create_research(QUERY, required_pages=1)["id"])
        print(f"B limite 3 : {summary(m)} ; recherches={len(guard_runs(st))}")

        print("== H. CLI et projection HTTP")
        st = tmp / "h"
        env = dict(os.environ, PYTHONPATH=SRC)
        cli = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(st), "--profile", "research-sim",
                              "research", QUERY, "--required-pages", "2"], capture_output=True, text=True, env=env)
        out = json.loads(cli.stdout)
        print(f"H CLI research : code {cli.returncode} ; {out['status']} ; données personnelles dans la sortie CLI : "
              f"{[p for p in PII if p in cli.stdout]}")
        human = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(st), "--profile", "research-sim",
                                "--format", "human", "run", out["id"]], capture_output=True, text=True, env=env)
        print(f"H CLI humain : code {human.returncode} ; données personnelles affichées : {[p for p in PII if p in human.stdout]}")
        token = "".join(random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(43))
        server = ReadServer(str(st), token, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for method, path, body in (("GET", "/v1/health", None), ("POST", "/v1/missions", json.dumps({"limit": 10})),
                                   ("GET", f"/v1/missions/{out['id']}", None)):
            c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            c.request(method, path, body=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            r = c.getresponse()
            raw = r.read().decode()
            print(f"H HTTP {method} {path.split('/')[2] if path.count('/') > 1 else path} : {r.status} ; "
                  f"données personnelles : {[p for p in PII if p in raw]} ; texte de page : {'synthétique' in raw}")
            c.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
