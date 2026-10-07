# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g058.py
# Description : Contre-revue indépendante de l'historique local des requêtes nettoyées C-019 (C-TASK-G058)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g058.py <frozen eidolon-core/src>

Synthetic queries only (example.invalid, documentation addresses), fake provider/reader/DNS,
temporary folders. Crashes are os._exit in subprocesses started here. Alterations are made
on copies with sqlite3: isolated ones must be refused, coherent rewrites are outside the
guarantee and are only reported."""
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

from eidolon_core.contracts import digest, encode  # noqa: E402
from eidolon_core.query_history import QueryHistoryError, read_history  # noqa: E402
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator  # noqa: E402
from eidolon_core.research_guard import GuardError, ResearchGuard  # noqa: E402

RAW = "pont synthetique jean@example.invalid 06 12 34 56 78 198.51.100.7"
PII = [b"jean@example.invalid", b"06 12 34 56 78", b"198.51.100.7"]


class Provider:
    provider_id = "g058-provider"

    def __init__(self):
        self.calls = 0

    def search(self, query, limit):
        self.calls += 1
        return [Hit("https://docs.example.com/a", "titre")]


class Reader:
    reader_id = "g058-reader"

    def read(self, url, policy):
        raise AccessFailure("UNAVAILABLE")


def coordinator(guard, provider=None):
    return ResearchCoordinator([provider or Provider()], Reader(), resolver=lambda h, p: ["93.184.216.34"], guard=guard)


CHILD = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
point = sys.argv[3]
if point == "before_commit":
    real = ResearchGuard._write
    def write(self, db, record, *, insert=False):
        if record["state"] == "INTENT":
            os._exit(9)
        real(self, db, record, insert=insert)
    ResearchGuard._write = write
class P:
    provider_id = "g058-provider"
    def search(self, q, l):
        open(sys.argv[4], "a").write("contact\n")
        os._exit(9)
class R:
    reader_id = "g058-reader"
c = ResearchCoordinator([P()], R(), resolver=lambda h, p: ["93.184.216.34"], guard=ResearchGuard(sys.argv[2], retain_queries=True))
c.run(sys.argv[5])
"""


def attempt(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (GuardError, QueryHistoryError) as exc:
        return f"REFUS {exc}"


def history(directory, **k):
    return attempt(lambda: read_history(ResearchGuard(directory, create=False), **k))


def summary(h):
    if isinstance(h, str):
        return h
    return f"total={h['total']} legacy={h['legacy_runs_without_text']} page={len(h['entries'])} suivant={'oui' if h['next_cursor'] else 'non'}"


def build(directory, n, retain=True, legacy=0):
    if legacy:
        g = ResearchGuard(directory)                        # schema 1
        for i in range(legacy):
            coordinator(g).run(f"ancienne recherche {i}")
    g = ResearchGuard(directory, retain_queries=retain)
    for i in range(n):
        coordinator(g).run(f"{RAW} {i}")
    return g


def copy(src, dst):
    shutil.copytree(src, dst)
    return dst


def sql(directory, *statements):
    db = sqlite3.connect(Path(directory) / "research-runs.sqlite3")
    for s, a in statements:
        db.execute(s, a)
    db.commit()
    db.close()


def version(directory):
    db = sqlite3.connect(Path(directory) / "research-runs.sqlite3")
    v = db.execute("PRAGMA user_version").fetchone()[0]
    db.close()
    return v


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g058-") as tmp:
        tmp = Path(tmp)

        print("== M. migration 1 → 2")
        d = tmp / "m"
        g1 = ResearchGuard(d)
        for i in range(3):
            coordinator(g1).run(f"ancienne recherche {i}")
        before = sqlite3.connect(d / "research-runs.sqlite3").execute("SELECT id, body FROM runs ORDER BY id").fetchall()
        print(f"M schéma initial {version(d)} ; lecture d'historique : {summary(history(d))} ; schéma ensuite {version(d)}")
        cli = subprocess.run([sys.executable, "-m", "eidolon_core.query_history", "--directory", str(d)],
                             env=dict(os.environ, PYTHONPATH=SRC), capture_output=True, text=True)
        print(f"M CLI de lecture sur schéma 1 : code {cli.returncode} {cli.stderr.strip()} ; schéma ensuite {version(d)}")
        print(f"M ouverture create=False + retain_queries : {attempt(lambda: ResearchGuard(d, create=False, retain_queries=True))} ; schéma {version(d)}")
        g2 = ResearchGuard(d, retain_queries=True)
        after = sqlite3.connect(d / "research-runs.sqlite3").execute("SELECT id, body FROM runs ORDER BY id").fetchall()
        print(f"M migration explicite : schéma {version(d)} ; anciennes fiches identiques octet pour octet : {before == after}")
        coordinator(g2).run(RAW)
        print(f"M historique après une recherche : {summary(history(d))}")
        print(f"M objet ouvert sans drapeau après migration : retain_queries={ResearchGuard(d).retain_queries}")
        stale = g1
        print(f"M ancien objet resté en schéma 1, nouvelle recherche : {attempt(lambda: coordinator(stale).run('apres migration'))}")

        print("== C. pannes avant commit et pendant l'appel")
        for point in ("before_commit", "during_call"):
            d = tmp / f"c-{point}"
            build(d, 1)
            log = tmp / f"contacts-{point}"
            p = subprocess.run([sys.executable, "-c", CHILD, SRC, str(d), point, str(log), RAW + " crash"],
                               capture_output=True, text=True)
            h = history(d)
            last = h["entries"][-1] if isinstance(h, dict) and h["entries"] else {}
            print(f"C {point} : code {p.returncode} ; contacts={len(log.read_text().splitlines()) if log.exists() else 0} ; "
                  f"{summary(h)} ; dernière entrée : texte={'crash' in (last.get('text') or '')} état={last.get('state')} émission={last.get('emission')}")
            nxt = attempt(lambda: coordinator(ResearchGuard(d, retain_queries=True)).run('suite'))
            print(f"C   nouvelle recherche : {nxt if isinstance(nxt, str) else nxt['status']}")

        print("== D. doublons, orphelins, altérations (copies)")
        base = tmp / "d"
        build(base, 4)
        rid = sqlite3.connect(base / "research-runs.sqlite3").execute("SELECT run_id FROM cleaned_queries ORDER BY run_id").fetchone()[0]

        def payload(db_dir):
            return json.loads(sqlite3.connect(Path(db_dir) / "research-runs.sqlite3").execute(
                "SELECT body FROM cleaned_queries WHERE run_id=?", (rid,)).fetchone()[0])
        cases = [
            ("ligne orpheline ajoutée", [("INSERT INTO cleaned_queries VALUES (?,?)", ("r-" + "0" * 32, encode(payload(base))))]),
            ("ligne supprimée seule", [("DELETE FROM cleaned_queries WHERE run_id=?", (rid,))]),
            ("texte modifié seul", [("UPDATE cleaned_queries SET body=json_set(body,'$.text','autre texte') WHERE run_id=?", (rid,))]),
            ("ligne de 50 000 octets", [("UPDATE cleaned_queries SET body=json_set(body,'$.text',?) WHERE run_id=?", ("x" * 50000, rid))]),
            ("clé dupliquée dans le JSON", [("UPDATE cleaned_queries SET body=replace(body,'{\"cleanup\"','{\"text\":\"x\",\"cleanup\"') WHERE run_id=?", (rid,))]),
            ("caractère invisible U+200B ajouté au texte", [("UPDATE cleaned_queries SET body=replace(body,'pont','po​nt') WHERE run_id=?", (rid,))]),
        ]
        for i, (name, statements) in enumerate(cases):
            d = copy(base, tmp / f"d{i}")
            sql(d, *statements)
            prov = Provider()
            run = attempt(lambda: coordinator(ResearchGuard(d, retain_queries=True), prov).run("suite"))
            print(f"D {name} : lecture {summary(history(d))} ; recherche {run if isinstance(run, str) else run['status']} ; contacts={prov.calls}")

        # Coherent rewrite: new text + recomputed hashes in the row, the run and its audit events.
        d = copy(base, tmp / "d-coherent")
        p = payload(d)
        p["text"] = "texte reecrit"
        p["cleanup"]["cleaned_sha256"] = hashlib.sha256(b"texte reecrit").hexdigest()
        db = sqlite3.connect(d / "research-runs.sqlite3")
        for table, key in (("runs", "id"), ("run_events", "run_id")):
            for row_key, body in db.execute(f"SELECT rowid, body FROM {table} WHERE {key}=?", (rid,)).fetchall():
                v = json.loads(body)
                v["descriptor"].update(query_sha256=p["cleanup"]["cleaned_sha256"], query_history_sha256=digest(p))
                db.execute(f"UPDATE {table} SET body=? WHERE rowid=?", (encode(v), row_key))
        db.execute("UPDATE cleaned_queries SET body=? WHERE run_id=?", (encode(p), rid))
        db.commit()
        db.close()
        h = history(d)
        print(f"D réécriture cohérente (texte, empreintes, fiche, audit) : {summary(h)} ; texte lu : "
              f"{[e['text'] for e in h['entries'] if e['run_id'] == rid] if isinstance(h, dict) else '—'}  (hors garantie)")
        # Coherent downgrade to a legacy run: row deleted and hash removed from descriptor everywhere.
        d = copy(base, tmp / "d-legacy")
        db = sqlite3.connect(d / "research-runs.sqlite3")
        for table, key in (("runs", "id"), ("run_events", "run_id")):
            for row_key, body in db.execute(f"SELECT rowid, body FROM {table} WHERE {key}=?", (rid,)).fetchall():
                v = json.loads(body)
                v["descriptor"].pop("query_history_sha256")
                db.execute(f"UPDATE {table} SET body=? WHERE rowid=?", (encode(v), row_key))
        db.execute("DELETE FROM cleaned_queries WHERE run_id=?", (rid,))
        db.commit()
        db.close()
        print(f"D texte effacé + lien retiré partout (devient « ancienne ») : {summary(history(d))}  (hors garantie)")

        print("== P. pagination et reset")
        d = tmp / "p"
        g = build(d, 7)
        first = read_history(ResearchGuard(d, create=False), limit=3)
        second = read_history(ResearchGuard(d, create=False), limit=3, cursor=first["next_cursor"])
        third = read_history(ResearchGuard(d, create=False), limit=3, cursor=second["next_cursor"])
        ids = [e["run_id"] for page in (first, second, third) for e in page["entries"]]
        print(f"P 7 entrées par pages de 3 : {[len(x['entries']) for x in (first, second, third)]} ; uniques={len(set(ids))} ; "
              f"ordre chronologique={ids == [e['run_id'] for e in read_history(ResearchGuard(d, create=False), limit=50)['entries']]}")
        cursor = first["next_cursor"]
        gid, rev, _ = cursor.split(":")
        for name, c in (("offset 7 (= total)", f"{gid}:{rev}:7"), ("offset 8", f"{gid}:{rev}:8"), ("offset 003", f"{gid}:{rev}:003"),
                        ("autre journal", f"g-{'0' * 32}:{rev}:3"), ("révision fausse", f"{gid}:{'0' * 64}:3"),
                        ("offset négatif", f"{gid}:{rev}:-1"), ("espace final", cursor + " "), ("151 caractères", "g" * 151)):
            print(f"P curseur {name} : {summary(history(d, limit=3, cursor=c))}")
        coordinator(g).run("nouvelle recherche entre deux pages")
        print(f"P nouvelle recherche puis page 2 : {summary(history(d, limit=3, cursor=cursor))}")
        for lim in (0, 51, True, 3.0):
            print(f"P limite {lim!r} : {summary(history(d, limit=lim))}")

        print("== B. SQLite occupé")
        d = tmp / "b"
        build(d, 2)
        hold = sqlite3.connect(d / "research-runs.sqlite3", isolation_level=None, check_same_thread=False)
        hold.execute("BEGIN EXCLUSIVE")
        threading.Timer(4.0, lambda: (hold.execute("ROLLBACK"), hold.close())).start()
        t0 = time.perf_counter()
        print(f"B lecture pendant un verrou d'écriture de 4 s : {summary(history(d))} en {time.perf_counter() - t0:.1f} s")
        time.sleep(4.5)
        hold2 = sqlite3.connect(d / "research-runs.sqlite3", isolation_level=None, check_same_thread=False)
        hold2.execute("BEGIN EXCLUSIVE")
        threading.Timer(4.0, lambda: (hold2.execute("ROLLBACK"), hold2.close())).start()
        prov = Provider()
        t0 = time.perf_counter()
        run = attempt(lambda: coordinator(ResearchGuard(d, retain_queries=True), prov).run("pendant verrou"))
        print(f"B recherche pendant le verrou : {run if isinstance(run, str) else run['status']} en "
              f"{time.perf_counter() - t0:.1f} s ; contacts={prov.calls}")
        time.sleep(4.5)
        print(f"B ensuite : {summary(history(d))}")

        print("== L. bornes, modes, données")
        d = tmp / "l"
        g = build(d, 2)
        long_query = "mot " * 249 + "fin"
        r = attempt(lambda: coordinator(g).run(long_query))
        print(f"L requête de {len(long_query)} caractères : {r if isinstance(r, str) else r['status']} ; "
              f"texte gardé de {len(read_history(ResearchGuard(d, create=False), limit=50)['entries'][-1]['text'])} caractères")
        modes = {p.name: oct(p.stat().st_mode & 0o777) for p in [d, *d.iterdir()]}
        print(f"L modes : {modes}")
        raw_bytes = (d / "research-runs.sqlite3").read_bytes()
        print(f"L données personnelles brutes dans la base : {[x.decode() for x in PII if x in raw_bytes]}")
        out = encode(read_history(ResearchGuard(d, create=False), limit=50))
        for i in range(2):
            raw = f"{RAW} {i}"
            leaks = [n for n, h in (("sha256 brut", hashlib.sha256(raw.encode()).hexdigest()), ("digest brut", digest(raw))) if h in out]
            print(f"L empreintes de la requête brute {i} dans la lecture : {leaks}")
        os.chmod(d / "research-runs.sqlite3", 0o644)
        print(f"L base en 0644 : {summary(history(d))}")
        d = tmp / "cap"
        build(d, 0, legacy=200)
        g = ResearchGuard(d, retain_queries=True)
        for i in range(56):
            coordinator(g).run(f"remplissage {i}")
        print(f"L 200 anciennes + 56 nouvelles : {summary(history(d, limit=50))} ; 257e : "
              f"{attempt(lambda: coordinator(g).run('de trop'))}")


if __name__ == "__main__":
    main()
