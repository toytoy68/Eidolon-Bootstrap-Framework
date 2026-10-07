# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g061.py
# Description : Contre-revue des diagnostics runtime-inspect, recovery-inspect et consultations CLI (C-TASK-G061)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g061.py <frozen eidolon-core/src>

Synthetic states only, built by the frozen Core in temporary folders. Every diagnostic is
run through the CLI (exit codes, JSON/human), and every state folder is fingerprinted
before and after (path, size, SHA-256, mtime) to detect any creation or mutation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True

from eidolon_core.memory import DEMO_REQUEST  # noqa: E402
from eidolon_core.runtime import Limits, Runtime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

# The demo request is the only catalogue request runnable end to end; it stands for the private
# request text that diagnostics must never export (any other text is refused as unsupported).
SECRET = DEMO_REQUEST
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


def cli(state, *args, human=False):
    pre = [sys.executable, "-m", "eidolon_core", "--state", str(state)] + (["--format", "human"] if human else [])
    p = subprocess.run(pre + [str(a) for a in args], capture_output=True, text=True, env=ENV, timeout=120)
    out = p.stdout.strip()
    try:
        value = json.loads(out) if out and not human else out
    except ValueError:
        value = out
    return p.returncode, value, p.stderr.strip()


def tree(path):
    path = Path(path)
    if not path.exists():
        return None
    return {str(p.relative_to(path)): (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(path.rglob("*")) if p.is_file()}


def brief(code, value, err):
    if isinstance(value, dict):
        keys = {k: value[k] for k in ("status", "phase", "hints", "invocation_budget", "changed_during_sampling",
                                      "execution_lock", "error", "historical_only") if k in value}
        return f"code {code} {json.dumps(keys, ensure_ascii=False)}"
    return f"code {code} {(value or err)[:160]!r}"


def leaks(*texts):
    return [SECRET in t for t in texts]


def demo(state, request=None, limit=64, checkpoint=None):
    rt = Runtime(Store(state), limits=Limits(max_invocations=limit), checkpoint=checkpoint)
    m = rt.create(request or DEMO_REQUEST)
    return rt, m["id"]


CRASH = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
def checkpoint(kind):
    if kind == sys.argv[3]:
        os._exit(9)
rt = Runtime(Store(sys.argv[2]), checkpoint=checkpoint)
m = rt.create(DEMO_REQUEST)
print(m["id"], flush=True)
rt.run(m["id"])
"""


def crashed(state, point):
    p = subprocess.run([sys.executable, "-c", CRASH, SRC, str(state), point], capture_output=True, text=True, env=ENV)
    time.sleep(1.0)        # an orphan worker may finish writing its receipt
    return p.stdout.split()[0]


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g061-") as tmp:
        tmp = Path(tmp)

        print("== R. runtime-inspect")
        absent = tmp / "absent"
        r = cli(absent, "runtime-inspect", "m-" + "0" * 32)
        print(f"R1 état absent : {brief(*r)} ; dossier créé : {absent.exists()}")
        st = tmp / "r"
        rt, mid = demo(st)
        rt.run(mid)
        before = tree(st)
        r = cli(st, "runtime-inspect", mid)
        h = cli(st, "runtime-inspect", mid, human=True)
        print(f"R2 mission terminée : {brief(*r)} ; humain code {h[0]} ; fichiers identiques : {tree(st) == before} ; "
              f"secret dans JSON/humain : {leaks(json.dumps(r[1]), h[1])}")
        print(f"R2 inconnue : {brief(*cli(st, 'runtime-inspect', 'm-' + 'f' * 32))} ; mal formée : {brief(*cli(st, 'runtime-inspect', '../x'))}")
        for point in ("WORKER_SPAWNED", "RESULT_SAVED"):
            s2 = tmp / f"r-{point}"
            mid2 = crashed(s2, point)
            before = tree(s2)
            r = cli(s2, "runtime-inspect", mid2)
            calls = r[1].get("calls") if isinstance(r[1], dict) else None
            print(f"R3 arrêt après {point} : {brief(*r)} ; appels {calls} ; fichiers identiques : {tree(s2) == before}")
        lock = st / f"{mid}.lock"
        holder = subprocess.Popen([sys.executable, "-c", "import fcntl,sys,time; f=open(sys.argv[1],'a'); "
                                   "fcntl.flock(f, fcntl.LOCK_EX); print('ok', flush=True); time.sleep(3)", str(lock)],
                                  stdout=subprocess.PIPE, text=True)
        holder.stdout.readline()
        held = cli(st, "runtime-inspect", mid)
        holder.wait()
        free = cli(st, "runtime-inspect", mid)
        print(f"R4 verrou de mission tenu par un autre processus : {held[1]['execution_lock']} ; relâché : {free[1]['execution_lock']}")
        db = sqlite3.connect(st / "missions.sqlite3")
        stop = threading.Event()

        def writer():
            w = sqlite3.connect(st / "missions.sqlite3", timeout=5)
            while not stop.is_set():
                w.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                          (mid, "2026-10-07T00:00:00+00:00", "G061_WRITER", "{}"))
                w.commit()
            w.close()
        t = threading.Thread(target=writer)
        t.start()
        flags = [cli(st, "runtime-inspect", mid) for _ in range(15)]
        stop.set()
        t.join()
        db.close()
        print(f"R5 15 inspections sous écrivain concurrent : codes {sorted({f[0] for f in flags})} ; "
              f"erreurs {sorted({f[2][:110] for f in flags if f[0]})} ; "
              f"changed_during_sampling vrai {sum(1 for f in flags if isinstance(f[1], dict) and f[1].get('changed_during_sampling'))} fois ; "
              f"indices {sorted({h for f in flags if isinstance(f[1], dict) for h in f[1].get('hints', [])})}")

        print("== B. budget dans runtime-inspect")
        cases = {}
        s3 = tmp / "b-legacy"
        rt, m3 = demo(s3, limit=None)
        rt.run(m3)
        cases["ancienne sans limite"] = (s3, m3)
        s4 = tmp / "b-exhausted"
        rt, m4 = demo(s4, limit=3)
        rt.run(m4)
        cases["épuisé (limite 3)"] = (s4, m4)
        s5 = tmp / "b-invalid"
        rt, m5 = demo(s5)
        rt.run(m5)
        c = sqlite3.connect(s5 / "missions.sqlite3")
        c.execute("UPDATE missions SET body=json_set(body,'$.invocation_budget.used',1) WHERE id=?", (m5,))
        c.commit()
        c.close()
        cases["compteur altéré"] = (s5, m5)
        s6 = tmp / "b-big"
        rt, m6 = demo(s6)
        rt.run(m6)
        c = sqlite3.connect(s6 / "missions.sqlite3")
        c.execute("UPDATE events SET detail=json_set(detail,'$.pad',?) WHERE mission_id=? AND kind='INVOCATION_RESERVED' "
                  "AND sequence=(SELECT min(sequence) FROM events WHERE mission_id=? AND kind='INVOCATION_RESERVED')",
                  ("x" * 20000, m6, m6))
        c.commit()
        c.close()
        cases["événement de 20 Kio"] = (s6, m6)
        for name, (s, m) in cases.items():
            before = tree(s)
            r = cli(s, "runtime-inspect", m)
            print(f"B {name} : {brief(*r)} ; fichiers identiques : {tree(s) == before} ; secret : {leaks(json.dumps(r[1]))}")
        # A resume is still governed by run, not by the diagnostic.
        r = Runtime(Store(s4), limits=Limits(max_invocations=3)).run(m4)
        print(f"B reprise de la mission épuisée par run : {r['status']} / {r['error']['code'] if r['error'] else None}")

        print("== V. recovery-prepare et recovery-inspect")
        src = tmp / "v-src"
        rt, mv = demo(src)
        rt.run(mv)
        dest = tmp / "v-copy"
        p = subprocess.run([sys.executable, "-m", "eidolon_core", "recovery-prepare", "--source", str(src / "missions.sqlite3"),
                            "--destination", str(dest), "--actor", "g061", "--reason", "revue jean@example.invalid"],
                           capture_output=True, text=True, env=ENV)
        print(f"V préparation : code {p.returncode}")
        before = tree(dest)
        r = cli(dest, "recovery-inspect")
        rm = cli(dest, "recovery-inspect", "--mission-id", mv)
        print(f"V inspection : code {r[0]} historical_only={r[1].get('historical_only')} ; mission : code {rm[0]} "
              f"{ {k: rm[1]['mission'][k] for k in list(rm[1]['mission'])[:4]} if isinstance(rm[1], dict) else rm[1]} ; "
              f"fichiers identiques : {tree(dest) == before}")
        print(f"V annotation reason exportée telle quelle (courriel présent) : {'jean@example.invalid' in json.dumps(r[1])} ; "
              f"secret dans la projection de mission : {SECRET in json.dumps(rm[1].get('mission', {}))}")
        print(f"V mission absente : {brief(*cli(dest, 'recovery-inspect', '--mission-id', 'm-' + 'e' * 32))}")
        for name, args in (("runtime-inspect", ["runtime-inspect", mv]), ("client-missions", ["client-missions"]),
                           ("client-snapshot", ["client-snapshot", mv]), ("run", ["run", mv])):
            r = cli(dest, *args)
            print(f"V {name} sur la copie : {brief(*r)}")
        print(f"V copie toujours REVIEW_ONLY : {(dest / 'RECOVERY-REVIEW-ONLY').exists()} ; fichiers identiques : {tree(dest) == before}")
        rep = json.loads(sqlite3.connect(dest / "missions.sqlite3").execute(
            "SELECT value FROM sync_metadata WHERE key='recovery_report'").fetchone()[0])

        def variant(name, value=None, raw=None, sql=None):
            d = tmp / ("v-" + name.replace(" ", "-")[:30])
            shutil.copytree(dest, d)
            c = sqlite3.connect(d / "missions.sqlite3")
            if raw is not None or value is not None:
                c.execute("UPDATE sync_metadata SET value=? WHERE key='recovery_report'",
                          (raw if raw is not None else json.dumps(value),))
            if sql:
                c.executescript(sql)
            c.commit()
            c.close()
            b = tree(d)
            r = cli(d, "recovery-inspect")
            print(f"V {name} : {brief(*r)} ; fichiers identiques : {tree(d) == b}")
        old = dict(rep)
        old.pop("capture_semantics", None)
        variant("ancien rapport sans capture_semantics", old)
        variant("source_store_id = store_id", dict(rep, source_store_id=rep["store_id"]))
        variant("execution_authority vrai", dict(rep, execution_authority=True))
        variant("capture_semantics inconnue", dict(rep, capture_semantics="raw-copy"))
        variant("JSON malformé", raw="{")
        variant("clé dupliquée", raw=json.dumps(rep)[:-1] + ', "mode": "REVIEW_ONLY"}')
        variant("NaN", raw=json.dumps(dict(rep, extra=float("nan")), allow_nan=True))
        variant("rapport de 40 000 octets", dict(rep, reason="x" * 40000))
        variant("store_id de base différent", sql="UPDATE sync_metadata SET value='s-" + "9" * 32 + "' WHERE key='store_id';")
        variant("10 001 missions", sql="WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<10001) "
                "INSERT INTO missions (id,revision,body) SELECT printf('m-%032x', i), 0, '{}' FROM n;")
        variant("rapport absent", sql="DELETE FROM sync_metadata WHERE key='recovery_report';")
        human = cli(dest, "recovery-inspect", human=True)
        print(f"V format humain : code {human[0]} ; commence par l'en-tête ECT : {human[1][:40]!r}")

        print("== C. consultations CLI client (C-027)")
        st = tmp / "c"
        rt, mc = demo(st)
        rt.run(mc)
        before = tree(st)
        lst = cli(st, "client-missions")
        snap = cli(st, "client-snapshot", mc)
        cursor = tmp / "cursor.json"
        cursor.write_text(json.dumps(snap[1]["cursor"]))
        poll = cli(st, "client-poll", mc, "--cursor", cursor)
        print(f"C missions/snapshot/poll : codes {lst[0]}/{snap[0]}/{poll[0]} ; fichiers identiques : {tree(st) == before} ; "
              f"secret : {leaks(json.dumps(lst[1]), json.dumps(snap[1]), json.dumps(poll[1]))}")
        print(f"C état absent : {brief(*cli(tmp / 'c-absent', 'client-missions'))} ; créé : {(tmp / 'c-absent').exists()}")
        for name, sql in (("table command_receipts absente", "DROP TABLE command_receipts;"),
                          ("schéma ancien (user_version 0)", "PRAGMA user_version=0;"),
                          ("sync_metadata absente", "DROP TABLE sync_metadata;")):
            d = tmp / ("c-" + name[:12].replace(" ", "-"))
            shutil.copytree(st, d)
            c = sqlite3.connect(d / "missions.sqlite3")
            c.executescript(sql)
            c.commit()
            c.close()
            b = tree(d)
            res = [cli(d, *a) for a in (["client-missions"], ["client-snapshot", mc])]
            print(f"C {name} : {[brief(*x) for x in res]} ; fichiers identiques : {tree(d) == b}")
        d = tmp / "c-writer"
        shutil.copytree(st, d)
        stop = threading.Event()

        def writer2():
            w = sqlite3.connect(d / "missions.sqlite3", timeout=5)
            while not stop.is_set():
                w.execute("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)",
                          (mc, "2026-10-07T00:00:00+00:00", "G061_WRITER", "{}"))
                w.commit()
            w.close()
        t = threading.Thread(target=writer2)
        t.start()
        res = [cli(d, "client-snapshot", mc) for _ in range(10)]
        stop.set()
        t.join()
        print(f"C 10 captures sous écrivain concurrent : codes {sorted({x[0] for x in res})} ; "
              f"erreurs {sorted({x[2][:110] for x in res if x[0]})} ; "
              f"as_of croissants : {[x[1]['snapshot']['as_of_sequence'] for x in res if isinstance(x[1], dict) and 'snapshot' in x[1]][:10]}")


if __name__ == "__main__":
    main()
