# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_g068.py
# Description : Banc de compatibilité producteur de rotation (prototype G063) / lecteur Core C-028 (C-TASK-G068)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 bench_g068.py <frozen eidolon-core/src>      (exit 1 if any check fails)

Producer: the isolated prototype docs/proposals/2026-10-07-research-retention/rotation.py.
Reader: the UNCHANGED Core module eidolon_core.research_archive (imported, never copied).
Journals: built by the UNCHANGED ResearchGuard and ResearchCoordinator with fixed fixtures.
Temporary folders only; no real journal is touched, nothing is activated in Core."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

SRC = str(Path(sys.argv[1]).resolve())
RETENTION = str(Path(__file__).resolve().parents[1] / "2026-10-07-research-retention")
sys.argv = [sys.argv[0], SRC]
sys.path[:0] = [SRC, RETENTION]
sys.dont_write_bytecode = True

import probes_g057 as g057  # noqa: E402
import rotation  # noqa: E402
from eidolon_core import research_archive as ra  # noqa: E402
from eidolon_core.research_guard import MAX_INTEGER, ResearchGuard  # noqa: E402

OP_ACTIVE = ["m-" + c * 32 for c in "bc"]      # missions NOT declared terminal: their runs must stay
OP_DONE = "m-" + "d" * 32                       # declared terminal by the caller
FAILED = []


def check(label, ok, detail=""):
    print(f"{'✓' if ok else '✗'} {label}{' — ' + detail if detail else ''}")
    if not ok:
        FAILED.append(label)


def journal(root, plain=120, mission_runs=True, wal=False):
    guard_dir = Path(root) / "guard"
    guard = ResearchGuard(guard_dir, retain_queries=True)
    if wal:
        db = sqlite3.connect(guard_dir / "research-runs.sqlite3")
        mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        db.close()
        assert mode == "wal"
    c = g057.coordinator(guard)
    if mission_runs:            # the OLDEST runs: they would be archived first if not protected
        for op in OP_ACTIVE + [OP_DONE]:
            c.run(f"recherche liee a une mission synthetique {op[2]}", operation_id=op)
    for i in range(plain):
        c.run(f"documentation synthetique numero {i}")
    archive = Path(root) / "archive"
    archive.mkdir(mode=0o700)
    return guard_dir, archive


def rows(guard_dir):
    db = sqlite3.connect(Path(guard_dir) / "research-runs.sqlite3")
    out = {}
    for identity, body in db.execute("SELECT id, body FROM runs"):
        events = [list(e) for e in db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? ORDER BY sequence",
                                              (identity,))]
        q = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone()
        out[identity] = {"id": identity, "body": body, "events": events, "cleaned_query": q[0] if q else None}
    db.close()
    return out


def exported(archive_dir):
    """Rows of every export, through the Core reader's validation (its private 'meta')."""
    out = {}
    for p in sorted(Path(archive_dir).glob("research-archive-*.json")):
        meta = ra.validate_export(p.read_bytes(), p.name)["meta"]
        for run in meta["runs"]:
            out[run["id"]] = run
    return out


def operation_of(row):
    return json.loads(row["body"])["descriptor"].get("operation_id")


def conserved(original, guard_dir, archive_dir):
    active, archived = rows(guard_dir), exported(archive_dir)
    return all((active.get(k) or archived.get(k)) == v for k, v in original.items()) and not (set(active) & set(archived))


def core_read(archive_dir):
    try:
        cat = ra.read_catalog(archive_dir)
        return f"OK {cat['archive_count']} exports / {cat['run_count']} recherches", cat
    except ra.ArchiveError as exc:
        return f"REFUS {exc}", None


def nominal(tmp):
    print("== N. 100 actives, missions non terminales protégées, lecture par le lecteur Core")
    g, a = journal(tmp / "n")
    original = rows(g)
    t0 = time.monotonic()
    report = rotation.auto_rotate(g, a, target=100, terminal_operations=(OP_DONE,), guard_src=SRC, clock_ms=1_760_000_000_000)
    elapsed = time.monotonic() - t0
    active = rows(g)
    status, cat = core_read(a)
    check("auto_rotate garde 100 recherches actives", report["active"] == 100 and len(active) == 100,
          f"{len(original)} → {len(active)} actives, {report['archived']} archivées en {elapsed:.2f} s")
    check("runs des missions non terminales toujours actifs",
          {operation_of(r) for r in active.values()} >= set(OP_ACTIVE))
    check("run de la mission terminale archivé et déclaré libéré",
          OP_DONE not in {operation_of(r) for r in active.values()}
          and json.loads(next(a.glob("*.json")).read_bytes()).get("released_operations") == [OP_DONE])
    check("le lecteur Core accepte la chaîne produite", cat is not None and cat["run_count"] == report["archived"], status)
    check("conservation octet pour octet (actives ∪ exports = origine)", conserved(original, g, a))
    again = rotation.auto_rotate(g, a, target=100, terminal_operations=(OP_DONE,), guard_src=SRC, clock_ms=1_760_000_000_001)
    check("second appel idempotent", again["archived"] == 0 and core_read(a)[0] == status)
    ra.write_index(a)
    import re
    links = re.findall(r"\]\((research-archive-[0-9]{6}\.json)\)", (a / "liste.md").read_text())
    check("liste.md Core générée sur la chaîne du producteur", links == ["research-archive-000001.json"], str(links))

    print("== D. dépassement explicite quand seules des missions non terminales restent")
    g, a = journal(tmp / "d", plain=0, mission_runs=False)
    guard = ResearchGuard(g, retain_queries=True)
    c = g057.coordinator(guard)
    for i in range(105):
        c.run(f"recherche de mission longue {i}", operation_id=OP_ACTIVE[0])
    before = rows(g)
    report = rotation.auto_rotate(g, a, target=100, terminal_operations=(), guard_src=SRC, clock_ms=1)
    check("aucun retrait, dépassement signalé", report["archived"] == 0 and report["above_target"] == 5 and rows(g) == before,
          f"active={report['active']} above_target={report['above_target']}")
    check("aucun export créé", list(a.iterdir()) == [])


def wal(tmp):
    print("== W. journal en WAL")
    g, a = journal(tmp / "w", wal=True)
    original = rows(g)
    report = rotation.auto_rotate(g, a, target=100, terminal_operations=(OP_DONE,), guard_src=SRC, clock_ms=1)
    status, cat = core_read(a)
    check("rotation sur un journal WAL lue par Core", cat is not None and report["active"] == 100, status)
    check("conservation en WAL", conserved(original, g, a))
    db = sqlite3.connect(g / "research-runs.sqlite3")
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    version = db.execute("PRAGMA user_version").fetchone()[0]
    db.close()
    check("le journal reste en WAL, schéma 3", (mode, version) == ("wal", 3), f"{mode}, user_version {version}")
    refused = ""
    try:
        ResearchGuard(g, create=False, retain_queries=True)
    except Exception as exc:  # noqa: BLE001
        refused = str(exc)
    check("la garde Core actuelle refuse le schéma 3 (pas d'usage silencieux)", refused == "UNSUPPORTED_RESEARCH_GUARD", refused)


AUTO_CRASH = ("import sys; sys.path[:0]=[sys.argv[1], sys.argv[2]]; import rotation; "
              "rotation.auto_rotate(sys.argv[3], sys.argv[4], target=100, terminal_operations=(sys.argv[5],), "
              "guard_src=sys.argv[1], clock_ms=1)")


def crashes(tmp):
    print("== C. coupure à chaque frontière puis reprises répétées")
    for point in ("after_partial_write", "after_publish", "inside_transaction", "after_commit"):
        g, a = journal(tmp / f"c-{point}")
        original = rows(g)
        p = subprocess.run([sys.executable, "-c", AUTO_CRASH, SRC, RETENTION, str(g), str(a), OP_DONE],
                           env=dict(os.environ, G057_CRASH_AT=point), capture_output=True, text=True)
        right_after = core_read(a)[0]
        reports = [rotation.auto_rotate(g, a, target=100, terminal_operations=(OP_DONE,), guard_src=SRC, clock_ms=2 + i)
                   for i in range(3)]
        status, cat = core_read(a)
        check(f"{point} : code {p.returncode}, lecteur juste après « {right_after} », trois reprises",
              p.returncode == 9 and cat is not None and len(rows(g)) == 100 and reports[2]["archived"] == 0
              and reports[2]["resumed"] is None and conserved(original, g, a),
              f"puis {status} ; reprises {[(r['partials_removed'], r['resumed'] is not None, r['archived']) for r in reports]}")


def limits(tmp):
    print("== L. limites producteur / lecteur")
    table = [("octets par export", rotation.MAX_EXPORT_BYTES, ra.MAX_ARCHIVE_BYTES),
             ("nombre d'exports", rotation.MAX_EXPORTS, ra.MAX_ARCHIVES),
             ("recherches par export", rotation.MAX_RUNS_PER_EXPORT, 256),
             ("octets cumulés", "aucune", ra.MAX_TOTAL_BYTES),
             ("entier maximal (horodatage, séquences)", "non contrôlé (clock_ms)", MAX_INTEGER)]
    for name, producer, reader in table:
        print(f"   {name} : producteur {producer} ; lecteur {reader}{'  ← ÉCART' if producer != reader else ''}")
    g, a = journal(tmp / "l-count", plain=8, mission_runs=False)
    for i in range(4):
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=10 + i)
    with patch.object(ra, "MAX_ARCHIVES", 3):
        producer_ok = rotation.verify(g, a, guard_src=SRC)["archives"] == 4
        status = core_read(a)[0]
    check("écart du nombre d'exports reproduit (lecteur abaissé à 3, producteur continue)",
          producer_ok and status == "REFUS ARCHIVE_COUNT_LIMIT", status)
    g, a = journal(tmp / "l-clock", plain=3, mission_runs=False)
    try:
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=MAX_INTEGER + 1)
        produced = "accepté"
    except rotation.RotationError as exc:
        produced = f"refusé {exc}"
    status = core_read(a)[0]
    check("horodatage 2^53 : écart producteur/lecteur documenté", True, f"producteur {produced} ; lecteur {status}")
    sizes = sorted(p.stat().st_size for p in (tmp / "n" / "archive").glob("*.json"))
    print(f"   taille mesurée des exports N : {sizes} octets ; une recherche synthétique ≈ {sizes[-1] // 23 if sizes else 0} octets")
    g, a = journal(tmp / "l-growth", plain=60, mission_runs=False)
    timings = []
    for i in range(60):
        t0 = time.monotonic()
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=100 + i)
        timings.append(time.monotonic() - t0)
    print(f"   coût d'une rotation selon la longueur de chaîne : export 1 {timings[0]:.3f} s ; 30 {timings[29]:.3f} s ; "
          f"60 {timings[59]:.3f} s (relecture complète de la chaîne à chaque appel)")


def reversible(tmp):
    print("== R. migration schéma 2 → 3 réversible avant tout retrait définitif")
    g, a = journal(tmp / "r")
    original = rows(g)
    rotation.auto_rotate(g, a, target=100, terminal_operations=(OP_DONE,), guard_src=SRC, clock_ms=1)
    copy = tmp / "r-copy" / "guard"
    shutil.copytree(g, copy)
    db = sqlite3.connect(copy / "research-runs.sqlite3", isolation_level=None)
    db.execute("BEGIN IMMEDIATE")
    for run in exported(a).values():            # rows re-inserted from exports validated by Core
        db.execute("INSERT INTO runs(id, body) VALUES (?, ?)", (run["id"], run["body"]))
        for seq, kind, body in run["events"]:
            db.execute("INSERT INTO run_events(sequence, run_id, kind, body) VALUES (?,?,?,?)", (seq, run["id"], kind, body))
        if run["cleaned_query"] is not None:
            db.execute("INSERT INTO cleaned_queries(run_id, body) VALUES (?, ?)", (run["id"], run["cleaned_query"]))
    db.execute("DROP TABLE archives")
    db.execute("PRAGMA user_version=2")
    db.execute("COMMIT")
    db.close()
    check("journal restauré depuis les exports = journal d'origine (lignes octet pour octet)", rows(copy) == original)
    guard = ResearchGuard(copy, create=False, retain_queries=True)
    check("la garde Core actuelle rouvre le journal restauré en schéma 2",
          len(guard.inspect()["runs"]) == len(original))


def main():
    print(f"Sources Core : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g068-") as tmp:
        tmp = Path(tmp)
        nominal(tmp)
        wal(tmp)
        crashes(tmp)
        limits(tmp)
        reversible(tmp)
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
