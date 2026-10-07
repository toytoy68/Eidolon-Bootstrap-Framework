# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g051.py
# Description : Contre-revue de la garde durable de recherche C-014a avec vrais processus (C-TASK-G051)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g051.py <frozen copy>/eidolon-core/src

Only processes started here, killed by their own PID. Fake providers/reader/DNS;
every provider contact appends one line to a counter file. No network."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

SRC = str(Path(sys.argv[1]).resolve())

# Child: one guarded research. argv: root, provider behaviour, hook
CHILD = r"""
import json, os, sys, time
from pathlib import Path
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_pauses import ResearchPauses
root, behaviour, hook = Path(sys.argv[1]), sys.argv[2], sys.argv[3]

def mark(name):
    (root / name).write_text(str(os.getpid()))

if hook in ("after_intent", "before_completion"):
    real = ResearchGuard._write
    def write(self, db, record, *, insert=False):
        if hook == "before_completion" and record["state"] == "COMPLETED":
            mark("hook.reached"); time.sleep(60)
        real(self, db, record, insert=insert)
        if hook == "after_intent" and record["state"] == "INTENT":
            db.commit(); mark("hook.reached"); time.sleep(60)
    ResearchGuard._write = write

class Provider:
    provider_id = "g051-provider"
    def search(self, query, limit):
        with open(root / "contacts.log", "a") as f:
            f.write(f"{os.getpid()} {behaviour}\n")
        if behaviour == "slow":
            mark("contact.started"); time.sleep(float(os.environ.get("G051_SLEEP", "60")))
            return []
        if behaviour == "rate":
            raise AccessFailure("RATE_LIMITED", retry_after=3600)
        return []

class Reader:
    reader_id = "g051-reader"
    def read(self, url, policy):
        raise AccessFailure("UNAVAILABLE")

try:
    guard = ResearchGuard(root / "guard")
    pauses = ResearchPauses(root / "pauses.sqlite3")
    c = ResearchCoordinator([Provider()], Reader(), resolver=lambda h, p: ["93.184.216.34"], pauses=pauses, guard=guard)
    r = c.run("documentation pont synthetique")
    print(json.dumps({"status": r["status"], "providers": [p["status"] for p in r["providers"]]}))
except Exception as exc:
    print(json.dumps({"error": type(exc).__name__, "code": str(exc)}))
"""

INSPECT = r"""
import json, sys
from pathlib import Path
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_pauses import ResearchPauses, provider_scope
root = Path(sys.argv[1])
try:
    g = ResearchGuard(root / "guard", create=False)
    runs = g.inspect()["runs"]
    out = {"runs": [(r["id"], r["state"], r.get("observed_state"), r["outcome"]) for r in runs]}
    if sys.argv[2] == "resolve":
        rid = next(r["id"] for r in runs if r["state"] == "INTENT")
        out["resolve"] = g.resolve(rid, expected_revision=1, actor="g051", reason="revue synthetique G051")
    pauses = ResearchPauses(root / "pauses.sqlite3")
    out["provider_paused"] = bool(pauses.active(provider_scope("g051-provider")))
    print(json.dumps(out))
except Exception as exc:
    print(json.dumps({"error": type(exc).__name__, "code": str(exc)}))
"""


def env():
    return dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


def child(root, behaviour, hook="none"):
    return subprocess.Popen([sys.executable, "-c", CHILD, str(root), behaviour, hook], env=env(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(proc):
    out, err = proc.communicate(timeout=120)
    return out.strip() or ("STDERR " + err.strip()[-200:])


def run(root, behaviour="hits", hook="none"):
    return finish(child(root, behaviour, hook))


def inspect(root, action="inspect"):
    proc = subprocess.run([sys.executable, "-c", INSPECT, str(root), action], env=env(),
                          capture_output=True, text=True, timeout=60)
    return json.loads(proc.stdout)


def contacts(root):
    path = Path(root) / "contacts.log"
    return len(path.read_text().splitlines()) if path.exists() else 0


def wait_for(path, timeout=30):
    end = time.time() + timeout
    while not Path(path).exists():
        if time.time() > end:
            raise SystemExit(f"timeout waiting {path}")
        time.sleep(0.02)


def short(value):
    if isinstance(value, dict) and "runs" in value:
        value = dict(value, runs=[r[1:] for r in value["runs"]])
        if "resolve" in value:
            value["resolve"] = {k: value["resolve"][k] for k in ("state", "request_sent", "effect_known")}
    return json.dumps(value, ensure_ascii=False)


def crash_case(base, name, behaviour, hook, marker, sig):
    root = base / name
    root.mkdir()
    print(f"-- {name}")
    print(f"   préalable : {run(root, 'hits')} ; contacts={contacts(root)}")
    proc = child(root, behaviour, hook)
    wait_for(root / marker)
    before = contacts(root)
    os.kill(proc.pid, sig)
    proc.communicate(timeout=30)
    print(f"   signal {signal.Signals(sig).name} au PID {proc.pid} ({marker}) : code {proc.returncode} ; contacts={before}")
    print(f"   inspection : {short(inspect(root))}")
    print(f"   nouvelle recherche : {run(root, 'hits')} ; contacts={contacts(root)} (aucun nouveau contact attendu)")
    print(f"   revue explicite : {short(inspect(root, 'resolve'))}")
    after = contacts(root)
    print(f"   après revue, sans nouvel appel : contacts={after} (inchangé = pas de relance implicite)")
    print(f"   nouvelle recherche explicite : {run(root, 'hits')} ; contacts={contacts(root)}")
    print(f"   inspection finale : {short(inspect(root))}")


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g051-") as tmp:
        base = Path(tmp)
        print("== K. pannes de vrais processus")
        crash_case(base, "K1 SIGKILL après l'intention, avant tout contact", "hits", "after_intent", "hook.reached", signal.SIGKILL)
        crash_case(base, "K2 SIGKILL pendant l'appel fournisseur", "slow", "none", "contact.started", signal.SIGKILL)
        crash_case(base, "K3 SIGTERM pendant l'appel fournisseur", "slow", "none", "contact.started", signal.SIGTERM)
        crash_case(base, "K4 429 → pause écrite, puis SIGKILL avant la fin", "rate", "before_completion", "hook.reached", signal.SIGKILL)

        print("== C. concurrence : 6 processus en même temps (fournisseur lent 1,5 s)")
        root = base / "C1"
        root.mkdir()
        print(f"   préalable : {run(root)}")
        os.environ["G051_SLEEP"] = "1.5"
        procs = [child(root, "slow") for _ in range(6)]
        outs = [finish(p) for p in procs]
        del os.environ["G051_SLEEP"]
        kinds = {}
        for o in outs:
            key = json.loads(o).get("code") or json.loads(o).get("status")
            kinds[key] = kinds.get(key, 0) + 1
        state = inspect(root)
        print(f"   résultats : {kinds} ; contacts lents={contacts(root) - 1} ; journal : "
              f"{[r[2] for r in state['runs']]}")
        print("== C2. pendant une recherche : inspection et revue par un autre processus")
        os.environ["G051_SLEEP"] = "3"
        (root / "contact.started").unlink()      # left by C1: wait for THIS run's contact
        proc = child(root, "slow")
        wait_for(root / "contact.started")
        print(f"   inspection : {short(inspect(root))}")
        print(f"   revue : {short(inspect(root, 'resolve'))}")
        print(f"   fin de la recherche : {finish(proc)}")
        del os.environ["G051_SLEEP"]
        print(f"   journal ensuite : {short(inspect(root))}")

        print("== J. journal altéré ou incomplet")
        def altered(name, sql=None, action=None):
            root = base / name
            root.mkdir()
            run(root)
            run(root)
            db = root / "guard" / "research-runs.sqlite3"
            if sql:
                c = sqlite3.connect(db)
                c.execute(sql)
                c.commit()
                c.close()
            if action:
                action(root)
            n = contacts(root)
            print(f"   {name} : {run(root)} ; nouveau contact={contacts(root) - n}")
        altered("J1 dernier événement COMPLETED supprimé", "DELETE FROM run_events WHERE sequence=(SELECT max(sequence) FROM run_events)")
        altered("J2 base en 0644", action=lambda r: os.chmod(r / "guard" / "research-runs.sqlite3", 0o644))
        altered("J3 fichier de verrou supprimé", action=lambda r: os.unlink(r / "guard" / "research-runs.lock"))
        altered("J4 base tronquée à 100 octets", action=lambda r: os.truncate(r / "guard" / "research-runs.sqlite3", 100))

        # Coherent deletion of an INTENT (row + its event): documented as outside detection.
        root = base / "J5"
        root.mkdir()
        proc = child(root, "slow")
        wait_for(root / "contact.started")
        os.kill(proc.pid, signal.SIGKILL)
        proc.communicate()
        c = sqlite3.connect(root / "guard" / "research-runs.sqlite3")
        rid = c.execute("SELECT id FROM runs").fetchone()[0]
        c.execute("DELETE FROM run_events WHERE run_id=?", (rid,))
        c.execute("DELETE FROM runs WHERE id=?", (rid,))
        c.commit()
        c.close()
        print(f"   J5 intention + son événement supprimés ensemble : {run(root)} (contournement documenté)")
        root = base / "J6"
        root.mkdir()
        proc = child(root, "slow")
        wait_for(root / "contact.started")
        os.kill(proc.pid, signal.SIGKILL)
        proc.communicate()
        import shutil
        shutil.rmtree(root / "guard")
        print(f"   J6 dossier du journal supprimé après une panne : {run(root)} (contournement documenté)")

        print("== L. verrou remplacé pendant une recherche en cours")
        root = base / "L1"
        root.mkdir()
        os.environ["G051_SLEEP"] = "3"
        proc = child(root, "slow")
        wait_for(root / "contact.started")
        lock = root / "guard" / "research-runs.lock"
        lock.unlink()
        fd = os.open(lock, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        print(f"   seconde recherche pendant la première : {run(root)} ; contacts={contacts(root)}")
        print(f"   première : {finish(proc)}")
        del os.environ["G051_SLEEP"]

        print("== H. capacité : 256 recherches, puis la 257e")
        root = base / "H1"
        root.mkdir()
        code = r"""
import sys, json
from pathlib import Path
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
class P:
    provider_id = "g051-provider"
    def search(self, q, l): return []
class R:
    reader_id = "g051-reader"
g = ResearchGuard(Path(sys.argv[1]) / "guard")
c = ResearchCoordinator([P()], R(), resolver=lambda h, p: ["93.184.216.34"], guard=g)
ok = 0
for i in range(256):
    c.run("documentation pont synthetique"); ok += 1
try:
    c.run("documentation pont synthetique"); last = "ACCEPTÉE"
except Exception as exc:
    last = f"{type(exc).__name__} {exc}"
print(json.dumps({"réussies": ok, "257e": last}, ensure_ascii=False))
"""
        p = subprocess.run([sys.executable, "-c", code, str(root)], env=env(), capture_output=True, text=True, timeout=300)
        print(f"   {p.stdout.strip() or p.stderr[-300:]}")
        help_text = subprocess.run([sys.executable, "-m", "eidolon_core.research_guard", "--help"], env=env(),
                                   capture_output=True, text=True).stdout
        print(f"   usage de la CLI : {' '.join(help_text.split()[:12])}")


if __name__ == "__main__":
    main()
