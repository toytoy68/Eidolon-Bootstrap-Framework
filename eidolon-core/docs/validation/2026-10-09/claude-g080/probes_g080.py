# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g080.py
# Description : Contre-revue indépendante des bornes producteur/lecteur de la rotation C-046 (C-TASK-G080)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/:
G062_SRC="$PWD/src" python3 -m unittest discover -s docs/validation/2026-10-09/claude-g080 -p 'probes_*.py' -v

Independent probes: rotation.py and research_archive.py are NOT modified. Synthetic journals are
built by Codex's fixture (unchanged ResearchGuard). Each probe checks the producer against the
Core reader at the EXACT limit and one unit beyond, and that every refusal happens before any
publication, with the journal and the archive folder byte-identical."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import unittest
from unittest.mock import patch

PROPOSAL = Path(__file__).resolve().parents[3] / "proposals" / "2026-10-07-research-retention"
sys.path.insert(0, str(PROPOSAL))

import tests_g062 as base  # noqa: E402
from tests_g062 import SRC, g057, rotation  # noqa: E402
from eidolon_core import research_archive as reader  # noqa: E402
from eidolon_core.research_guard import MAX_INTEGER, ResearchGuard  # noqa: E402


def files(folder):
    return {p.name: p.read_bytes() for p in Path(folder).iterdir()}


def rows(guard_dir):
    """Every journal row that carries meaning: runs, their events and cleaned queries."""
    db = sqlite3.connect(Path(guard_dir) / "research-runs.sqlite3")
    try:
        out = {}
        for identity, body in db.execute("SELECT id, body FROM runs"):
            events = [list(e) for e in db.execute("SELECT sequence, kind, body FROM run_events WHERE run_id=? "
                                                   "ORDER BY sequence", (identity,))]
            query = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone()
            out[identity] = {"id": identity, "body": body, "events": events, "cleaned_query": query[0] if query else None}
        return out
    finally:
        db.close()


class Probes(base.Base):
    def rotate(self, g, a, count=1, clock_ms=1):
        return rotation.rotate(g, a, count=count, guard_src=SRC, clock_ms=clock_ms)

    def preserved(self, code, g, a, call):
        journal, folder = (g / "research-runs.sqlite3").read_bytes(), files(a)
        self.refused(code, call)
        self.assertEqual((g / "research-runs.sqlite3").read_bytes(), journal, "journal changed on refusal")
        self.assertEqual(files(a), folder, "archive folder changed on refusal")

    def size_of_next(self, g, a, count=1, clock_ms=1):
        """Size of the export the producer WOULD publish, measured on a copy (nothing touched)."""
        copy = self.tmp / ("measure-" + os.urandom(4).hex())
        shutil.copytree(g.parent, copy, symlinks=True)
        self.rotate(copy / g.name, copy / a.name, count, clock_ms)
        new = set(files(copy / a.name)) - set(files(a))
        return (copy / a.name / new.pop()).stat().st_size

    # -- unit size --------------------------------------------------------------------------

    def test_unit_size_exact_limit_is_published_and_read_one_byte_less_is_refused_before(self):
        g, a = self.journal()
        size = self.size_of_next(g, a)
        with patch.object(reader, "MAX_ARCHIVE_BYTES", size - 1):
            self.preserved("ARCHIVE_TOO_LARGE", g, a, lambda: self.rotate(g, a))
        with patch.object(reader, "MAX_ARCHIVE_BYTES", size):
            self.rotate(g, a)
            self.assertEqual(reader.read_catalog(a)["archive_count"], 1)

    # -- cumulative volume -------------------------------------------------------------------

    def test_total_exact_limit_agrees_with_the_reader(self):
        g, a = self.journal()
        self.rotate(g, a)
        first = next(a.glob("*.json")).stat().st_size
        second = self.size_of_next(g, a, clock_ms=2)
        with patch.object(reader, "MAX_TOTAL_BYTES", first + second - 1):
            self.preserved("ARCHIVE_TOTAL_LIMIT", g, a, lambda: self.rotate(g, a, clock_ms=2))
        with patch.object(reader, "MAX_TOTAL_BYTES", first + second):
            self.rotate(g, a, clock_ms=2)
            self.assertEqual(reader.read_catalog(a)["archive_count"], 2)    # the reader agrees at equality

    # -- count and directory entries ----------------------------------------------------------

    def test_count_exact_limit(self):
        g, a = self.journal()
        with patch.object(reader, "MAX_ARCHIVES", 3):
            for clock in (1, 2, 3):
                self.rotate(g, a, clock_ms=clock)
            self.preserved("TOO_MANY_EXPORTS", g, a, lambda: self.rotate(g, a, clock_ms=4))
            self.assertEqual(reader.read_catalog(a)["archive_count"], 3)

    def test_directory_margin_is_conservative_by_one_entry(self):
        """Known, documented gap: the producer reserves partial + final (2 entries) although the
        published state holds one more entry only. Refusing a state the reader would accept is
        safe (nothing removed); reported, not a defect."""
        g, a = self.journal()
        with patch.object(reader, "MAX_DIRECTORY_ENTRIES", 1):
            self.preserved("TOO_MANY_EXPORTS", g, a, lambda: self.rotate(g, a))
        with patch.object(reader, "MAX_DIRECTORY_ENTRIES", 2):
            self.rotate(g, a)
            self.assertEqual(reader.read_catalog(a)["archive_count"], 1)

    def test_a_name_only_the_reader_refuses_stops_the_producer_before_publication(self):
        g, a = self.journal()
        stray = a / "research-archive-notes.txt"; stray.write_bytes(b"operateur"); stray.chmod(0o600)
        self.preserved("INVALID_ARCHIVE_FILENAME", g, a, lambda: self.rotate(g, a))
        stray.unlink()
        self.rotate(g, a)

    # -- timestamps (JavaScript integers) ---------------------------------------------------------

    def test_javascript_safe_timestamps_and_non_monotonic_clock(self):
        g, a = self.journal()
        self.rotate(g, a, clock_ms=1760000000000)                         # Date.now()-like value
        self.rotate(g, a, clock_ms=1)                                       # clock went backwards
        catalog = reader.read_catalog(a)
        self.assertEqual([f["created_at_ms"] for f in catalog["files"]], [1760000000000, 1])
        for clock in (MAX_INTEGER + 1, 2.0 ** 53, False, None):
            with self.subTest(clock=clock):
                self.preserved("INVALID_CLOCK", g, a, lambda: self.rotate(g, a, clock_ms=clock))

    # -- orphan export and resumption ----------------------------------------------------------------

    def test_orphan_then_journal_growth_resume_removes_only_the_exported_rows(self):
        g, a = self.journal()
        orphan = self.crash_after_publish(g, a, count=2)
        self.refused("UNCOMMITTED_EXPORT", rotation.verify, g, a, guard_src=SRC)
        self.preserved("UNCOMMITTED_EXPORT", g, a, lambda: self.rotate(g, a))
        catalog = reader.read_catalog(a)                                    # readable, commit unknown
        self.assertEqual((catalog["archive_count"], catalog["committed_status_known"]), (1, False))
        g057.coordinator(ResearchGuard(g, retain_queries=True)).run("recherche ajoutee apres la coupure")
        before = rows(g)
        exported = json.loads(orphan.read_bytes())["runs"]
        rotation.resume_uncommitted(g, a, guard_src=SRC)
        after = rows(g)
        self.assertEqual(set(before) - set(after), {r["id"] for r in exported})
        self.assertEqual({**after, **{r["id"]: r for r in exported}}, before)  # nothing lost, nothing changed
        self.assertEqual(rotation.verify(g, a, guard_src=SRC)["archives"], 1)

    def test_orphan_over_the_unit_limit_is_kept_and_not_committed(self):
        g, a = self.journal()
        orphan = self.crash_after_publish(g, a)
        with patch.object(reader, "MAX_ARCHIVE_BYTES", orphan.stat().st_size - 1):
            self.preserved("ARCHIVE_TOO_LARGE", g, a, lambda: rotation.resume_uncommitted(g, a, guard_src=SRC))
        rotation.resume_uncommitted(g, a, guard_src=SRC)

    # -- withdrawal keeps the journal whole --------------------------------------------------------

    def test_withdrawal_is_exactly_the_export_and_the_rest_is_byte_identical(self):
        g, a = self.journal()
        before = rows(g)
        done = self.rotate(g, a, count=3)
        exported = json.loads((a / done["file"]).read_bytes())["runs"]
        after = rows(g)
        self.assertEqual(len(exported), 3)
        self.assertEqual({k: v for k, v in before.items() if k not in after}, {r["id"]: r for r in exported})
        self.assertEqual({k: before[k] for k in after}, after)
        catalog = reader.read_catalog(a)
        self.assertEqual(catalog["run_count"] + len(after), len(before))


if __name__ == "__main__":
    unittest.main()
