# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g070.py
# Description : Banc borné de courses : exécutants concurrents, annulation, reçu tardif, verrous, interruptions (C-TASK-G070)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g070.py <frozen eidolon-core/src>      (exit 1 if an assertion fails)

Real runtime processes (subprocesses) and real spawned tool workers. The number of tool
executions and verifications is counted OUTSIDE the runtime (g070_tools: fsynced log written by
the tool itself). Every wait is bounded; no delay was raised to hide a failure. Temporary
folders only; every process created here is checked stopped at the end."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

SRC = str(Path(sys.argv[1]).resolve())
HERE = str(Path(__file__).resolve().parent)
sys.path[:0] = [SRC, HERE]
sys.dont_write_bytecode = True

from eidolon_core.memory import DEMO_REQUEST  # noqa: E402
from eidolon_core.runtime_inspect import inspect_runtime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

FAILED = []
STARTED = []

RUNNER = r"""
import json, os, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
import g070_tools as t
from eidolon_core.store import Busy
point = sys.argv[5]
def checkpoint(kind):
    if kind == point:
        os._exit(9)
rt = t.runtime(sys.argv[3], seconds=float(os.environ.get("G070_SECONDS", "10")), checkpoint=checkpoint)
try:
    m = rt.run(sys.argv[4])
    print(json.dumps({"status": m["status"], "code": (m.get("error") or {}).get("code")}), flush=True)
except Busy:
    print(json.dumps({"status": "BUSY"}), flush=True)
"""


def check(label, ok, detail=""):
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}", flush=True)
    if not ok:
        FAILED.append(label)


class Case:
    def __init__(self, root, name):
        self.dir = Path(root) / name
        self.dir.mkdir()
        self.state = self.dir / "state"
        os.environ["G070_DIR"] = str(self.dir)
        import g070_tools as t
        self.t = t
        self.mission = t.runtime(self.state).create(DEMO_REQUEST)["id"]
        self.store = Store(self.state)

    def env(self, **extra):
        return dict(os.environ, G070_DIR=str(self.dir), PYTHONPATH=f"{SRC}:{HERE}", PYTHONDONTWRITEBYTECODE="1",
                    **{k: str(v) for k, v in extra.items()})

    def start(self, point="", **extra):
        p = subprocess.Popen([sys.executable, "-c", RUNNER, SRC, HERE, str(self.state), self.mission, point],
                             env=self.env(**extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        STARTED.append(p)
        return p

    def finish(self, p, timeout=30):
        out, err = p.communicate(timeout=timeout)
        try:
            return json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"status": f"EXIT {p.returncode}", "stderr": err.strip()[-160:]}

    def run(self, point="", **extra):
        return self.finish(self.start(point, **extra))

    def calls(self):
        return self.t.calls()

    def mission_state(self):
        m = self.store.get(self.mission)
        return {"status": m["status"], "code": (m.get("error") or {}).get("code"), "phase": m["phase"],
                "cancel": m["cancel_requested"], "calls": [c["status"] for c in m["calls"]],
                "late_receipt": any("late_receipt" in c for c in m["calls"]),
                "verified": sum(c["status"] == "VERIFIED" for c in m["calls"])}

    def wait_log(self, kind, n=1, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.calls()[kind] >= n:
                return True
            time.sleep(0.02)
        return False

    def worker_pid(self):
        for line in (self.dir / "calls.log").read_text().splitlines():
            if line.startswith("exec-start"):
                return int(line.split()[1])
        return None

    def hold(self, on=True):
        p = self.dir / "hold"
        if on:
            p.touch()
        elif p.exists():
            p.unlink()


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:   # a zombie is not alive
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except OSError:
        return False


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g070-") as tmp:
        root = Path(tmp)
        c = Case(root, "nominal")
        r = c.run()
        steps = len(c.store.get(c.mission)["calls"])
        n = c.calls()
        check("N nominal : chaque étape exécutée et vérifiée une fois", r["status"] == "SUCCEEDED"
              and n == {"exec-start": steps, "exec-end": steps, "verify": steps}, f"{steps} étapes, journal {n}")
        r2 = c.run()
        check("N reprise d'une mission réussie : aucun nouvel appel", r2["status"] == "SUCCEEDED" and c.calls() == n)

        print("== A. deux exécutants")
        c = Case(root, "two")
        c.hold()
        a = c.start()
        check("A le premier exécutant est dans l'outil", c.wait_log("exec-start"))
        t0 = time.monotonic()
        b = c.run()
        check("A le second exécutant est refusé sans attendre (Busy)", b["status"] == "BUSY",
              f"{time.monotonic() - t0:.2f} s, état pendant : {c.mission_state()['phase']}")
        c.hold(False)
        ra = c.finish(a)
        n = c.calls()
        check("A le premier termine ; aucun double appel", ra["status"] == "SUCCEEDED"
              and n["exec-start"] == steps and n["verify"] == steps, str(n))

        print("== B. annulation avant l'outil")
        c = Case(root, "cancel-before")
        c.store.request_cancel(c.mission)
        r = c.run()
        check("B annulation demandée avant tout : CANCELLED, zéro appel d'outil",
              r["status"] == "CANCELLED" and c.calls()["exec-start"] == 0, f"{r} {c.calls()}")

        print("== C. annulation pendant l'outil")
        c = Case(root, "cancel-during")
        c.hold()
        a = c.start()
        c.wait_log("exec-start")
        worker = c.worker_pid()
        c.store.request_cancel(c.mission)
        ra = c.finish(a)
        st = c.mission_state()
        gone = not alive(worker)
        check("C effet inconnu, jamais « annulée » : REVIEW_REQUIRED / CANCELLED",
              ra["status"] == "REVIEW_REQUIRED" and ra["code"] == "CANCELLED" and st["verified"] == 0,
              f"{ra} ; appels {st['calls']}")
        check("C l'exécutant a été arrêté dans l'outil (exec-end absent)", gone and c.calls()["exec-end"] == 0,
              f"pid {worker} vivant={not gone}, journal {c.calls()}")
        c.hold(False)
        diag = inspect_runtime(c.state, c.mission)
        check("C diagnostic : revue requise et annulation non prouvée",
              {"EFFECT_UNKNOWN_REVIEW_REQUIRED", "CANCELLATION_REQUESTED_NOT_PROOF_OF_STOP"} <= set(diag["hints"])
              and diag["authorizes_execution"] is False, str(diag["hints"]))
        r = c.run()
        check("C reprise : reste en revue, aucun nouvel appel", r["status"] == "REVIEW_REQUIRED"
              and c.calls()["exec-start"] == 1)

        print("== D. annulation après un résultat reçu (coupure après RESULT_SAVED)")
        c = Case(root, "cancel-after")
        crash = c.run(point="RESULT_SAVED")
        before = c.calls()
        c.store.request_cancel(c.mission)
        r = c.run()
        st = c.mission_state()
        after = c.calls()
        check("D le résultat reçu est vérifié malgré l'annulation, puis CANCELLED",
              r["status"] == "CANCELLED" and st["calls"][:1] == ["VERIFIED"] and after["verify"] == before["verify"] + 1,
              f"coupure {crash['status']} ; appels {st['calls']} ; journal {before} → {after}")
        check("D aucune nouvelle exécution d'outil après l'annulation", after["exec-start"] == before["exec-start"] == 1)
        check("D annulée ≠ réussie : aucun résultat de mission", c.store.get(c.mission)["result"] is None)

        print("== E. reçu tardif : l'outil finit pendant que l'annulation est enregistrée (5 essais)")
        outcomes = []
        for i in range(5):
            c = Case(root, f"late-{i}")
            (c.dir / "cancel-at-end").write_text(json.dumps([str(c.state), c.mission]))
            r = c.run()
            st = c.mission_state()
            outcomes.append((r["status"], r["code"], st["late_receipt"], st["verified"], c.calls()["exec-end"]))
            (c.dir / "cancel-at-end").unlink()
            again = c.run()
            if again["status"] != r["status"] or c.calls()["exec-start"] != 1:
                outcomes.append(("REPRISE", again))
        late = [o for o in outcomes if o[2]]
        check("E toujours REVIEW_REQUIRED / CANCELLED, jamais vérifié, jamais réexécuté",
              all(o[:2] == ("REVIEW_REQUIRED", "CANCELLED") and o[3] == 0 for o in outcomes) and len(outcomes) == 5,
              f"reçu tardif conservé dans {len(late)}/5 essais (course réelle avec l'arrêt de l'exécutant)")

        print("== F. verrou de mission réellement détenu par un autre processus")
        c = Case(root, "lock")
        holder = subprocess.Popen([sys.executable, "-c",
                                   "import fcntl,sys,time;f=open(sys.argv[1],'a');fcntl.flock(f,fcntl.LOCK_EX);"
                                   "print('held',flush=True);time.sleep(30)", str(c.state / f"{c.mission}.lock")],
                                  stdout=subprocess.PIPE, text=True)
        STARTED.append(holder)
        holder.stdout.readline()
        r = c.run()
        check("F Busy, aucun appel tant que le verrou est détenu", r["status"] == "BUSY" and c.calls()["exec-start"] == 0)
        holder.kill()
        holder.wait(5)
        check("F verrou libéré par la fin du détenteur : exécution normale", c.run()["status"] == "SUCCEEDED")

        print("== G. exécutant tué (SIGKILL) dans l'outil")
        c = Case(root, "kill-worker")
        c.hold()
        a = c.start()
        c.wait_log("exec-start")
        os.kill(c.worker_pid(), signal.SIGKILL)
        ra = c.finish(a)
        c.hold(False)
        check("G effet inconnu : REVIEW_REQUIRED / WORKER_LOST, aucune relance",
              ra["status"] == "REVIEW_REQUIRED" and ra["code"] == "WORKER_LOST" and c.run()["status"] == "REVIEW_REQUIRED"
              and c.calls()["exec-start"] == 1, f"{ra} {c.calls()}")

        print("== H. runtime tué (SIGKILL) pendant que l'exécutant est dans l'outil")
        c = Case(root, "kill-runtime")
        c.hold()
        a = c.start()
        c.wait_log("exec-start")
        worker = c.worker_pid()
        a.kill()
        a.wait(5)
        orphan = alive(worker)
        diag = inspect_runtime(c.state, c.mission)
        leases = [x["lease"]["state"] for x in diag["calls"]]
        check("H l'exécutant orphelin continue ; le diagnostic voit son bail détenu",
              orphan and "HELD_AT_SAMPLE" in leases and "LOCAL_LOCK_HELD" in diag["hints"], f"baux {leases}")
        r = c.run()
        check("H reprise pendant que l'orphelin travaille : revue, aucune seconde exécution",
              r["status"] == "REVIEW_REQUIRED" and r["code"] == "UNKNOWN_EFFECT" and c.calls()["exec-start"] == 1, str(r))
        c.hold(False)
        finished = c.wait_log("exec-end")
        deadline = time.monotonic() + 10
        while alive(worker) and time.monotonic() < deadline:
            time.sleep(0.05)
        diag = inspect_runtime(c.state, c.mission)
        receipts = [x["receipt"]["state"] for x in diag["calls"]]
        check("H l'orphelin a fini l'effet APRÈS la revue ; son reçu reste non adopté",
              finished and not alive(worker) and "PRESENT_UNVERIFIED" in receipts
              and c.mission_state()["status"] == "REVIEW_REQUIRED" and c.mission_state()["verified"] == 0,
              f"reçus {receipts}")

    leftovers = [p.pid for p in STARTED if p.poll() is None]
    for p in STARTED:
        if p.poll() is None:
            p.kill()
    check("tous les processus créés sont arrêtés", not leftovers, str(leftovers))
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
