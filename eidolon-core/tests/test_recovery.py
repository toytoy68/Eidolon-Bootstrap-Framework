# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_recovery.py
# Description : Copies de revue, garde persistante et erreurs de stockage
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.cli import main
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands, lookup_receipt
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.recovery import inspect_review, prepare_review
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'source')
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create(DEMO_REQUEST)
        self.target = self.root / 'review'

    def prepare(self, **kwargs):
        return prepare_review(self.store.path, self.target, actor='synthetic-operator', reason='restoration rehearsal', **kwargs)

    def rows(self, path, table):
        with closing(sqlite3.connect(path)) as db:
            return db.execute('SELECT * FROM ' + table).fetchall()

    def test_copy_has_new_identity_and_preserves_historical_records_and_source(self):
        cancel = dict(protocol=CANCEL_PROTOCOL, store_id=ClientSync(self.store).snapshot(self.mission['id'])['store_id'],
                      client_id='test-client', command_key='cancel', mission_id=self.mission['id'],
                      actor='synthetic', reason='test')
        CancelCommands(self.store).submit(cancel)
        before = self.store.path.read_bytes()
        report = self.prepare()
        self.assertEqual(report['source_store_id'], cancel['store_id'])
        self.assertNotEqual(report['store_id'], cancel['store_id'])
        self.assertTrue(report['historical_only'])
        self.assertFalse(report['external_effects_reconciled'])
        self.assertFalse(report['execution_authority'])
        self.assertEqual(report['counts'], {'missions': 1, 'events': 2, 'command_receipts': 1})
        for table in ('missions', 'events', 'command_receipts'):
            self.assertEqual(self.rows(self.store.path, table), self.rows(self.target / 'missions.sqlite3', table))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.lookup_original(cancel)['status'], 'FOUND')
        self.assertEqual(inspect_review(self.target)['recovery_id'], report['recovery_id'])

    def lookup_original(self, command):
        return lookup_receipt(self.store, **{k: command[k] for k in ('store_id', 'client_id', 'command_key')})

    def test_runtime_and_old_commands_cannot_open_copy_even_if_identity_known(self):
        report = self.prepare()
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)
        # Emulate a long-lived Store whose directory now points to this copy.
        self.store.path = self.target / 'missions.sqlite3'
        self.store.directory = self.target
        old = dict(protocol=CANCEL_PROTOCOL, store_id=report['source_store_id'], client_id='client',
                   command_key='old', mission_id=self.mission['id'], actor='test', reason='test')
        operations = [lambda: self.store.create(DEMO_REQUEST, self.runtime.configuration()),
                      lambda: self.store.save(self.mission, 'SHOULD_NOT_WRITE'),
                      lambda: self.store.request_cancel(self.mission['id']),
                      lambda: CancelCommands(self.store).submit(old),
                      lambda: CancelCommands(self.store).submit({**old, 'store_id': report['store_id']}),
                      lambda: ClientSync(self.store).snapshot(self.mission['id']),
                      lambda: self.lookup_original(old), lambda: self.runtime.run(self.mission['id'])]
        before = (self.target / 'missions.sqlite3').read_bytes()
        with patch.object(self.runtime, '_invoke', side_effect=AssertionError('provider must not run')):
            for operation in operations:
                with self.subTest(operation=operation), self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
                    operation()
        self.assertEqual((self.target / 'missions.sqlite3').read_bytes(), before)

    def test_database_guard_survives_missing_marker_and_reopen(self):
        self.prepare()
        (self.target / 'RECOVERY-REVIEW-ONLY').unlink()
        for _ in range(2):
            with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
                Store(self.target)
        self.assertEqual(inspect_review(self.target)['mode'], 'REVIEW_ONLY')

    def test_marker_blocks_incomplete_or_missing_database_without_creating_it(self):
        with patch('eidolon_core.recovery.os.link', side_effect=OSError('publication interrupted')):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        self.assertTrue((self.target / 'review.pending.sqlite3').exists())
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)
        self.assertFalse((self.target / 'missions.sqlite3').exists())

    def test_recovery_never_overwrites_existing_directory_or_source(self):
        self.target.mkdir()
        sentinel = self.target / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(sentinel.read_text(), 'keep')
        for target in (self.store.directory, self.store.directory / 'nested'):
            with self.assertRaisesRegex(ContractError, 'RECOVERY_DESTINATION'):
                prepare_review(self.store.path, target, actor='test', reason='test')
        self.assertFalse((self.store.directory / 'nested').exists())

    def test_competing_final_file_is_not_overwritten(self):
        import os
        link = os.link
        def race(source, target):
            Path(target).write_bytes(b'concurrent destination')
            return link(source, target)
        with patch('eidolon_core.recovery.os.link', side_effect=race):
            with self.assertRaises(FileExistsError):
                self.prepare()
        self.assertEqual((self.target / 'missions.sqlite3').read_bytes(), b'concurrent destination')
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)

    def test_size_and_backup_deadline_limits_leave_no_runtime_database(self):
        with patch('eidolon_core.recovery.MAX_DATABASE_BYTES', 1):
            with self.assertRaisesRegex(ContractError, 'RECOVERY_SIZE_LIMIT'):
                self.prepare()
        self.assertFalse(self.target.exists())
        with patch('eidolon_core.recovery.time.monotonic', side_effect=[0, 31]):
            with self.assertRaisesRegex(ContractError, 'RECOVERY_BACKUP_LIMIT'):
                self.prepare()
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)

    def test_snapshot_includes_wal_and_is_consistent_with_concurrent_writer(self):
        import eidolon_core.recovery as recovery
        with closing(sqlite3.connect(self.store.path)) as keeper:
            keeper.execute('PRAGMA journal_mode=WAL')
            keeper.execute('PRAGMA wal_autocheckpoint=0')
            keeper.execute('BEGIN')
            keeper.execute('SELECT count(*) FROM missions').fetchone()
            second = self.runtime.create(DEMO_REQUEST)
            self.assertTrue(Path(str(self.store.path) + '-wal').exists())
            readonly = recovery._readonly
            owner = self
            class Proxy:
                def __init__(self, db): self.db = db
                def __getattr__(self, name): return getattr(self.db, name)
                def backup(self, destination, **kwargs):
                    owner.runtime.create(DEMO_REQUEST)  # committed after the source read snapshot began
                    self.db.backup(destination, **kwargs)
            with patch.object(recovery, '_readonly', side_effect=lambda path: Proxy(readonly(path))):
                report = self.prepare()
            self.assertEqual(report['counts']['missions'], 2)
            self.assertEqual(len(self.rows(self.store.path, 'missions')), 3)
            self.assertEqual(inspect_review(self.target, mission_id=second['id'])['mission']['status_at_snapshot'], 'NEW')

    def test_approved_mission_remains_historical_and_world_is_not_copied(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart('nas')['id'])
        runtime.decide(mission['id'], expected_sha256=mission['proposal']['sha256'], decision='approve', actor='test', reason='test')
        self.prepare()
        report = inspect_review(self.target, mission_id=mission['id'])
        self.assertEqual(report['mission']['proposal_status_at_snapshot'], 'APPROVED')
        self.assertFalse(report['execution_authority'])
        self.assertFalse((self.target / 'simulation.sqlite3').exists())
        with patch('eidolon_core.cli.ActionRuntime', side_effect=AssertionError('must not construct')):
            with patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(main(['--state', str(self.target), '--profile', 'action-sim', 'run', mission['id']]), 2)
        self.assertEqual(runtime.world.observe('sim-nas')['restarts'], 0)

    def test_terminal_status_and_sensitive_content_are_historical_only(self):
        completed = self.runtime.run(self.mission['id'])
        self.assertEqual(completed['status'], 'SUCCEEDED')
        self.prepare()
        report = inspect_review(self.target, mission_id=completed['id'])
        self.assertEqual(report['mission']['status_at_snapshot'], 'SUCCEEDED')
        self.assertTrue(report['historical_only'])
        self.assertNotIn('request', report['mission'])
        self.assertNotIn('result', report['mission'])
        self.assertNotIn('context', report['mission'])

    def test_invalid_source_or_actor_does_not_create_destination(self):
        for actor in ('', '\ud800', 'x' * 201):
            with self.assertRaises(ValueError):
                prepare_review(self.store.path, self.target, actor=actor, reason='test')
        with self.store.connection() as db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(ContractError, 'UNSUPPORTED_RECOVERY_SCHEMA'):
            self.prepare()
        self.assertFalse(self.target.exists())

    def test_a_review_copy_cannot_be_prepared_as_an_active_store(self):
        self.prepare()
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            prepare_review(self.target / 'missions.sqlite3', self.root / 'review2', actor='test', reason='test')
        self.assertFalse((self.root / 'review2').exists())

    def test_readonly_inspection_missing_normal_and_mismatched_databases(self):
        with self.assertRaises(sqlite3.Error):
            inspect_review(self.root / 'missing')
        self.assertFalse((self.root / 'missing').exists())
        with self.assertRaisesRegex(ContractError, 'NOT_A_RECOVERY_COPY'):
            inspect_review(self.store.directory)
        self.prepare()
        with self.assertRaises(KeyError):
            inspect_review(self.target, mission_id='m-' + 'f' * 32)
        with closing(sqlite3.connect(self.target / 'missions.sqlite3')) as db:
            with db: db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ('s-' + 'f' * 32,))
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REPORT_MISMATCH'):
            inspect_review(self.target)

    def test_cli_prepare_inspect_no_runtime_and_sql_error_has_uncertain_outcome(self):
        args = ['recovery-prepare', '--source', str(self.store.path), '--destination', str(self.target), '--actor', 'test', '--reason', 'test']
        with patch('eidolon_core.cli.Runtime', side_effect=AssertionError), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.getvalue())['mode'], 'REVIEW_ONLY')
        with patch('eidolon_core.cli.Store', side_effect=AssertionError), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['--state', str(self.target), '--format', 'human', 'recovery-inspect']), 0)
            self.assertIn('[ATTENTION]', output.getvalue())
            self.assertNotIn('[OK]', output.getvalue())
        with patch('eidolon_core.recovery.inspect_review', side_effect=sqlite3.OperationalError('SECRET internal path')), \
                patch('sys.stderr', new_callable=io.StringIO) as output:
            self.assertEqual(main(['--state', str(self.target), 'recovery-inspect']), 2)
            result = json.loads(output.getvalue())
            self.assertEqual(result['error'], 'STORAGE_UNAVAILABLE')
            self.assertIn('uncertainty', result['message'])
            self.assertNotIn('SECRET', output.getvalue())

    def test_child_exit_after_publication_loses_reply_but_copy_remains_blocked(self):
        code = """
import os,sys
from unittest.mock import patch
from eidolon_core.recovery import prepare_review
with patch('eidolon_core.recovery.inspect_review', side_effect=lambda *a: os._exit(74)):
    prepare_review(sys.argv[1],sys.argv[2],actor='test',reason='test')
"""
        result = subprocess.run([sys.executable, '-c', code, str(self.store.path), str(self.target)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 74, result.stderr)
        self.assertEqual(inspect_review(self.target)['mode'], 'REVIEW_ONLY')
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)
        self.assertFalse((self.target / 'review.pending.sqlite3').exists())

    def test_child_exit_before_publication_leaves_blocked_review_directory(self):
        code = '''
import os,sys
from unittest.mock import patch
from eidolon_core.recovery import prepare_review
with patch('eidolon_core.recovery.os.link', side_effect=lambda *a: os._exit(73)):
    prepare_review(sys.argv[1],sys.argv[2],actor='test',reason='test')
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.store.path), str(self.target)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 73, result.stderr)
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            Store(self.target)
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        self.assertEqual(self.store.get(self.mission['id']), self.mission)


if __name__ == '__main__':
    unittest.main()
