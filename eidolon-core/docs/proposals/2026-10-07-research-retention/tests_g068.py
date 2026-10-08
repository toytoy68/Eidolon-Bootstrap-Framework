# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests_g068.py
# Description : Fermeture du snapshot, codes constants et budget de copie sous écrivain concurrent (C-TASK-G068)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G062_SRC=<frozen eidolon-core/src> python3 -m unittest tests_g068 -v   (from this folder)

Codex counter-probes G086/G087: descriptors must be closed by finally/close, not by the GC;
a missing metadata row is a constant refusal; a writer holding the journal cannot make the
online backup wait forever."""
import gc
import os
import sqlite3
import time
from unittest.mock import patch

import tests_g062 as base
from tests_g062 import SRC, g057, rotation


def fds():
    return len(os.listdir("/proc/self/fd"))


class Snapshot(base.Base):
    def test_invalid_metadata_closes_everything_without_gc(self):
        g, a = self.journal()
        db = sqlite3.connect(g / "research-runs.sqlite3")
        with db:
            db.execute("DELETE FROM metadata WHERE key='guard_id'")
        db.close()
        before_bytes = (g / "research-runs.sqlite3").read_bytes()
        gc.collect()
        gc.disable()
        try:
            before = fds()
            codes = set()
            for _ in range(10):
                try:
                    rotation.verify(g, a, guard_src=SRC)
                except rotation.RotationError as exc:
                    codes.add(str(exc))
            after = fds()
        finally:
            gc.enable()
        self.assertEqual(codes, {"JOURNAL_IDENTITY_INVALID"})
        self.assertEqual(after, before, "descriptors released without the garbage collector")
        self.assertEqual((g / "research-runs.sqlite3").read_bytes(), before_bytes)
        self.assertEqual(list(a.iterdir()), [])

    def test_unexpected_journal_content_is_a_constant_refusal(self):
        for name, sql in (("table runs absente", "DROP TABLE runs"),
                          ("identité non textuelle", "UPDATE metadata SET value=x'00' WHERE key='guard_id'")):
            with self.subTest(name):
                g, a = self.journal(name.replace(" ", "-"))
                db = sqlite3.connect(g / "research-runs.sqlite3")
                with db:
                    db.execute(sql)
                db.close()
                gc.disable()
                try:
                    before = fds()
                    with self.assertRaises(rotation.RotationError) as ctx:
                        rotation.verify(g, a, guard_src=SRC)
                    self.assertEqual(fds(), before)
                finally:
                    gc.enable()
                self.assertRegex(str(ctx.exception), r"^[A-Z][A-Z0-9_]+$")

    def test_backup_under_exclusive_writer_is_refused_within_budget(self):
        g, a = self.journal()
        before = g057.state(g)
        opened = fds()
        writer = sqlite3.connect(g / "research-runs.sqlite3", isolation_level=None)
        writer.execute("BEGIN EXCLUSIVE")
        try:
            with patch.object(rotation, "SNAPSHOT_BUDGET_SECONDS", 1.0):
                gc.disable()
                try:
                    start = time.monotonic()
                    with self.assertRaises(rotation.RotationError) as ctx:
                        rotation.verify(g, a, guard_src=SRC)
                    elapsed = time.monotonic() - start
                finally:
                    gc.enable()
        finally:
            writer.execute("ROLLBACK")
            writer.close()
        # SQLite's unix VFS defers closing a descriptor while ANOTHER connection of the same
        # process holds POSIX locks on that file; it is released with the writer, not by the GC.
        self.assertEqual(fds(), opened)
        self.assertEqual(str(ctx.exception), "JOURNAL_BUSY")
        self.assertLess(elapsed, 3.0)
        self.assertEqual(g057.state(g), before)
        self.assertEqual(list(a.iterdir()), [])
        self.assertEqual(rotation.verify(g, a, guard_src=SRC)["archives"], 0, "works again once the writer is gone")

    def test_backup_with_a_reserved_writer_still_copies_committed_state(self):
        # A writer that only RESERVED the journal (uncommitted change) does not block readers.
        g, a = self.journal()
        writer = sqlite3.connect(g / "research-runs.sqlite3", isolation_level=None)
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE metadata SET value=value")
        try:
            report = rotation.verify(g, a, guard_src=SRC)
        finally:
            writer.execute("ROLLBACK")
            writer.close()
        self.assertEqual(report["archives"], 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
