# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_g056.py
# Description : Coût de _ensure_invocation_budget selon l'historique, et variante filtrée en SQL (C-TASK-G056)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 bench_g056.py <frozen eidolon-core/src> [--proposal]

Synthetic missions only, in temporary folders. A mission is created by the real Runtime
(limit 4096), then N INVOCATION_RESERVED events plus 2 filler events per reservation are
appended with sqlite3, and the mission's counter is set to N: the same shape as a long
mission, without running N workers. --proposal measures the SQL-filtered variant
(proposal-budget-query.diff) applied on the same copy."""
import json
import multiprocessing
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)

from eidolon_core.memory import DEMO_REQUEST  # noqa: E402
from eidolon_core.runtime import InvocationBudgetError, Limits, Runtime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

SIZES = (64, 256, 1024, 4095)   # 4095: the last check before the 4096th reservation
FILLER = {"call_id": "c-" + "0" * 32, "note": "x" * 240}     # about 300 bytes, like a worker event


def build(directory, n):
    store = Store(directory)
    rt = Runtime(store, limits=Limits(max_invocations=4096))
    m = rt.create(DEMO_REQUEST)
    db = sqlite3.connect(Path(directory) / "missions.sqlite3")
    rows = []
    for i in range(1, n + 1):
        rows.append((m["id"], "2026-10-07T10:00:00+00:00", "INVOCATION_RESERVED", json.dumps(
            {"ordinal": i, "limit": 4096, "phase": "EXECUTING", "verification": False, "call_id": None})))
        rows += [(m["id"], "2026-10-07T10:00:00+00:00", "G056_FILLER", json.dumps(FILLER))] * 2
    db.executemany("INSERT INTO events (mission_id,at,kind,detail) VALUES (?,?,?,?)", rows)
    body = json.loads(db.execute("SELECT body FROM missions WHERE id=?", (m["id"],)).fetchone()[0])
    body["invocation_budget"]["used"] = n
    db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(body), m["id"]))
    db.commit()
    events = db.execute("SELECT count(*) FROM events WHERE mission_id=?", (m["id"],)).fetchone()[0]
    db.close()
    return m["id"], events


def timed(fn, repeat):
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples) * 1000


def check_once(directory, identity):
    rt = Runtime(Store(directory), limits=Limits(max_invocations=4096))
    m = rt.store.get(identity)
    rt._ensure_invocation_budget(m)


def worker(args):
    directory, identity, repeat = args
    rt = Runtime(Store(directory), limits=Limits(max_invocations=4096))
    m = rt.store.get(identity)
    t0 = time.perf_counter()
    for _ in range(repeat):
        rt._ensure_invocation_budget(m)
    return (time.perf_counter() - t0) / repeat * 1000


def tamper_checks(directory, identity):
    """The detection the optimisation must keep (G052 T1-T5 shapes, on copies)."""
    import shutil
    out = []

    def run(name, sql):
        d = Path(directory).parent / ("t-" + name)
        shutil.copytree(directory, d)
        db = sqlite3.connect(d / "missions.sqlite3")
        for s, a in sql:
            db.execute(s, a)
        db.commit()
        db.close()
        try:
            check_once(d, identity)
            out.append((name, "ACCEPTÉ"))
        except InvocationBudgetError as exc:
            out.append((name, exc.code))
    last = ("SELECT max(sequence) FROM events WHERE kind='INVOCATION_RESERVED'",)
    run("compteur seul diminué", [("UPDATE missions SET body=json_set(body,'$.invocation_budget.used',"
                                   "json_extract(body,'$.invocation_budget.used')-1)", ())])
    run("dernière réservation supprimée", [("DELETE FROM events WHERE sequence=(" + last[0] + ")", ())])
    run("réservation au milieu renommée", [("UPDATE events SET kind='G056_FILLER' WHERE sequence=(SELECT min(sequence) "
                                            "FROM events WHERE kind='INVOCATION_RESERVED')+3*10", ())])
    run("ordinal du milieu modifié", [("UPDATE events SET detail=json_set(detail,'$.ordinal',999999) WHERE sequence=("
                                       "SELECT min(sequence) FROM events WHERE kind='INVOCATION_RESERVED')", ())])
    run("limite d'une réservation modifiée", [("UPDATE events SET detail=json_set(detail,'$.limit',64) WHERE sequence=("
                                               + last[0] + ")", ())])
    run("détail non objet", [("UPDATE events SET detail='[]' WHERE sequence=(" + last[0] + ")", ())])
    run("réécriture cohérente (compteur et événement)", [
        ("DELETE FROM events WHERE sequence=(" + last[0] + ")", ()),
        ("UPDATE missions SET body=json_set(body,'$.invocation_budget.used',json_extract(body,'$.invocation_budget.used')-1)", ())])
    return out


def main():
    label = "proposition" if "--proposal" in sys.argv else "actuel"
    print(f"== {label} ({SRC})")
    with tempfile.TemporaryDirectory(prefix="eidolon-g056-") as tmp:
        for n in SIZES:
            d = Path(tmp) / f"n{n}"
            identity, events = build(d, n)
            size = (d / "missions.sqlite3").stat().st_size
            store = Store(d)
            rt = Runtime(store, limits=Limits(max_invocations=4096))
            m = store.get(identity)
            repeat = 30 if n <= 1024 else 15
            t_check = timed(lambda: rt._ensure_invocation_budget(m), repeat)
            t_events = timed(lambda: store.events(identity), repeat)
            print(f"N={n:5d} : événements={events:6d} ; base={size / 1024:8.0f} Kio ; "
                  f"_ensure_invocation_budget médiane={t_check:8.2f} ms ; store.events seul={t_events:8.2f} ms")
            if n == 4095:
                with multiprocessing.get_context("spawn").Pool(4) as pool:
                    per_call = pool.map(worker, [(str(d), identity, 10)] * 4)
                print(f"N=4095, 4 processus × 10 vérifications simultanées : {', '.join(f'{x:.1f}' for x in per_call)} ms par appel")
                print("altérations (détection à conserver) :")
                for name, result in tamper_checks(d, identity):
                    print(f"  {name} : {result}")
        print("coût cumulé estimé jusqu'à N (somme des vérifications avant chaque réservation) : voir README")


if __name__ == "__main__":
    main()
