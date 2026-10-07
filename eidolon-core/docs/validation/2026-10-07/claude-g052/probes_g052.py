# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g052.py
# Description : Contre-revue du budget d'invocations C-015 et du seuil des reçus (C-TASK-G052)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g052.py <frozen 7d8efb9>/eidolon-core/src <frozen 0fdf18e>/eidolon-core/src

Synthetic missions (DEMO_REQUEST, default simulated tools) in temporary folders; each
crash is an os._exit in a subprocess started here. Alterations are made on copies."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SRC, C012 = (str(Path(p).resolve()) for p in sys.argv[1:3])
sys.path.insert(0, SRC)

from eidolon_core.http_api import ReadOnlyStore  # noqa: E402
from eidolon_core.receipt_lookup import ReceiptLookupError, lookup  # noqa: E402

RUN = r"""
import json, os, sys
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
state, limit, identity, crash_at = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
seen = {"n": 0}
def checkpoint(kind):
    if crash_at == "kind:" + kind:
        os._exit(9)              # after this event's commit
    if kind == "INVOCATION_RESERVED" and crash_at.isdigit():
        seen["n"] += 1
        if seen["n"] == int(crash_at):
            os._exit(9)          # after the reservation commit, before the worker
limit = None if limit == "none" else int(limit)
rt = Runtime(Store(state), limits=Limits(max_invocations=limit), checkpoint=checkpoint)
try:
    if identity == "new":
        identity = rt.create(DEMO_REQUEST)["id"]
    m = rt.run(identity)
    print(json.dumps({"id": m["id"], "status": m["status"], "code": (m.get("error") or {}).get("code"),
                      "budget": m.get("invocation_budget")}))
except Exception as exc:
    print(json.dumps({"id": identity, "error": type(exc).__name__, "code": str(exc)[:80]}))
"""

BUILD = r"""
import json, sys
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CancelCommands
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
store = Store(sys.argv[1]); prefix = sys.argv[2]
rt = Runtime(store)
m = rt.create(DEMO_REQUEST)
store_id = ClientSync(store).snapshot(m["id"])["store_id"]
q = {}
for i in range(2):
    c = dict(protocol="eidolon-cancel-command/1", store_id=store_id, client_id="g052", command_key=f"{prefix}{i}",
             mission_id=m["id"], actor="g052", reason="synthetique")
    CancelCommands(store).submit(c)
    q[c["command_key"]] = {k: c[k] for k in ("store_id", "client_id", "command_key", "mission_id")}
print(json.dumps(q))
"""

SUBMIT = r"""
import json, os, sqlite3, sys
import eidolon_core.store as store_mod
from eidolon_core.commands import CancelCommands
from eidolon_core.store import Store
real = sqlite3.connect
def connect(*a, **k):
    db = real(*a, **k)
    db.create_function("g052_crash", 0, lambda: os._exit(9))
    return db
store_mod.sqlite3.connect = connect
try:
    print(json.dumps(CancelCommands(Store(sys.argv[1])).submit(json.loads(sys.argv[2]))))
except Exception as exc:
    print("ERROR", type(exc).__name__, str(exc)[:60])
"""


def sub(src, code, *args):
    env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", code, *map(str, args)], env=env, capture_output=True, text=True, timeout=180)


def run(state, limit, identity="new", crash_at=0):
    p = sub(SRC, RUN, state, limit, identity, crash_at)
    return json.loads(p.stdout) if p.stdout.strip() else {"exit": p.returncode, "stderr": p.stderr[-120:]}


def reservations(state, identity):
    db = sqlite3.connect(Path(state) / "missions.sqlite3")
    rows = [json.loads(r[0]) for r in db.execute(
        "SELECT detail FROM events WHERE mission_id=? AND kind='INVOCATION_RESERVED' ORDER BY sequence", (identity,))]
    body = json.loads(db.execute("SELECT body FROM missions WHERE id=?", (identity,)).fetchone()[0])
    started = db.execute("SELECT count(*) FROM events WHERE mission_id=? AND kind='CALL_STARTED'", (identity,)).fetchone()[0]
    db.close()
    return [r["ordinal"] for r in rows], body.get("invocation_budget"), started


def edit_db(state, fn):
    db = sqlite3.connect(Path(state) / "missions.sqlite3")
    fn(db)
    db.commit()
    db.close()


def ask(directory, query):
    try:
        r = lookup(ReadOnlyStore(directory), query)
        return f"{r['status']} {r.get('receipt_binding')}"
    except ReceiptLookupError as exc:
        return f"{exc.status} {exc.code}"


def receipt_edit(key, *, drop_hash=False, alter=False):
    def apply(db):
        body = json.loads(db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0])
        if alter:
            body["mission_status_at_recording"] = "RUNNING"
            db.execute("UPDATE command_receipts SET body=? WHERE command_key=?", (json.dumps(body), key))
        if drop_hash:
            raw = db.execute("SELECT detail FROM events WHERE sequence=?", (body["event_sequence"],)).fetchone()[0]
            detail = json.loads(raw)
            detail.pop("receipt_sha256", None)
            db.execute("UPDATE events SET detail=? WHERE sequence=?", (json.dumps(detail), body["event_sequence"]))
    return apply


def boundary(directory):
    db = sqlite3.connect(Path(directory) / "missions.sqlite3")
    row = db.execute("SELECT value FROM sync_metadata WHERE key='receipt_hash_required_from'").fetchone()
    db.close()
    return row[0] if row else None


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g052-") as tmp:
        tmp = Path(tmp)
        print("== I. budget : limites 1 à 5 sur la mission de démonstration")
        for limit in range(1, 6):
            state = tmp / f"i{limit}"
            r = run(state, limit)
            ordinals, budget, started = reservations(state, r["id"])
            again = run(state, limit, r["id"])
            print(f"I limite {limit}: {r['status']} {r['code']} ; budget={budget} ; ordinaux={ordinals} ; "
                  f"CALL_STARTED={started} ; relance → {again['status']} {again['code']} {again['budget']}")

        print("== K. arrêt brutal juste après une réservation (avant le worker)")
        for crash_at in (1, 2, 3):
            state = tmp / f"k{crash_at}"
            first = run(state, 4, crash_at=crash_at)
            db = sqlite3.connect(state / "missions.sqlite3")
            identity = db.execute("SELECT id FROM missions").fetchone()[0]
            db.close()
            before = reservations(state, identity)
            r = run(state, 4, identity)
            after = reservations(state, identity)
            print(f"K arrêt à la réservation {crash_at}: code {first.get('exit')} ; réservé={before[0]} → "
                  f"reprise : {r['status']} {r['code']} ; ordinaux={after[0]} ; budget={after[1]}")

        print("== F. configuration figée")
        def unfinished(name, limit):
            # Interrupted after its first reservation: the mission is not terminal.
            state = tmp / name
            run(state, limit, crash_at="kind:CONTEXT_SAVED")
            db = sqlite3.connect(state / "missions.sqlite3")
            identity = db.execute("SELECT id FROM missions").fetchone()[0]
            db.close()
            return state, identity
        for other in ("65", "4", "none"):
            state, identity = unfinished(f"f{other}", 64)
            print(f"F créée à 64 (inachevée), reprise à {other}: {run(state, other, identity)}")
        state, identity = unfinished("fback", 64)
        print(f"F reprise à 65 puis de nouveau à 64 (bonne valeur) : {run(state, '65', identity)['code']} → {run(state, 64, identity)}")
        state, identity = unfinished("flegacy", "none")
        print(f"F créée sans budget (inachevée), reprise à 64 : {run(state, 64, identity)}")

        print("== T. altérations du compteur et du journal (copies)")
        base = tmp / "t"
        run(base, 8, crash_at=1)             # interrupted in RECALL: resuming needs new invocations
        db = sqlite3.connect(base / "missions.sqlite3")
        identity = db.execute("SELECT id FROM missions").fetchone()[0]
        db.close()

        def budget_edit(fn):
            def apply(db):
                body = json.loads(db.execute("SELECT body FROM missions WHERE id=?", (identity,)).fetchone()[0])
                fn(body)
                db.execute("UPDATE missions SET body=? WHERE id=?", (json.dumps(body), identity))
            return apply

        def drop_last(db):
            db.execute("DELETE FROM events WHERE sequence=(SELECT max(sequence) FROM events "
                       "WHERE mission_id=? AND kind='INVOCATION_RESERVED')", (identity,))
        cases = [
            ("T1 compteur seul diminué", budget_edit(lambda b: b["invocation_budget"].update(used=b["invocation_budget"]["used"] - 1))),
            ("T2 dernier événement de réservation seul supprimé", drop_last),
            ("T3 compteur ET événement retirés ensemble (cohérent)",
             lambda db: (drop_last(db), budget_edit(lambda b: b["invocation_budget"].update(used=b["invocation_budget"]["used"] - 1))(db))),
            ("T4 limite de la mission portée à 4096", budget_edit(lambda b: b["invocation_budget"].update(limit=4096))),
            ("T6 témoin sans altération", lambda db: None),
            ("T5 champ invocation_budget supprimé", budget_edit(lambda b: b.pop("invocation_budget"))),
        ]
        for i, (name, fn) in enumerate(cases):
            state = tmp / f"t{i}"
            shutil.copytree(base, state)
            edit_db(state, fn)
            out = run(state, 8, identity)
            print(f"{name}: {out.get('status')} {out.get('code')} {out.get('budget')} ; ordinaux={reservations(state, identity)[0]}")

        print("== C. 4 processus sur la même mission en même temps (limite 4)")
        state = tmp / "c"
        run(state, 4, crash_at=1)
        db = sqlite3.connect(state / "missions.sqlite3")
        identity = db.execute("SELECT id FROM missions").fetchone()[0]
        db.close()
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
        procs = [subprocess.Popen([sys.executable, "-c", RUN, str(state), "4", identity, "0"], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        outs = [json.loads(p.communicate(timeout=180)[0]) for p in procs]
        ordinals, budget, started = reservations(state, identity)
        print(f"C réponses : {sorted({(o.get('status') or o.get('error'), o.get('code')) for o in outs}, key=str)} ; "
              f"ordinaux={ordinals} ; budget={budget} ; CALL_STARTED={started}")

        print("== R. seuil receipt_hash_required_from")
        fresh = tmp / "r-fresh"
        q = json.loads(sub(SRC, BUILD, fresh, "n").stdout)
        print(f"R1 base neuve : seuil={boundary(fresh)} ; séquences des reçus="
              f"{[json.loads(sqlite3.connect(fresh / 'missions.sqlite3').execute('SELECT body FROM command_receipts WHERE command_key=?', (k,)).fetchone()[0])['event_sequence'] for k in q]}")

        def variant(name, src_dir, key, *fns):
            d = tmp / name
            shutil.copytree(src_dir, d)
            for fn in fns:
                edit_db(d, fn)
            return ask(d, qall[key])
        qall = dict(q)
        print(f"R1 hash retiré + statut altéré, reçu au-delà du seuil : "
              f"{variant('r1', fresh, 'n0', receipt_edit('n0', drop_hash=True, alter=True))}")
        drop_boundary = lambda db: db.execute("DELETE FROM sync_metadata WHERE key='receipt_hash_required_from'")  # noqa: E731
        r2 = variant('r2', fresh, 'n0', drop_boundary, receipt_edit('n0', drop_hash=True, alter=True))
        print(f"R2 seuil supprimé, puis hash retiré + altération : {r2}")
        print(f"R3 seuil relevé à max(sequence), puis hash retiré + altération du 1er reçu : "
              f"{variant('r3', fresh, 'n0', lambda db: db.execute('UPDATE sync_metadata SET value=(SELECT CAST(max(sequence) AS TEXT) FROM events) WHERE key=?', ('receipt_hash_required_from',)), receipt_edit('n0', drop_hash=True, alter=True))}")
        raise_boundary = lambda db: db.execute("UPDATE sync_metadata SET value=(SELECT CAST(max(sequence) AS TEXT) FROM events) "  # noqa: E731
                                               "WHERE key='receipt_hash_required_from'")
        print(f"R3b seuil relevé seul, hash intact, 1er reçu : {variant('r3b', fresh, 'n0', raise_boundary)}")
        for label, value in (("'0'", "0"), ("'abc'", "abc"), ("' 5'", " 5"), ("au-delà du journal", "999999"), ("entier SQLite 5", 5)):
            d = tmp / f"rv{label}"
            shutil.copytree(fresh, d)
            edit_db(d, lambda db, v=value: db.execute("UPDATE sync_metadata SET value=? WHERE key='receipt_hash_required_from'", (v,)))
            cmd = dict(protocol="eidolon-cancel-command/1", **dict(qall["n0"], command_key="after"), actor="g052", reason="x")
            out = sub(SRC, SUBMIT, d, json.dumps(cmd)).stdout.strip()[:60]
            print(f"R4 seuil {label}: lecture {ask(d, qall['n0'])} ; nouvelle commande : {out}")

        print("== M. fenêtre de migration : reçus 0fdf18e (hash sans seuil), puis un reçu 7d8efb9")
        mig = tmp / "r-mig"
        qm = json.loads(sub(C012, BUILD, mig, "old").stdout)
        print(f"M après 0fdf18e : seuil={boundary(mig)}")
        cmd = dict(protocol="eidolon-cancel-command/1", **dict(qm["old0"], command_key="new0"), actor="g052", reason="x")
        sub(SRC, SUBMIT, mig, json.dumps(cmd))
        qm["new0"] = dict(qm["old0"], command_key="new0")
        print(f"M après 7d8efb9 : seuil={boundary(mig)} ; lectures : old0 {ask(mig, qm['old0'])}, new0 {ask(mig, qm['new0'])}")
        qall = qm
        print(f"M hash retiré + altération d'un reçu 0fdf18e (avant le seuil) : "
              f"{variant('m1', mig, 'old0', receipt_edit('old0', drop_hash=True, alter=True))}")
        print(f"M même chose sur le reçu 7d8efb9 (au seuil) : "
              f"{variant('m2', mig, 'new0', receipt_edit('new0', drop_hash=True, alter=True))}")

        print("== A. atomicité du seuil")
        for name, ddl in (("panne après insertion du seuil, avant le commit",
                           "CREATE TRIGGER g052 AFTER INSERT ON sync_metadata WHEN NEW.key='receipt_hash_required_from' "
                           "BEGIN SELECT g052_crash(); END"),):
            d = tmp / "a1"
            q1 = json.loads(sub(C012, BUILD, d, "pre").stdout)   # no boundary yet
            edit_db(d, lambda db: db.execute(ddl))
            cmd = dict(protocol="eidolon-cancel-command/1", **dict(q1["pre0"], command_key="crash"), actor="g052", reason="x")
            p = sub(SRC, SUBMIT, d, json.dumps(cmd))
            edit_db(d, lambda db: db.execute("DROP TRIGGER g052"))
            print(f"A {name}: code {p.returncode} ; seuil={boundary(d)} ; consultation : {ask(d, dict(q1['pre0'], command_key='crash'))}")
            p = sub(SRC, SUBMIT, d, json.dumps(cmd))
            print(f"A   renvoi de la même clé : seuil={boundary(d)} ; consultation : {ask(d, dict(q1['pre0'], command_key='crash'))}")
        d = tmp / "a2"
        q2 = json.loads(sub(C012, BUILD, d, "pre").stdout)
        procs = [subprocess.Popen([sys.executable, "-c", SUBMIT, str(d), json.dumps(dict(
            protocol="eidolon-cancel-command/1", **dict(q2["pre0"], command_key=f"par{i}"), actor="g052", reason="x"))],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
        outs = [p.communicate(timeout=120)[0].strip() for p in procs]
        seqs = [json.loads(o)["event_sequence"] if o.startswith("{") else o[:60] for o in outs]
        print(f"A 4 premiers reçus en parallèle sur une base sans seuil : séquences={seqs} ; seuil={boundary(d)} ; "
              f"lectures={[ask(d, dict(q2['pre0'], command_key=f'par{i}')) for i in range(4)]}")


if __name__ == "__main__":
    main()
