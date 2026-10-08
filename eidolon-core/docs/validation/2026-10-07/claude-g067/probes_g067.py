# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g067.py
# Description : Contre-revue des lectures SQLite bornées : ReadOnlyStore, MissionList, ClientSync (C-TASK-G067)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g067.py <frozen eidolon-core/src>

Synthetic missions in temporary folders only. Each case runs on a fresh copy of a reference
state. "empreinte" = names, sizes, modes, mtimes and hashes of every file of the state folder,
taken before and after the read: any created, migrated or modified file is reported.
Volume cases run in a subprocess to measure peak memory (ru_maxrss) without polluting this one."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import resource
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

from eidolon_core.client_sync import ClientSync  # noqa: E402
from eidolon_core.http_api import ReadOnlyStore, ReadServer  # noqa: E402
from eidolon_core.memory import DEMO_REQUEST  # noqa: E402
from eidolon_core.mission_list import MissionList  # noqa: E402
from eidolon_core.runtime import Runtime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


def fingerprint(root):
    out = []
    for p in sorted(Path(root).rglob("*")):
        st = p.lstat()
        out.append((str(p.relative_to(root)), st.st_size, oct(st.st_mode & 0o7777), st.st_mtime_ns,
                    hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.is_file() else "-"))
    return out


def diff(before, after):
    b, a = {x[0]: x for x in before}, {x[0]: x for x in after}
    created = sorted(set(a) - set(b))
    removed = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    parts = ([f"créés {created}"] if created else []) + ([f"retirés {removed}"] if removed else []) + \
            ([f"modifiés {changed}"] if changed else [])
    return "; ".join(parts) or "aucun fichier créé ni modifié"


def reference(root, missions=4):
    state = Path(root) / "state"
    rt = Runtime(Store(state))
    rt.run(rt.create(DEMO_REQUEST)["id"])
    for i in range(missions - 1):
        rt.create(f"compter les mots synthétiques {i}")
    return state


def edit(state, sql, params=()):
    db = sqlite3.connect(state / "missions.sqlite3")
    with db:
        db.execute(sql, params)
    db.close()


def first_mission(state):
    db = sqlite3.connect(state / "missions.sqlite3")
    row = db.execute("SELECT min(id) FROM missions").fetchone()[0]
    db.close()
    return row


def attempt(fn):
    try:
        out = fn()
        items = out.get("items")
        return "OK" + (f" ({len(items)} missions, has_more={out['has_more']})" if items is not None else f" ({out['status']})")
    except Exception as exc:  # noqa: BLE001 -- the exact type and code are the observation
        return f"{type(exc).__name__} {getattr(exc, 'code', None) or str(exc)[:50]}"


def both(state, identity=None):
    def run():
        store = ReadOnlyStore(state)
        return MissionList(store).page(limit=100)

    def snap():
        store = ReadOnlyStore(state)
        return ClientSync(store).snapshot(identity or first_mission(state))
    return attempt(run), attempt(snap)


def altered(tmp):
    print("== A. tables vides ou altérées (API en processus, copie fraîche par cas)")
    base = reference(tmp / "ref")
    empty = Path(tmp) / "empty" / "state"
    Store(empty)
    before = fingerprint(empty)
    print(f"A0 Store sans mission : liste {both(empty, 'm-' + '0' * 32)[0]} ; {diff(before, fingerprint(empty))}")
    big_nest = "[" * 100000 + "]" * 100000
    cases = [
        ("événements d'une mission supprimés", "DELETE FROM events WHERE mission_id=(SELECT max(id) FROM missions)", ()),
        ("corps JSON invalide (1 mission sur 4)", "UPDATE missions SET body='{' WHERE id=(SELECT max(id) FROM missions)", ()),
        ("clé dupliquée dans le corps", "UPDATE missions SET body='{\"id\":\"x\",' || substr(body,2) WHERE id=(SELECT max(id) FROM missions)", ()),
        ("identité du corps différente de la ligne", "UPDATE missions SET body=json_set(body,'$.id','m-' || printf('%032d',7)) WHERE id=(SELECT max(id) FROM missions)", ()),
        ("révision 1.5", "UPDATE missions SET revision=1.5 WHERE id=(SELECT max(id) FROM missions)", ()),
        ("révision '3' (texte, colonne INTEGER)", "UPDATE missions SET revision='3' WHERE id=(SELECT max(id) FROM missions)", ()),
        ("révision 2^53", "UPDATE missions SET revision=9007199254740992 WHERE id=(SELECT max(id) FROM missions)", ()),
        ("cancel_requested=2", "UPDATE missions SET cancel_requested=2 WHERE id=(SELECT max(id) FROM missions)", ()),
        ("statut de 41 caractères", "UPDATE missions SET body=json_set(body,'$.status',printf('%041d',0)) WHERE id=(SELECT max(id) FROM missions)", ()),
        ("imbrication 100000 dans le corps", "UPDATE missions SET body=? WHERE id=(SELECT max(id) FROM missions)", (big_nest,)),
        ("corps en BLOB UTF-16", "UPDATE missions SET body=CAST(? AS BLOB) WHERE id=(SELECT max(id) FROM missions)", None),
        ("détail du dernier événement en BLOB", "UPDATE events SET detail=x'00ff' WHERE sequence=(SELECT max(sequence) FROM events)", ()),
        ("date du dernier événement vide", "UPDATE events SET at='' WHERE sequence=(SELECT max(sequence) FROM events)", ()),
        ("store_id retiré", "DELETE FROM sync_metadata WHERE key='store_id'", ()),
        ("user_version=2", "PRAGMA user_version=2", ()),
        ("table command_receipts supprimée", "DROP TABLE command_receipts", ()),
        ("mode revue (recovery_mode)", "INSERT INTO sync_metadata(key,value) VALUES ('recovery_mode','1')", ()),
    ]
    for name, sql, params in cases:
        state = Path(tmp) / ("a-" + str(abs(hash(name)))) / "state"
        shutil.copytree(base, state)
        if params is None:      # UTF-16 copy of the real body: valid JSON in another encoding
            db = sqlite3.connect(state / "missions.sqlite3")
            ident, body = db.execute("SELECT id, body FROM missions ORDER BY id DESC LIMIT 1").fetchone()
            with db:
                db.execute("UPDATE missions SET body=? WHERE id=?", (body.encode("utf-16"), ident))
            db.close()
        else:
            edit(state, sql, params)
        before = fingerprint(state)
        db = sqlite3.connect(state / "missions.sqlite3")
        target = db.execute("SELECT max(id) FROM missions").fetchone()[0]
        db.close()
        listing, snapshot = both(state, target)
        print(f"A {name} : liste {listing} ; capture {snapshot} ; {diff(before, fingerprint(state))}")
    return base


VOLUME = r"""
import json, resource, sys, time
sys.path.insert(0, sys.argv[1])
from eidolon_core.client_sync import ClientSync
from eidolon_core.http_api import ReadOnlyStore
from eidolon_core.mission_list import MissionList
state, kind, target = sys.argv[2], sys.argv[3], sys.argv[4]
store = ReadOnlyStore(state)
t0 = time.monotonic()
try:
    if kind == "list":
        out = MissionList(store).page(limit=100)
    elif kind == "snapshot":
        out = ClientSync(store).snapshot(target)
    else:
        cur = ClientSync(store).snapshot(target)["cursor"]
        cur.update(sequence=1, event_count=1, anchor_sha256=json.loads(sys.argv[5]))
        out = ClientSync(store).poll(target, cur, limit=100)
    result = "OK %d octets JSON" % len(json.dumps(out))
except Exception as exc:
    result = "%s %s" % (type(exc).__name__, getattr(exc, "code", None) or str(exc)[:40])
print(json.dumps({"result": result, "seconds": round(time.monotonic() - t0, 3),
                  "max_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
"""


def measure(state, kind, target="-", extra="null"):
    p = subprocess.run([sys.executable, "-c", VOLUME, SRC, str(state), kind, target, extra], capture_output=True,
                       text=True, env=ENV, timeout=600)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"result": "ÉCHEC " + p.stderr.strip()[-120:], "seconds": None, "max_rss_mib": None}


def volume(tmp, base):
    print("== B. volumes (sous-processus ; temps mural et pic mémoire du processus)")
    baseline = measure(base, "list")
    print(f"B0 référence 4 missions : liste {baseline}")
    for mib in (1, 16, 64, 256):
        state = Path(tmp) / f"b-body-{mib}" / "state"
        shutil.copytree(base, state)
        db = sqlite3.connect(state / "missions.sqlite3")
        ident = db.execute("SELECT max(id) FROM missions").fetchone()[0]
        with db:
            db.execute("UPDATE missions SET body=json_set(body,'$.padding',?) WHERE id=?", ("x" * (mib * 1024 * 1024), ident))
        db.close()
        size = (state / "missions.sqlite3").stat().st_size
        print(f"B corps d'une mission {mib} Mio (base {size // 1048576} Mio) : liste {measure(state, 'list')} ; "
              f"capture {measure(state, 'snapshot', ident)}")
    state = Path(tmp) / "b-many" / "state"
    shutil.copytree(base, state)
    db = sqlite3.connect(state / "missions.sqlite3")
    ident, body = db.execute("SELECT id, body FROM missions ORDER BY id DESC LIMIT 1").fetchone()
    padded = json.loads(body)
    padded["padding"] = "y" * (2 * 1024 * 1024)
    with db:
        for i in range(100):
            new = "m-" + hashlib.sha256(f"g067-{i}".encode()).hexdigest()[:32]
            padded["id"] = new
            db.execute("INSERT INTO missions(id,revision,cancel_requested,body) VALUES (?,?,?,?)",
                       (new, 0, 0, json.dumps(padded)))
            db.execute("INSERT INTO events(mission_id,at,kind,detail) VALUES (?,?,?,?)",
                       (new, "2026-10-08T00:00:00Z", "CREATED", "{}"))
    db.close()
    print(f"B 100 missions de 2 Mio dans une page : liste {measure(state, 'list')}")
    for n in (100_000, 1_000_000):
        state = Path(tmp) / f"b-events-{n}" / "state"
        shutil.copytree(base, state)
        target = first_mission(state)
        edit(state, f"WITH RECURSIVE k(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM k WHERE i<{n}) "
                    "INSERT INTO events(mission_id,at,kind,detail) SELECT ?, '2026-10-08T00:00:00Z', 'NOTE', '{}' FROM k",
             (target,))
        db = sqlite3.connect(state / "missions.sqlite3")
        first = db.execute("SELECT sequence,mission_id,at,kind,detail FROM events WHERE mission_id=? ORDER BY sequence LIMIT 1",
                           (target,)).fetchone()
        db.close()
        sys.path.insert(0, SRC)
        from eidolon_core.contracts import digest
        anchor = json.dumps(digest(list(first)))
        print(f"B {n} événements sur une mission : liste {measure(state, 'list')} ; capture {measure(state, 'snapshot', target)} ; "
              f"rattrapage depuis la séquence 1 {measure(state, 'poll', target, anchor)}")


def budget(tmp, base):
    print("== C. budget SQL coopératif et verrous (distinguer délai SQL et blocage stockage)")
    state = Path(tmp) / "c-budget" / "state"
    shutil.copytree(base, state)
    edit(state, "WITH RECURSIVE k(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM k WHERE i<300000) "
                "INSERT INTO events(mission_id,at,kind,detail) SELECT (SELECT min(id) FROM missions), 'x', 'NOTE', '{}' FROM k")
    for seconds in (2.0, 0.005, 0.0):
        store = ReadOnlyStore(state)
        store.query_budget_seconds = seconds
        t0 = time.monotonic()
        result = attempt(lambda: MissionList(store).page(limit=100))
        print(f"C budget {seconds} s, 300 000 événements : liste {result} en {time.monotonic() - t0:.3f} s")
    for mode in ("DELETE", "WAL"):
        state = Path(tmp) / f"c-lock-{mode}" / "state"
        shutil.copytree(base, state)
        if mode == "WAL":
            edit(state, "PRAGMA journal_mode=WAL")
        before = fingerprint(state)
        names_before = sorted(p.name for p in state.iterdir())
        result = attempt(lambda: MissionList(ReadOnlyStore(state)).page(limit=100))
        print(f"C {mode} au repos : liste {result} ; fichiers avant {names_before} ; {diff(before, fingerprint(state))}")
        writer = sqlite3.connect(state / "missions.sqlite3", isolation_level=None, timeout=1)
        writer.execute("BEGIN EXCLUSIVE")
        writer.execute("UPDATE missions SET revision=revision WHERE id=(SELECT min(id) FROM missions)")
        t0 = time.monotonic()
        result = attempt(lambda: MissionList(ReadOnlyStore(state)).page(limit=100))
        print(f"C {mode}, écrivain en transaction exclusive non validée : liste {result} en {time.monotonic() - t0:.2f} s")
        writer.execute("ROLLBACK")
        writer.close()


def concurrent(tmp, base):
    print("== D. auteur concurrent entre deux pages")
    state = Path(tmp) / "d" / "state"
    shutil.copytree(base, state)
    store = ReadOnlyStore(state)
    first = MissionList(store).page(limit=2)
    Runtime(Store(state)).create("mission synthétique ajoutée entre deux pages")
    second = MissionList(store).page(limit=2, cursor=first["next_cursor"])
    print(f"D création normale par Runtime entre les pages : {second['status']} {second.get('reason')}")
    state = Path(tmp) / "d2" / "state"
    shutil.copytree(base, state)
    store = ReadOnlyStore(state)
    first = MissionList(store).page(limit=2)
    edit(state, "UPDATE missions SET body=json_set(body,'$.status','FAILED') WHERE id=(SELECT max(id) FROM missions)")
    second = MissionList(store).page(limit=2, cursor=first["next_cursor"])
    print(f"D corps réécrit en SQL sans événement entre les pages : {second['status']} "
          f"(statut lu {[i['mission']['status'] for i in second['items']]}) — hors garantie documentée")
    state = Path(tmp) / "d3" / "state"
    shutil.copytree(base, state)
    stop = threading.Event()
    errors, pages = [], 0

    def writer():
        rt = Runtime(Store(state))
        while not stop.is_set():
            rt.create("écriture concurrente synthétique")
    t = threading.Thread(target=writer)
    t.start()
    t0 = time.monotonic()
    store = ReadOnlyStore(state)
    while time.monotonic() - t0 < 3:
        try:
            page = MissionList(store).page(limit=100)
            pages += 1
            ids = [i["mission"]["id"] for i in page["items"]]
            if ids != sorted(ids) or len(ids) != len(set(ids)):
                errors.append("ordre")
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__ + " " + str(getattr(exc, "code", exc))[:30])
    stop.set()
    t.join()
    counted = {e: errors.count(e) for e in set(errors)}
    print(f"D 3 s de lectures pendant des créations continues : {pages} pages cohérentes ; refus {counted or 'aucun'}")


def http_probe(tmp, base):
    print("== E. réponses HTTP réelles (aucune page partielle)")
    token = "t" * 43
    for name, sql in (("intact", None), ("corps invalide", "UPDATE missions SET body='{' WHERE id=(SELECT max(id) FROM missions)"),
                      ("détail BLOB du dernier événement", "UPDATE events SET detail=x'00ff' WHERE sequence=(SELECT max(sequence) FROM events)"),
                      ("Store verrouillé par un écrivain", "LOCK")):
        state = Path(tmp) / ("e-" + name.replace(" ", "-")) / "state"
        shutil.copytree(base, state)
        writer = None
        if sql == "LOCK":
            server = ReadServer(state, token, port=0)
            writer = sqlite3.connect(state / "missions.sqlite3", isolation_level=None)
            writer.execute("BEGIN EXCLUSIVE")
        elif sql:
            edit(state, sql)
        if sql != "LOCK":
            server = ReadServer(state, token, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            conn.request("POST", "/v1/missions", body=json.dumps({"limit": 100}),
                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                  "Host": f"127.0.0.1:{server.server_address[1]}"})
            t0 = time.monotonic()
            res = conn.getresponse()
            body = res.read()
            elapsed = time.monotonic() - t0
            print(f"E {name} : HTTP {res.status} en {elapsed:.2f} s ; {len(body)} octets ; "
                  f"{json.loads(body).get('error') or str(len(json.loads(body)['items'])) + ' missions'}")
        finally:
            if writer is not None:
                writer.execute("ROLLBACK")
                writer.close()
            server.shutdown()
            server.server_close()


def main():
    print(f"Sources examinées : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g067-") as tmp:
        tmp = Path(tmp)
        base = altered(tmp)
        volume(tmp, base)
        budget(tmp, base)
        concurrent(tmp, base)
        http_probe(tmp, base)
    print(f"pic mémoire du processus principal : {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} Mio")


if __name__ == "__main__":
    main()
