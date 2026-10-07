# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g057.py
# Description : Sondes du prototype de rotation sur journaux synthétiques de schéma 2 (C-TASK-G057)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g057.py <frozen eidolon-core/src>

Each scenario builds a fresh schema-2 journal with the UNCHANGED ResearchGuard
(retain_queries=True): 6 completed runs, 1 linked to a mission (operation_id), 1 resolved
after a crash, synthetic queries only. Crashes are os._exit in subprocesses started here."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SRC = str(Path(sys.argv[1]).resolve())
HERE = str(Path(__file__).resolve().parent)
sys.path[:0] = [SRC, HERE]

from eidolon_core.research import Hit, ResearchCoordinator  # noqa: E402
from eidolon_core.research_guard import GuardError, ResearchGuard  # noqa: E402
from eidolon_core.query_history import read_history  # noqa: E402
import rotation  # noqa: E402

sys.dont_write_bytecode = True

OPERATION = "m-" + "a" * 32


class Provider:
    provider_id = "g057-provider"

    def search(self, query, limit):
        return [Hit("https://docs.example.com/a", "titre")]


class Reader:
    reader_id = "g057-reader"

    def read(self, url, policy):
        from eidolon_core.research import AccessFailure
        raise AccessFailure("UNAVAILABLE")


def coordinator(guard):
    return ResearchCoordinator([Provider()], Reader(), resolver=lambda h, p: ["93.184.216.34"], guard=guard)


CRASH_RUN = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
class P:
    provider_id = "g057-provider"
    def search(self, q, l): os._exit(9)
class R:
    reader_id = "g057-reader"
c = ResearchCoordinator([P()], R(), resolver=lambda h, p: ["93.184.216.34"], guard=ResearchGuard(sys.argv[2], retain_queries=True))
c.run("requete interrompue synthetique")
"""


def build(root):
    guard_dir = Path(root) / "guard"
    guard = ResearchGuard(guard_dir, retain_queries=True)
    c = coordinator(guard)
    for i in range(5):
        c.run(f"documentation pont synthetique {i} jean@example.invalid")
    c.run("recherche liee a une mission synthetique", operation_id=OPERATION)
    subprocess.run([sys.executable, "-c", CRASH_RUN, SRC, str(guard_dir)], capture_output=True)
    guard = ResearchGuard(guard_dir, retain_queries=True)
    intent = next(r for r in guard.inspect()["runs"] if r["state"] == "INTENT")
    guard.resolve(intent["id"], expected_revision=1, actor="g057", reason="revue synthetique G057")
    archive = Path(root) / "archive"
    archive.mkdir(mode=0o700)
    return guard_dir, archive


def state(guard_dir):
    db = sqlite3.connect(Path(guard_dir) / "research-runs.sqlite3")
    out = {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("runs", "run_events", "cleaned_queries")}
    out["version"] = db.execute("PRAGMA user_version").fetchone()[0]
    out["archives"] = (db.execute("SELECT count(*) FROM archives").fetchone()[0]
                       if db.execute("SELECT 1 FROM sqlite_master WHERE name='archives'").fetchone() else 0)
    db.close()
    return out


def attempt(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (rotation.RotationError, GuardError) as exc:
        return f"REFUS {exc}"


def rotate_sub(guard_dir, archive, count, crash):
    code = ("import sys; sys.path[:0]=[sys.argv[1], sys.argv[2]]; import rotation, json; "
            "print(json.dumps(rotation.rotate(sys.argv[3], sys.argv[4], count=int(sys.argv[5]), guard_src=sys.argv[1], clock_ms=1)))")
    env = dict(os.environ, G057_CRASH_AT=crash)
    p = subprocess.run([sys.executable, "-c", code, SRC, HERE, str(guard_dir), str(archive), str(count)],
                       env=env, capture_output=True, text=True)
    tail = p.stderr.strip().splitlines()
    return p.returncode, p.stdout.strip() or (tail[-1] if tail else "")


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g057-") as tmp:
        tmp = Path(tmp)

        print("== R. rotation nominale (3 plus anciennes)")
        g, a = build(tmp / "r")
        before = state(g)
        texts_before = {e["run_id"]: e["text"] for e in read_history(ResearchGuard(g, create=False), limit=50)["entries"]}
        print(f"R avant : {before}")
        print(f"R rotation : {attempt(rotation.rotate, g, a, count=3, guard_src=SRC, clock_ms=1)}")
        print(f"R après : {state(g)} ; vérification : {attempt(rotation.verify, g, a, guard_src=SRC)}")
        export = json.loads(next(a.glob('*.json')).read_bytes())
        exported_texts = {r['id']: json.loads(r['cleaned_query'])['text'] for r in export['runs'] if r['cleaned_query']}
        print(f"R export : {len(export['runs'])} recherches, textes nettoyés identiques : "
              f"{all(texts_before[k] == v for k, v in exported_texts.items())} ; mode {oct(next(a.glob('*.json')).stat().st_mode & 0o777)}")
        print(f"R garde actuelle sur le journal de schéma 3 : {attempt(lambda: ResearchGuard(g, create=False))}")
        print(f"R deuxième rotation (tout le reste) : {attempt(rotation.rotate, g, a, count=256, guard_src=SRC, clock_ms=2)}")
        print(f"R après : {state(g)} ; vérification : {attempt(rotation.verify, g, a, guard_src=SRC)}")
        print(f"R la recherche liée à la mission reste : "
              f"{OPERATION in (tmp / 'r' / 'guard' / 'research-runs.sqlite3').read_bytes().decode('utf-8', 'replace')}")
        print(f"R mission libérée explicitement : "
              f"{attempt(rotation.rotate, g, a, count=256, operations=(OPERATION,), guard_src=SRC, clock_ms=3)} ; {state(g)}")

        print("== P. refus préalables")
        g, a = build(tmp / "p")
        subprocess.run([sys.executable, "-c", CRASH_RUN, SRC, str(g)], capture_output=True)
        print(f"P intention en cours : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=1)}")
        g, a = build(tmp / "p2")
        os.unlink(g / "research-runs.lock")
        print(f"P verrou absent : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=1)} ; "
              f"verrou recréé : {(g / 'research-runs.lock').exists()}")
        g, a = build(tmp / "p3")
        os.chmod(a, 0o755)
        print(f"P dossier d'archive non privé : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=1)}")
        g, a = build(tmp / "p4")
        db = sqlite3.connect(g / "research-runs.sqlite3")
        db.execute("DELETE FROM run_events WHERE sequence=(SELECT max(sequence) FROM run_events)")
        db.commit()
        db.close()
        print(f"P journal incohérent : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=1)} ; {state(g)}")
        g, a = build(tmp / "p5")
        import fcntl
        fd = os.open(g / "research-runs.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        print(f"P recherche en cours (verrou tenu) : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=1)}")
        os.close(fd)

        print("== K. coupures à chaque frontière")
        for point in ("after_partial_write", "after_publish", "inside_transaction", "after_commit"):
            g, a = build(tmp / f"k-{point}")
            code, out = rotate_sub(g, a, 3, point)
            files = sorted(p.name.split(".")[-1] if p.name.endswith(".partial") else "export" for p in a.iterdir())
            print(f"K {point} : code {code} ; journal {state(g)} ; fichiers {files} ; vérification : {attempt(rotation.verify, g, a, guard_src=SRC)}")
            if point == "after_partial_write":
                print(f"K   nouvelle rotation : {attempt(rotation.rotate, g, a, count=3, guard_src=SRC, clock_ms=2)}")
            if point in ("after_publish", "inside_transaction"):
                print(f"K   reprise : {attempt(rotation.resume_uncommitted, g, a, guard_src=SRC)} ; {state(g)} ; "
                      f"vérification : {attempt(rotation.verify, g, a, guard_src=SRC)}")

        print("== D. copie, restauration, altérations")
        g, a = build(tmp / "d")
        backup = tmp / "d-backup"
        shutil.copytree(g, backup)
        rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=1)
        rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=2)
        print(f"D deux rotations : {state(g)} ; {attempt(rotation.verify, g, a, guard_src=SRC)}")
        shutil.rmtree(g)
        shutil.copytree(backup, g)
        print(f"D journal restauré d'avant les rotations : {attempt(rotation.verify, g, a, guard_src=SRC)} ; "
              f"nouvelle rotation : {attempt(rotation.rotate, g, a, count=1, guard_src=SRC, clock_ms=3)}")
        g, a = build(tmp / "d2")
        rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=1)
        f = next(a.glob("*.json"))
        data = f.read_bytes()
        f.write_bytes(data.replace(b"synthetique", b"synthetiqUE", 1))
        print(f"D export modifié : {attempt(rotation.verify, g, a, guard_src=SRC)}")
        f.unlink()
        print(f"D export supprimé : {attempt(rotation.verify, g, a, guard_src=SRC)}")
        g, a = build(tmp / "d3")
        rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=1)
        db = sqlite3.connect(g / "research-runs.sqlite3")
        db.execute("DELETE FROM archives")
        db.commit()
        db.close()
        print(f"D entrée de chaîne supprimée du journal : {attempt(rotation.verify, g, a, guard_src=SRC)} ; "
              f"reprise : {attempt(rotation.resume_uncommitted, g, a, guard_src=SRC)}")


if __name__ == "__main__":
    main()
