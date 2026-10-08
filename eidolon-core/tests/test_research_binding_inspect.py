# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_binding_inspect.py
# Description : Consultation bornée sans création ni mutation des trois identités
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing, redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.contracts import ContractError
from eidolon_core import research_binding_inspect as inspect
from eidolon_core.research_pauses import ResearchPauses, provider_scope
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.store import Store


class BindingInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'state')
        self.runtime = ResearchRuntime(self.store)
        self.path = self.store.directory / 'research-fixture/pauses.sqlite3'
        ResearchPauses(self.path, create=False).pause([provider_scope('private-provider')], reason='ACCESS_DENIED')

    def files(self):
        return {str(p.relative_to(self.root)): (p.stat().st_mode, p.stat().st_mtime_ns, p.read_bytes())
                for p in self.root.rglob('*') if p.is_file()}

    def test_three_ids_observed_readonly_without_content_or_authority_claim(self):
        before = self.files()
        with patch.object(Store, '__init__', side_effect=AssertionError('no Store initialization')):
            result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'BOUND')
        self.assertEqual(result['guard']['database_id'], self.runtime.backend.guard_id)
        self.assertEqual(result['pauses']['database_id'], self.runtime.backend.pause_id)
        for key in ('authorizes_execution', 'request_sent', 'state_modified', 'histories_verified',
                    'snapshots_atomic', 'rollback_detection_supported'):
            self.assertFalse(result[key])
        self.assertNotIn('private-provider', json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(self.files(), before)

    def test_legacy_and_missing_binding_report_review_without_adoption(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("DELETE FROM sync_metadata WHERE key='research_fixture_pause_id'")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TABLE pause_metadata'); db.execute('PRAGMA user_version=1')
        before = self.files()
        result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'MIGRATION_REVIEW_REQUIRED')
        self.assertEqual(result['pauses']['state'], 'LEGACY_NO_ID')
        self.assertEqual(self.files(), before)

    def test_replacement_and_missing_evidence_have_distinct_diagnostics(self):
        self.path.unlink(); ResearchPauses(self.path)
        before = self.files()
        result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'IDENTITY_MISMATCH')
        self.assertNotEqual(result['pauses']['expected_id'], result['pauses']['database_id'])
        self.assertEqual(self.files(), before)
        self.path.unlink(); before = self.files()
        result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'MISSING_EVIDENCE')
        self.assertEqual(self.files(), before)

    def test_changes_between_samples_are_not_reported_bound(self):
        original = inspect._component
        def changed(path, kind):
            result = original(path, kind)
            if kind == 'pauses':
                path.unlink(); ResearchPauses(path)
            return result
        with patch.object(inspect, '_component', side_effect=changed):
            result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'CHANGED_DURING_INSPECTION')
        self.assertFalse(result['authorizes_execution'])

    def test_store_rebinding_between_samples_is_detected(self):
        original = inspect._component
        def changed(path, kind):
            result = original(path, kind)
            if kind == 'pauses':
                with closing(sqlite3.connect(self.store.path)) as db, db:
                    db.execute("UPDATE sync_metadata SET value=? WHERE key='research_fixture_pause_id'", ('pd-' + 'e' * 32,))
            return result
        with patch.object(inspect, '_component', side_effect=changed):
            result = inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(result['status'], 'CHANGED_DURING_INSPECTION')

    def test_wal_is_refused_without_creating_sidecars(self):
        with closing(sqlite3.connect(self.path)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
        self.assertFalse(Path(str(self.path) + '-wal').exists())
        self.assertFalse(Path(str(self.path) + '-shm').exists())
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^READ_ONLY_WAL_UNSUPPORTED$'):
            inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(self.files(), before)

    def test_symlink_fifo_and_directory_are_refused_without_opening_target(self):
        original = self.path.read_bytes()
        foreign = self.root / 'foreign'; foreign.write_bytes(original)
        for kind in ('symlink', 'fifo', 'directory'):
            self.path.unlink()
            if kind == 'symlink': self.path.symlink_to(foreign)
            elif kind == 'fifo': os.mkfifo(self.path)
            else: self.path.mkdir()
            with self.subTest(kind=kind), self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_FILE_TYPE$'):
                inspect.inspect_research_binding(self.store.directory)
            self.assertEqual(foreign.read_bytes(), original)
            if kind == 'directory': self.path.rmdir()
            else: self.path.unlink()
            self.path.write_bytes(original)

    def test_malformed_and_oversized_identity_is_not_echoed_or_repaired(self):
        for value in ('private-canary', 'pd-' + 'a' * 129, 'x' * 1000000):
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute("UPDATE pause_metadata SET value=? WHERE key='database_id'", (value,))
            before = self.files()
            with self.assertRaisesRegex(ContractError, '^INVALID_RESEARCH_BINDING_IDENTITY$'):
                inspect.inspect_research_binding(self.store.directory)
            self.assertEqual(self.files(), before)

    def test_query_connections_are_readonly_and_cannot_write(self):
        with inspect._read_connection(self.path) as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM pauses')

    def test_missing_store_and_review_copy_never_created_or_activated(self):
        absent = self.root / 'absent'
        with self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_INSPECTION_UNAVAILABLE$'):
            inspect.inspect_research_binding(absent)
        self.assertFalse(absent.exists())
        (self.store.directory / 'RECOVERY-REVIEW-ONLY').write_text('review')
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_REVIEW_ONLY$'):
            inspect.inspect_research_binding(self.store.directory)
        self.assertEqual(self.files(), before)

    def test_cli_json_human_exit_codes_and_no_runtime(self):
        for form in ('json', 'human'):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err), patch.object(
                    ResearchRuntime, '__init__', side_effect=AssertionError('no runtime')):
                code = main(['--state', str(self.store.directory), '--format', form, 'research-binding-inspect'])
            self.assertEqual((code, err.getvalue()), (0, ''))
            if form == 'json': self.assertEqual(json.loads(out.getvalue())['status'], 'BOUND')
            else: self.assertIn('Eidolon Core Technologies', out.getvalue())
        self.path.unlink()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--state', str(self.store.directory), 'research-binding-inspect'])
        self.assertEqual((code, err.getvalue()), (2, ''))
        self.assertEqual(json.loads(out.getvalue())['status'], 'MISSING_EVIDENCE')


if __name__ == '__main__':
    unittest.main()
