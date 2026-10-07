# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests_g063.py
# Description : Conservation des données lors des pannes de publication du prototype de rotation (C-TASK-G063)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G062_SRC=<frozen eidolon-core/src> python3 -m unittest tests_g063 -v   (from this folder)

Every removal must be covered by a complete, durable, re-read export: after each case the
union of all exports plus the journal must still hold every original row byte for byte."""
import errno
import json
import os
from pathlib import Path
import sqlite3
import threading
import unittest
from unittest.mock import patch

import tests_g062 as base           # sets sys.path / SRC, builds the synthetic journals
from tests_g062 import SRC, g057, rotation
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research_guard import ResearchGuard


def rows(guard_dir):
    db = sqlite3.connect(Path(guard_dir) / "research-runs.sqlite3")
    out = {}
    for identity, body in db.execute("SELECT id, body FROM runs"):
        events = [list(e) for e in db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? ORDER BY sequence",
                                              (identity,))]
        query = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone()
        out[identity] = {"id": identity, "body": body, "events": events, "cleaned_query": query[0] if query else None}
    db.close()
    return out


def exported(archive_dir):
    out = {}
    for p in Path(archive_dir).glob("research-archive-*.json"):
        try:
            for run in json.loads(p.read_bytes())["runs"]:
                out[run["id"]] = run
        except ValueError:
            pass
    return out


class Conservation(base.Base):
    def assert_conserved(self, original, g, a):
        """Every original run is either still active or in a READABLE export, identical."""
        active, archived = rows(g), exported(a)
        for identity, row in original.items():
            self.assertEqual(active.get(identity) or archived.get(identity), row, identity)

    def test_short_writes_are_completed(self):
        g, a = self.journal()
        original = rows(g)
        real = os.write
        with patch.object(rotation.os, "write", side_effect=lambda fd, b: real(fd, bytes(b)[:max(1, len(b) // 2)])):
            result = rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=1)
        self.assertEqual(result["archived"], 2)
        json.loads(next(a.glob("*.json")).read_bytes())          # complete, readable
        self.assert_conserved(original, g, a)
        self.assertEqual(rotation.verify(g, a, guard_src=SRC)["archives"], 1)

    def test_zero_write_and_no_space_remove_nothing(self):
        for name, effect in (("zero", lambda fd, b: 0), ("enospc", OSError(errno.ENOSPC, "no space"))):
            with self.subTest(name):
                g, a = self.journal(name)
                original, before = rows(g), g057.state(g)
                with patch.object(rotation.os, "write", side_effect=effect):
                    self.refused("ARCHIVE_WRITE_FAILED", rotation.rotate, g, a, count=2, guard_src=SRC, clock_ms=1)
                self.assertEqual(g057.state(g), before)
                self.assertEqual(list(a.iterdir()), [], "no export, no leftover partial of this call")
                self.assert_conserved(original, g, a)

    def test_published_file_differs_from_written_bytes(self):
        g, a = self.journal()
        original, before = rows(g), g057.state(g)
        real = os.link

        def link_then_damage(src, dst):
            real(src, dst)
            with open(dst, "ab") as f:
                f.write(b"x")             # not JSON whitespace: the published file is now unreadable
        with patch.object(rotation.os, "link", side_effect=link_then_damage):
            self.refused("ARCHIVE_PUBLISH_MISMATCH", rotation.rotate, g, a, count=2, guard_src=SRC, clock_ms=1)
        self.assertEqual(g057.state(g), before, "nothing removed")
        self.assertEqual(len(list(a.glob("*.json"))), 1, "the damaged export is kept for review")
        self.refused("ARCHIVE_UNREADABLE", rotation.resume_uncommitted, g, a, guard_src=SRC)
        self.assertEqual(g057.state(g), before)
        self.assert_conserved(original, g, a)

    def test_codex_partial_kept_when_intent_is_uncertain(self):
        g, a = self.journal()
        partial = a / "research-archive-unrecognized.partial"
        partial.write_text("Synthetic notes that are not a valid archive")
        partial.chmod(0o600)
        q = clean_query("synthetic uncertain")

        class Interrupted(BaseException):
            pass

        def interrupted():
            raise Interrupted()
        try:
            ResearchGuard(g, create=False).execute(interrupted, cleaned_query=q, descriptor={
                "query_sha256": q.cleaned_sha256, "policy_id": "synthetic", "providers": ["synthetic"]})
        except Interrupted:
            pass
        self.refused("WEB_RESEARCH_UNCERTAIN", rotation.auto_rotate, g, a, target=1, guard_src=SRC, clock_ms=1)
        self.assertTrue(partial.exists())

    def test_unknown_or_truncated_partials_are_kept(self):
        for name, content in (("foreign", None), ("truncated", "cut")):
            with self.subTest(name):
                g, a = self.journal(name)
                if name == "foreign":
                    partial = a / "notes.partial"
                    partial.write_text("manual notes")
                else:
                    code, _ = g057.rotate_sub(g, a, 2, "after_partial_write")
                    self.assertEqual(code, 9)
                    partial = next(a.glob("*.partial"))
                    partial.write_bytes(partial.read_bytes()[: partial.stat().st_size // 2])
                partial.chmod(0o600)
                before, data = g057.state(g), partial.read_bytes()
                self.refused("PARTIAL_EXPORT_PRESENT", rotation.auto_rotate, g, a, target=1, guard_src=SRC, clock_ms=1)
                self.assertEqual((g057.state(g), partial.read_bytes()), (before, data))

    def test_complete_own_partial_is_removed_only_when_redundant(self):
        g, a = self.journal()
        original = rows(g)
        code, _ = g057.rotate_sub(g, a, 2, "after_partial_write")
        self.assertEqual(code, 9)
        report = rotation.auto_rotate(g, a, target=4, guard_src=SRC, clock_ms=2)
        self.assertEqual((report["partials_removed"], report["archived"]), (1, 3))
        self.assert_conserved(original, g, a)

    def test_every_crash_point_conserves_and_resumes_idempotently(self):
        for point in ("after_partial_write", "after_publish", "inside_transaction", "after_commit"):
            with self.subTest(point):
                g, a = self.journal(point)
                original = rows(g)
                code, _ = g057.rotate_sub(g, a, 2, point)
                self.assertEqual(code, 9)
                self.assert_conserved(original, g, a)
                first = rotation.auto_rotate(g, a, target=5, guard_src=SRC, clock_ms=2)
                second = rotation.auto_rotate(g, a, target=5, guard_src=SRC, clock_ms=3)
                self.assertEqual(second["archived"], 0, "idempotent")
                self.assertEqual(second["resumed"], None)
                self.assert_conserved(original, g, a)
                self.assertEqual(rotation.verify(g, a, guard_src=SRC)["active"], first["active"])

    def test_fifo_and_special_files_never_block(self):
        g, a = self.journal()
        rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=1)
        export = next(a.glob("*.json"))
        export.rename(self.tmp / "moved.json")
        os.mkfifo(export, 0o600)
        result = {}
        t = threading.Thread(target=lambda: result.update(r=g057.attempt(rotation.verify, g, a, guard_src=SRC)))
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "verify blocked on a FIFO")
        self.assertEqual(result["r"], "REFUS NOT_PRIVATE")
        os.unlink(export)
        partial = a / "research-archive-000002.json.0123456789abcdef.partial"
        os.mkfifo(partial, 0o600)
        t = threading.Thread(target=lambda: result.update(p=g057.attempt(
            rotation.auto_rotate, g, a, target=1, guard_src=SRC, clock_ms=2)))
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "auto_rotate blocked on a FIFO partial")
        self.assertEqual(result["p"], "REFUS PARTIAL_EXPORT_PRESENT")   # refused without blocking, kept
        self.assertTrue(partial.exists())


if __name__ == "__main__":
    unittest.main()
