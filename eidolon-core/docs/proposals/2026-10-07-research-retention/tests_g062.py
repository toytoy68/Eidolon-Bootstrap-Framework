# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests_g062.py
# Description : Assertions du prototype de rotation v2 : contre-exemples Codex, WAL, bornes, automatisme (C-TASK-G062)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G062_SRC=<frozen eidolon-core/src> python3 -m unittest tests_g062 -v   (from this folder)

Synthetic journals built by the UNCHANGED ResearchGuard (schema 2, cleaned_queries,
operation_id). Crashes are os._exit in subprocesses (probes_g057.rotate_sub)."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SRC = str(Path(os.environ["G062_SRC"]).resolve())
HERE = str(Path(__file__).resolve().parent)
sys.argv = [sys.argv[0], SRC]
sys.path[:0] = [SRC, HERE]
sys.dont_write_bytecode = True

import probes_g057 as g057  # noqa: E402
import rotation  # noqa: E402
from eidolon_core.research_guard import ResearchGuard  # noqa: E402


def fds():
    return len(os.listdir("/proc/self/fd"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g062-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def journal(self, name="j"):
        return g057.build(self.tmp / name)          # 7 runs: 5 plain, 1 mission-linked, 1 resolved

    def refused(self, code, fn, *a, **k):
        before = fds()
        with self.assertRaises(rotation.RotationError) as ctx:
            fn(*a, **k)
        self.assertEqual(str(ctx.exception), code)
        self.assertEqual(fds(), before, "descriptor leaked on refusal")

    def crash_after_publish(self, g, a, count=1):
        code, _ = g057.rotate_sub(g, a, count, "after_publish")
        self.assertEqual(code, 9)
        return sorted(a.glob("*.json"))[-1]

    def rewrite(self, path, change):
        value = json.loads(path.read_bytes())
        change(value)
        path.write_bytes(rotation._canon(value))


class CodexCounterExamples(Base):
    """codex-g057-review: each case must now be refused WITHOUT removing anything."""

    def assert_nothing_removed(self, g, before):
        self.assertEqual(g057.state(g), before)

    def test_null_cleaned_query_in_export(self):
        g, a = self.journal()
        export = self.crash_after_publish(g, a)
        self.rewrite(export, lambda v: v["runs"][0].update(cleaned_query=None))
        before = g057.state(g)
        self.refused("EXPORT_DOES_NOT_MATCH_JOURNAL", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assert_nothing_removed(g, before)

    def test_modified_cleaned_query_in_export(self):
        g, a = self.journal()
        export = self.crash_after_publish(g, a)
        self.rewrite(export, lambda v: v["runs"][0].update(cleaned_query=v["runs"][0]["cleaned_query"].replace("pont", "pnot")))
        before = g057.state(g)
        self.refused("EXPORT_DOES_NOT_MATCH_JOURNAL", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assert_nothing_removed(g, before)

    def test_foreign_guard_id_in_export(self):
        g, a = self.journal()
        export = self.crash_after_publish(g, a)
        self.rewrite(export, lambda v: v.update(guard_id="g-" + "f" * 32))
        before = g057.state(g)
        self.refused("EXPORT_DOES_NOT_MATCH_JOURNAL", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assert_nothing_removed(g, before)

    def test_prior_archive_missing_during_resume(self):
        g, a = self.journal()
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=1)
        self.crash_after_publish(g, a)
        sorted(a.glob("*.json"))[0].unlink()
        before = g057.state(g)
        self.refused("ARCHIVE_MISSING", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assert_nothing_removed(g, before)

    def test_prior_archive_altered_during_resume(self):
        g, a = self.journal()
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=1)
        self.crash_after_publish(g, a)
        first = sorted(a.glob("*.json"))[0]
        first.write_bytes(first.read_bytes().replace(b"synthetique", b"synthetiqUE", 1))
        before = g057.state(g)
        self.refused("ARCHIVE_ALTERED", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assert_nothing_removed(g, before)

    def test_genuine_resume_still_works(self):
        g, a = self.journal()
        self.crash_after_publish(g, a, count=2)
        result = rotation.resume_uncommitted(g, a, guard_src=SRC)
        self.assertEqual(result["archived"], 2)
        self.assertEqual(rotation.verify(g, a, guard_src=SRC)["archives"], 1)


class ExportBounds(Base):
    def test_duplicate_key_and_oversize_and_symlink(self):
        g, a = self.journal()
        export = self.crash_after_publish(g, a)
        raw = export.read_bytes()
        export.write_bytes(raw.replace(b'{"authorizes_execution"', b'{"authorizes_execution":false,"authorizes_execution"', 1))
        self.refused("ARCHIVE_UNREADABLE", rotation.resume_uncommitted, g, a, guard_src=SRC)
        export.write_bytes(raw)
        old = rotation.MAX_EXPORT_BYTES
        rotation.MAX_EXPORT_BYTES = 100
        try:
            self.refused("ARCHIVE_TOO_LARGE", rotation.resume_uncommitted, g, a, guard_src=SRC)
        finally:
            rotation.MAX_EXPORT_BYTES = old
        target = self.tmp / "elsewhere.json"
        export.rename(target)
        os.symlink(target, export)
        self.refused("ARCHIVE_UNREADABLE", rotation.resume_uncommitted, g, a, guard_src=SRC)

    def test_chain_entry_with_path_in_file_name(self):
        g, a = self.journal()
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=1)
        db = sqlite3.connect(g / "research-runs.sqlite3")
        body = json.loads(db.execute("SELECT body FROM archives").fetchone()[0])
        body["file"] = "../research-runs.sqlite3"
        db.execute("UPDATE archives SET body=?", (json.dumps(body),))
        db.commit()
        db.close()
        self.refused("ARCHIVE_CHAIN_BROKEN", rotation.verify, g, a, guard_src=SRC)


class WalSnapshot(Base):
    def test_rows_only_in_wal_are_seen(self):
        g, a = self.journal()
        db = sqlite3.connect(g / "research-runs.sqlite3")
        self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        db.close()
        guard = ResearchGuard(g, retain_queries=True)
        reader = sqlite3.connect(g / "research-runs.sqlite3")     # an open reader blocks checkpoints
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM runs").fetchone()
        g057.coordinator(guard).run("recherche ecrite dans le wal")
        raw_copy = self.tmp / "raw.sqlite3"
        shutil.copy2(g / "research-runs.sqlite3", raw_copy)      # what G057 v1 did
        copied = sqlite3.connect(raw_copy).execute("SELECT count(*) FROM runs").fetchone()[0]
        snap = rotation._Snapshot(g, SRC)
        reader.close()
        self.assertEqual(copied, 7, "the raw file copy misses the WAL row")
        self.assertEqual(len(snap.rows), 8, "the online backup includes it")


class Automatic(Base):
    def build_many(self, n, mission_ops=()):
        g = self.tmp / "auto" / "guard"
        guard = ResearchGuard(g, retain_queries=True)
        c = g057.coordinator(guard)
        for op in mission_ops:
            c.run("recherche de mission", operation_id=op)
        for i in range(n):
            c.run(f"recherche automatique {i}")
        a = self.tmp / "auto" / "archive"
        a.mkdir(mode=0o700)
        return g, a

    def test_keeps_target_and_mission_runs(self):
        ops = ["m-" + str(i) * 32 for i in range(3)]
        g, a = self.build_many(104, ops)                  # 107 active, the 3 oldest belong to missions
        report = rotation.auto_rotate(g, a, target=100, terminal_operations=(ops[0],), guard_src=SRC, clock_ms=1)
        self.assertEqual((report["archived"], report["active"], report["above_target"]), (7, 100, 0))
        remaining = {json.loads(b)["descriptor"].get("operation_id")
                     for (b,) in sqlite3.connect(g / "research-runs.sqlite3").execute("SELECT body FROM runs")}
        self.assertNotIn(ops[0], remaining)               # terminal mission: archived
        self.assertTrue({ops[1], ops[2]} <= remaining)    # non-terminal missions: kept
        again = rotation.auto_rotate(g, a, target=100, guard_src=SRC, clock_ms=2)
        self.assertEqual(again["archived"], 0)

    def test_overshoot_reported_when_missions_protected(self):
        ops = ["m-" + c * 32 for c in "abcdef"]
        g, a = self.build_many(0, ops)
        report = rotation.auto_rotate(g, a, target=2, guard_src=SRC, clock_ms=1)
        self.assertEqual((report["archived"], report["active"], report["above_target"]), (0, 6, 4))

    def test_recovers_partial_and_uncommitted(self):
        g, a = self.build_many(5)
        code, _ = g057.rotate_sub(g, a, 1, "after_partial_write")
        self.assertEqual(code, 9)
        report = rotation.auto_rotate(g, a, target=3, guard_src=SRC, clock_ms=1)
        self.assertEqual((report["partials_removed"], report["archived"], report["active"]), (1, 2, 3))
        g2, a2 = self.tmp / "auto2" / "guard", self.tmp / "auto2" / "archive"
        shutil.copytree(g.parent, g2.parent)
        shutil.rmtree(a2)
        a2.mkdir(mode=0o700)
        db = sqlite3.connect(g2 / "research-runs.sqlite3")
        db.execute("DROP TABLE archives")
        db.execute("PRAGMA user_version=2")
        db.commit()
        db.close()
        code, _ = g057.rotate_sub(g2, a2, 1, "after_publish")
        self.assertEqual(code, 9)
        report = rotation.auto_rotate(g2, a2, target=1, guard_src=SRC, clock_ms=2)
        self.assertEqual(report["resumed"]["archived"], 1)
        self.assertEqual(report["active"], 1)

    def test_refuses_during_intent_and_in_flight(self):
        g, a = self.build_many(3)
        subprocess.run([sys.executable, "-c", g057.CRASH_RUN, SRC, str(g)], capture_output=True)
        self.refused("WEB_RESEARCH_UNCERTAIN", rotation.auto_rotate, g, a, target=1, guard_src=SRC, clock_ms=1)
        import fcntl
        fd = os.open(g / "research-runs.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            self.refused("WEB_RESEARCH_IN_FLIGHT", rotation.auto_rotate, g, a, target=1, guard_src=SRC, clock_ms=1)
        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
