# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests_c046.py
# Description : Compatibilité des refus producteur/lecteur avant retrait
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic fixtures only; producer remains isolated from Core runtime."""
from unittest.mock import patch
import sqlite3
import tests_g062 as base
from tests_g062 import SRC, g057, rotation
from eidolon_core import research_archive as reader
from eidolon_core.research_guard import MAX_INTEGER


class ReaderLimits(base.Base):
    def assert_refusal_preserves(self, code, g, a, call):
        before = (g / 'research-runs.sqlite3').read_bytes()
        files = {p.name: p.read_bytes() for p in a.iterdir()}
        self.refused(code, call)
        self.assertEqual((g / 'research-runs.sqlite3').read_bytes(), before)
        self.assertEqual({p.name: p.read_bytes() for p in a.iterdir()}, files)

    def rotate(self, g, a, clock_ms=1):
        return rotation.rotate(g, a, count=1, guard_src=SRC, clock_ms=clock_ms)

    def test_size_refused_before_any_export(self):
        g, a = self.journal()
        with patch.object(reader, 'MAX_ARCHIVE_BYTES', 1024):
            self.assert_refusal_preserves('ARCHIVE_TOO_LARGE', g, a, lambda: self.rotate(g, a))
        self.rotate(g, a)
        self.assertEqual(reader.read_catalog(a)['run_count'], 1)

    def test_count_limit_and_existing_catalog_remain_readable(self):
        g, a = self.journal()
        with patch.object(reader, 'MAX_ARCHIVES', 2):
            self.rotate(g, a)
            self.rotate(g, a)
            self.assert_refusal_preserves('TOO_MANY_EXPORTS', g, a, lambda: self.rotate(g, a))
            self.assertEqual(reader.read_catalog(a)['archive_count'], 2)

    def test_total_limit_and_recovery_after_budget_increase(self):
        g, a = self.journal()
        self.rotate(g, a)
        occupied = next(a.glob('*.json')).stat().st_size
        with patch.object(reader, 'MAX_TOTAL_BYTES', occupied + 1):
            self.assert_refusal_preserves('ARCHIVE_TOTAL_LIMIT', g, a, lambda: self.rotate(g, a))
            self.assertEqual(reader.read_catalog(a)['archive_count'], 1)
        self.rotate(g, a)
        self.assertEqual(reader.read_catalog(a)['archive_count'], 2)

    def test_directory_budget_counts_non_archive_entries(self):
        g, a = self.journal()
        p = a / 'operator-note'; p.write_bytes(b'synthetic'); p.chmod(0o600)
        with patch.object(reader, 'MAX_DIRECTORY_ENTRIES', 2):
            self.assert_refusal_preserves('TOO_MANY_EXPORTS', g, a, lambda: self.rotate(g, a))
        self.rotate(g, a)
        self.assertEqual(reader.read_catalog(a)['archive_count'], 1)

    def test_invalid_clocks_both_entry_points(self):
        g, a = self.journal()
        for clock in (True, -1, 1.5, '1', MAX_INTEGER + 1):
            for fn in (lambda: self.rotate(g, a, clock), lambda: rotation.auto_rotate(
                    g, a, target=1, guard_src=SRC, clock_ms=clock)):
                with self.subTest(clock=clock):
                    self.assert_refusal_preserves('INVALID_CLOCK', g, a, fn)

    def test_clock_boundaries_accepted_by_core_reader(self):
        for value in (0, MAX_INTEGER):
            g, a = self.journal(str(value))
            self.rotate(g, a, value)
            self.assertEqual(reader.read_catalog(a)['run_count'], 1)

    def test_orphan_unreadable_clock_is_not_committed(self):
        g, a = self.journal()
        orphan = self.crash_after_publish(g, a)
        self.rewrite(orphan, lambda data: data.update(created_at_ms=MAX_INTEGER + 1))
        self.assert_refusal_preserves('ARCHIVE_UNREADABLE', g, a,
                                     lambda: rotation.resume_uncommitted(g, a, guard_src=SRC))

    def test_over_budget_existing_orphan_is_not_committed(self):
        g, a = self.journal()
        self.crash_after_publish(g, a)
        with patch.object(reader, 'MAX_TOTAL_BYTES', 1):
            self.assert_refusal_preserves('ARCHIVE_TOTAL_LIMIT', g, a,
                                         lambda: rotation.resume_uncommitted(g, a, guard_src=SRC))
        rotation.resume_uncommitted(g, a, guard_src=SRC)
        self.assertEqual(reader.read_catalog(a)['archive_count'], 1)


    def test_snapshot_copy_deadline_preserves_state_and_closes_handles(self):
        g, a = self.journal()
        with patch.object(rotation.time, 'monotonic', side_effect=(0.0, 6.0)):
            self.assert_refusal_preserves('JOURNAL_SNAPSHOT_BUDGET_EXHAUSTED', g, a,
                                         lambda: rotation.verify(g, a, guard_src=SRC))
        self.assertEqual(rotation.verify(g, a, guard_src=SRC)['archives'], 0)



    def test_live_guard_identity_changed_after_publish_refuses_retirement(self):
        g, a = self.journal()
        before = g057.state(g)
        publish = rotation._publish

        def replace_identity(*args):
            name = publish(*args)
            db = sqlite3.connect(g / 'research-runs.sqlite3')
            try:
                with db:
                    db.execute("UPDATE metadata SET value=? WHERE key='guard_id'", ('g-' + 'f' * 32,))
            finally:
                db.close()
            return name

        with patch.object(rotation, '_publish', side_effect=replace_identity):
            self.refused('JOURNAL_CHANGED', self.rotate, g, a)
        self.assertEqual(g057.state(g), before)
        self.assertEqual(len(list(a.glob('*.json'))), 1, 'orphan retained for review')



    def test_chain_summary_changed_refused_without_mutation(self):
        g, a = self.journal()
        self.rotate(g, a)
        db = sqlite3.connect(g / 'research-runs.sqlite3')
        try:
            import json
            data = json.loads(db.execute('SELECT body FROM archives WHERE seq=1').fetchone()[0])
            data['count'] += 1
            with db:
                db.execute('UPDATE archives SET body=? WHERE seq=1', (rotation._canon(data).decode(),))
        finally:
            db.close()
        self.assert_refusal_preserves('ARCHIVE_CHAIN_BROKEN', g, a,
                                     lambda: rotation.verify(g, a, guard_src=SRC))

    def test_directory_scan_failure_is_constant_and_preserves_journal(self):
        g, a = self.journal()
        with patch.object(rotation.os, 'scandir', side_effect=PermissionError('synthetic private detail')):
            self.assert_refusal_preserves('ARCHIVE_UNREADABLE', g, a, lambda: self.rotate(g, a))


if __name__ == '__main__':
    import unittest
    unittest.main()
