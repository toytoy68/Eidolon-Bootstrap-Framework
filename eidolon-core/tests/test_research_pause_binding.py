# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_pause_binding.py
# Description : Identité des pauses, migration auditée et coupures sans relance
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.contracts import ContractError
from eidolon_core.research_binding import ExistingResearchStore
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_pauses import ResearchPauses, PauseStorageError, provider_scope
from eidolon_core.research_runtime import ResearchRuntime, migrate_research_pauses
from eidolon_core.store import Store


class PauseBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.runtime = ResearchRuntime(self.store)
        self.path = self.store.directory / 'research-fixture/pauses.sqlite3'
        self.scope = provider_scope('synthetic-research-provider/1')
        self.pauses = ResearchPauses(self.path, create=False)
        self.record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.mission = self.runtime.create_research('synthetic pending')

    def migrate(self, **kwargs):
        return migrate_research_pauses(self.store, actor='synthetic operator', reason='reviewed evidence', **kwargs)

    def rows(self, path, table):
        with closing(sqlite3.connect(path)) as db:
            return db.execute('SELECT * FROM ' + table).fetchall()

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def legacy(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TABLE pause_metadata')
            db.execute('PRAGMA user_version=1')
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("DELETE FROM sync_metadata WHERE key IN ('research_fixture_pause_id','research_fixture_pause_adoption')")

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--state', str(self.store.directory), '--profile', 'research-sim', *args])
        return code, out.getvalue(), err.getvalue()

    def child(self, code):
        script = "import os, sys\nfrom unittest.mock import patch\nfrom eidolon_core.store import Store\nfrom eidolon_core.research_pauses import ResearchPauses\nfrom eidolon_core.research_runtime import migrate_research_pauses, ResearchRuntime\nstore=Store(sys.argv[1])\n" + code
        return subprocess.run([sys.executable, '-c', script, str(self.store.directory)],
                              capture_output=True, text=True, timeout=10)

    def test_new_binding_pins_pauses_without_changing_mission_configuration(self):
        self.assertRegex(self.pauses.database_id, r'^pd-[0-9a-f]{32}$')
        metadata = dict(self.rows(self.store.path, 'sync_metadata'))
        self.assertEqual(metadata['research_fixture_pause_id'], self.pauses.database_id)
        self.assertEqual(ResearchRuntime(self.store).configuration(), self.mission['configuration'])

    def test_valid_empty_replacement_refused_before_constructor_or_provider_can_run(self):
        self.path.unlink(); replacement = ResearchPauses(self.path)
        self.assertNotEqual(self.pauses.database_id, replacement.database_id)
        before = self.files()
        with patch('eidolon_core.research_runtime.FixtureProvider.search', side_effect=AssertionError('no provider')):
            with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_CHANGED$'):
                ResearchRuntime(self.store)
            with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_CHANGED$'):
                self.runtime.backend.execute({'query': 'fixture', 'required_pages': 1,
                                              'operation_id': self.mission['id']}, {})
            with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_CHANGED$'):
                self.migrate()
        self.assertEqual(self.files(), before)

    def test_live_pause_handle_checks_identity_for_reads_and_writes(self):
        self.path.unlink(); ResearchPauses(self.path)
        before = self.files()
        actions = [lambda: self.pauses.active(self.scope), self.pauses.inspect,
                   lambda: self.pauses.check_capacity([self.scope]),
                   lambda: self.pauses.pause([self.scope], reason='ACCESS_DENIED'),
                   lambda: self.pauses.release(self.record['id'], expected_revision=1, actor='op', reason='review')]
        for action in actions:
            with self.subTest(action=action), self.assertRaisesRegex(PauseStorageError, '^RESEARCH_PAUSES_CHANGED$'):
                action()
        self.assertEqual(self.files(), before)

    def test_legacy_readable_but_runtime_requires_explicit_migration_without_mutation(self):
        self.legacy()
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_MIGRATION_REQUIRED$'):
            ResearchRuntime(self.store)
        code, out, err = self.cli('research-pauses')
        self.assertEqual((code, err), (0, ''))
        self.assertIsNone(json.loads(out)['database_id'])
        self.assertEqual(json.loads(out)['pauses'], [self.record])
        self.assertEqual(self.files(), before)

    def test_migration_preserves_pause_audit_missions_events_and_guard(self):
        self.legacy()
        tables = [(self.path, 'pauses'), (self.path, 'pause_events'),
                  (self.store.path, 'missions'), (self.store.path, 'events')]
        before = [self.rows(path, table) for path, table in tables]
        guard = self.path.parent / 'guard/research-runs.sqlite3'
        guard_before = guard.read_bytes()
        with patch('socket.socket', side_effect=AssertionError('no network')):
            result = self.migrate()
        self.assertEqual(result['status'], 'BOUND')
        for field in ('authorizes_execution', 'request_sent', 'pauses_released'):
            self.assertFalse(result[field])
        self.assertEqual(before, [self.rows(path, table) for path, table in tables])
        self.assertEqual(guard.read_bytes(), guard_before)
        reopened = ResearchRuntime(self.store)
        self.assertEqual(reopened.configuration(), self.mission['configuration'])
        self.assertEqual(ResearchPauses(self.path, create=False).active(self.scope), self.record)
        audit = json.loads(dict(self.rows(self.path, 'pause_metadata'))['adoption'])
        self.assertEqual(audit['actor'], 'synthetic operator')
        self.assertEqual(audit['guard_id'], reopened.backend.guard_id)
        stable = self.files()
        self.assertEqual(self.migrate(), result)
        self.assertEqual(self.files(), stable)

    def test_pending_mission_after_migration_still_obeys_committed_pause(self):
        self.legacy(); self.migrate()
        with patch('eidolon_core.research_runtime.FixtureProvider.search', side_effect=AssertionError('paused')):
            result = ResearchRuntime(self.store).backend.execute(
                {'query': 'new synthetic', 'required_pages': 1, 'operation_id': self.mission['id']}, {})
        self.assertEqual(result['providers'][0]['status'], 'RETRY_WAIT')
        self.assertEqual(ResearchPauses(self.path, create=False).active(self.scope), self.record)

    def test_missing_base_and_malformed_identity_never_repaired_by_migration(self):
        self.path.unlink()
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_MISSING$'):
            self.migrate()
        self.assertEqual(self.files(), before)
        ResearchPauses(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE pause_metadata SET value='private-canary' WHERE key='database_id'")
        before = self.files()
        with self.assertRaisesRegex(PauseStorageError, '^INVALID_PAUSE_DATABASE_IDENTITY$'):
            self.migrate()
        self.assertEqual(self.files(), before)

    def test_schema_downgrade_of_bound_database_cannot_be_readopted(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TABLE pause_metadata'); db.execute('PRAGMA user_version=1')
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_PAUSES_CHANGED$'):
            self.migrate()
        self.assertEqual(self.files(), before)

    def test_bad_store_pause_binding_refused_before_touching_legacy_evidence(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE sync_metadata SET value='private-canary' WHERE key='research_fixture_pause_id'")
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^INVALID_RESEARCH_PAUSE_BINDING$'):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_legacy_conflicting_guard_is_not_migrated(self):
        self.legacy()
        shutil.rmtree(self.path.parent / 'guard')
        ResearchGuard(self.path.parent / 'guard', retain_queries=True)
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_BACKEND_CHANGED$'):
            self.migrate()
        self.assertEqual(self.files(), before)

    def test_malformed_pause_prevents_migration_without_partial_schema(self):
        self.legacy()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE pauses SET body='private-canary'")
        before = self.files()
        with self.assertRaisesRegex(PauseStorageError, '^INVALID_PAUSE_RECORD$'):
            self.migrate()
        self.assertEqual(self.files(), before)

    def test_concurrent_adopters_keep_one_identity_and_one_adoption(self):
        self.legacy()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.migrate(), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(self.rows(self.path, 'pause_metadata')), 2)
        self.assertEqual(ResearchPauses(self.path, create=False).active(self.scope), self.record)

    def test_process_exit_during_schema_upgrade_rolls_back_identity_and_keeps_pauses(self):
        self.legacy()
        before = self.rows(self.path, 'pause_events')
        process = self.child("original=ResearchPauses._create_identity\ndef stop(db):\n original(db)\n os._exit(81)\nwith patch.object(ResearchPauses, '_create_identity', staticmethod(stop)):\n migrate_research_pauses(store, actor='op', reason='review')\n")
        self.assertEqual(process.returncode, 81, process.stderr)
        self.assertIsNone(ResearchPauses(self.path, create=False).database_id)
        self.assertEqual(self.rows(self.path, 'pause_events'), before)
        with self.assertRaisesRegex(ContractError, 'MIGRATION_REQUIRED'):
            ResearchRuntime(self.store)
        self.migrate()
        self.assertEqual(ResearchPauses(self.path, create=False).active(self.scope), self.record)

    def test_process_exit_between_databases_requires_explicit_retry_and_keeps_original_audit(self):
        self.legacy()
        process = self.child("original=ResearchPauses.adopt_identity\ndef stop(self, **kwargs):\n original(self, **kwargs)\n os._exit(82)\nwith patch.object(ResearchPauses, 'adopt_identity', stop):\n migrate_research_pauses(store, actor='first operator', reason='first review')\n")
        self.assertEqual(process.returncode, 82, process.stderr)
        pauses = ResearchPauses(self.path, create=False)
        self.assertIsNotNone(pauses.database_id)
        before = self.rows(self.path, 'pause_metadata')
        with self.assertRaisesRegex(ContractError, 'MIGRATION_REQUIRED'):
            ResearchRuntime(self.store)
        self.migrate()
        self.assertEqual(self.rows(self.path, 'pause_metadata'), before)
        self.assertEqual(ResearchRuntime(self.store).backend.pause_id, pauses.database_id)
        self.assertEqual(pauses.active(self.scope), self.record)

    def test_process_exit_after_store_commit_is_idempotent(self):
        self.legacy()
        process = self.child("migrate_research_pauses(store, actor='first operator', reason='review')\nos._exit(83)\n")
        self.assertEqual(process.returncode, 83, process.stderr)
        before = self.files()
        self.migrate()
        ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_prebinding_crash_of_fresh_backend_does_not_trigger_silent_adoption(self):
        other = Store(self.root / 'new-state')
        from eidolon_core.research_runtime import SyntheticResearchBackend
        original = SyntheticResearchBackend.__init__
        class Stopped(BaseException): pass
        def stop(backend, *args, **kwargs):
            original(backend, *args, **kwargs)
            raise Stopped()
        with patch.object(SyntheticResearchBackend, '__init__', stop), self.assertRaises(Stopped):
            ResearchRuntime(other)
        with self.assertRaisesRegex(ContractError, 'MIGRATION_REQUIRED'):
            ResearchRuntime(other)
        migrate_research_pauses(other, actor='operator', reason='reviewed complete initialization')
        ResearchRuntime(other)

    def test_cli_existing_only_no_schema_creation_and_recovery_copies_refused(self):
        self.legacy()
        code, out, err = self.cli('research-pauses-migrate', '--actor', 'op', '--reason', 'review')
        self.assertEqual((code, err), (0, ''))
        self.assertFalse(json.loads(out)['authorizes_execution'])
        (self.store.directory / 'RECOVERY-REVIEW-ONLY').write_text('review')
        before = self.files()
        code, out, err = self.cli('research-pauses-migrate', '--actor', 'op', '--reason', 'review')
        self.assertEqual((code, out), (2, ''))
        self.assertIn('RECOVERY_REVIEW_ONLY', err)
        self.assertEqual(self.files(), before)
        missing = self.root / 'absent'
        with self.assertRaises(ContractError):
            migrate_research_pauses(ExistingResearchStore(missing), actor='op', reason='review')
        self.assertFalse(missing.exists())

    def test_fixture_release_refuses_foreign_or_unbound_database_without_mutation(self):
        command = ('research-release', self.record['id'], '--revision', '1', '--actor', 'op', '--reason', 'review')
        self.legacy()
        before = self.files()
        code, out, err = self.cli(*command)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('RESEARCH_PAUSES_MIGRATION_REQUIRED', err)
        self.assertEqual(self.files(), before)
        self.migrate()
        self.path.unlink()
        replacement = ResearchPauses(self.path)
        replacement.pause([self.scope], reason='ACCESS_DENIED')
        before = self.files()
        code, out, err = self.cli(*command)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('RESEARCH_PAUSES_CHANGED', err)
        self.assertEqual(self.files(), before)

    def test_fixture_release_checks_binding_then_preserves_revision_contract(self):
        command = ('research-release', self.record['id'], '--revision', '1', '--actor', 'op', '--reason', 'review')
        before = self.rows(self.store.path, 'events')
        with patch('eidolon_core.research_runtime.ResearchRuntime', side_effect=AssertionError('no runtime')):
            code, out, err = self.cli(*command)
        self.assertEqual((code, err), (0, ''))
        result = json.loads(out)
        self.assertEqual((result['status'], result['revision']), ('RELEASED', 2))
        self.assertFalse(result['request_sent'])
        self.assertEqual(self.rows(self.store.path, 'events'), before)
        code, out, err = self.cli(*command)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('STALE_PAUSE', err)

    def test_invalid_review_and_foreign_adoption_do_not_mutate(self):
        self.legacy()
        before = self.files()
        with self.assertRaisesRegex(ContractError, 'INVALID_PAUSE_REVIEW'):
            migrate_research_pauses(self.store, actor='', reason='review')
        self.assertEqual(self.files(), before)
        pauses = ResearchPauses(self.path, create=False)
        pauses.adopt_identity(store_id='s-' + 'a' * 32, guard_id=self.runtime.backend.guard_id, actor='op', reason='review')
        before = self.files()
        with self.assertRaisesRegex(PauseStorageError, 'PAUSE_ADOPTION_CHANGED'):
            self.migrate()
        self.assertEqual(self.files(), before)

    def test_same_identity_rollback_remains_outside_local_binding_guarantee(self):
        # Explicit limitation: identity is not an external monotonic anchor.
        saved = self.path.read_bytes()
        self.pauses.release(self.record['id'], expected_revision=1, actor='op', reason='review')
        self.path.write_bytes(saved)
        self.assertEqual(ResearchRuntime(self.store).backend.pause_id, self.pauses.database_id)
        self.assertIsNotNone(ResearchPauses(self.path, create=False).active(self.scope))

    def test_binding_lock_contention_is_normalized_without_raw_sqlite_error(self):
        connect = sqlite3.connect
        def short_wait(*args, **kwargs):
            kwargs['timeout'] = 0.03
            return connect(*args, **kwargs)
        with closing(connect(self.store.path)) as writer:
            writer.execute('BEGIN IMMEDIATE')
            before = self.files()
            with patch('sqlite3.connect', side_effect=short_wait):
                with self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_BUSY$'):
                    ResearchRuntime(self.store)
            self.assertEqual(self.files(), before)

    def test_legacy_scan_timeout_is_normalized_and_does_not_write_binding(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")
            body = db.execute('SELECT body FROM missions LIMIT 1').fetchone()[0]
            db.executemany('INSERT INTO missions(id,revision,body) VALUES (?,0,?)',
                           [('m-' + format(n, '032x'), body) for n in range(1000)])
        before = self.files()
        with patch('eidolon_core.research_runtime.time.monotonic', side_effect=[0] + [100] * 100):
            with self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_SCAN_TIMEOUT$'):
                ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_invalid_legacy_json_has_constant_binding_error(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")
            db.execute("UPDATE missions SET body='private-canary'")
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^RESEARCH_BINDING_UNAVAILABLE$'):
            ResearchRuntime(self.store)
        self.assertEqual(self.files(), before)

    def test_missing_mission_schema_is_not_created_by_migration_cli(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('DROP TABLE missions')
        before = self.files()
        code, out, err = self.cli('research-pauses-migrate', '--actor', 'op', '--reason', 'review')
        self.assertEqual((code, out), (2, ''))
        self.assertIn('RESEARCH_BINDING_UNAVAILABLE', err)
        self.assertNotIn('OperationalError', err)
        self.assertEqual(self.files(), before)

    def test_legacy_migration_does_not_clear_uncertain_research_intent(self):
        from eidolon_core.query_cleanup import clean_query
        guard = ResearchGuard(self.path.parent / 'guard', create=False)
        cleaned = clean_query('interrupted synthetic')
        class Stopped(BaseException): pass
        def stop(): raise Stopped()
        with self.assertRaises(Stopped):
            guard.execute(stop, descriptor={'query_sha256': cleaned.cleaned_sha256,
                          'policy_id': 'synthetic', 'providers': ['synthetic']}, cleaned_query=cleaned)
        self.legacy(); self.migrate()
        with self.assertRaisesRegex(ContractError, 'WEB_RESEARCH_UNCERTAIN'):
            ResearchRuntime(self.store).backend.execute(
                {'query': 'next synthetic', 'required_pages': 1, 'operation_id': self.mission['id']}, {})
        self.assertEqual(guard.inspect()['runs'][0]['state'], 'INTENT')


if __name__ == '__main__':
    unittest.main()
