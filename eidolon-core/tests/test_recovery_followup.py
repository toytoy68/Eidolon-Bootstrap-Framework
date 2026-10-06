# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_recovery_followup.py
# Description : Concurrence de copie et gardes après interruption (revue G017)
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

from eidolon_core import recovery
from eidolon_core.cli import main
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class RecoveryFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'source')
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create(DEMO_REQUEST)
        self.target = self.root / 'review'

    def prepare(self):
        return recovery.prepare_review(self.store.path, self.target, actor='synthetic', reason='G017 follow-up')

    def proxy(self, callback):
        readonly = recovery._readonly
        class Proxy:
            def __init__(self, db): self.db = db
            def __getattr__(self, name): return getattr(self.db, name)
            def backup(self, destination, **kwargs):
                original_progress = kwargs['progress']
                def progress(status, remaining, total):
                    callback(status, remaining, total)
                    original_progress(status, remaining, total)
                kwargs['progress'] = progress
                return self.db.backup(destination, **kwargs)
        return patch.object(recovery, '_readonly', side_effect=lambda path: Proxy(readonly(path)))

    def test_writer_commits_between_steps_in_delete_and_wal_modes(self):
        for journal in ('DELETE', 'WAL'):
            with self.subTest(journal=journal):
                self.target = self.root / ('review-' + journal)
                with closing(sqlite3.connect(self.store.path)) as db:
                    db.execute('PRAGMA journal_mode=' + journal)
                    db.execute('CREATE TABLE IF NOT EXISTS filler (body BLOB)')
                    db.execute('INSERT INTO filler VALUES (zeroblob(2097152))')
                    db.commit()
                writers = []
                code = '''import sys
from eidolon_core.store import Store
from eidolon_core.runtime import Runtime
from eidolon_core.memory import DEMO_REQUEST
print(Runtime(Store(sys.argv[1])).create(DEMO_REQUEST)['id'])
'''
                def during_copy(status, remaining, total):
                    if remaining > 0 and not writers:
                        writers.append(subprocess.run([sys.executable, '-c', code, str(self.store.directory)],
                                                      capture_output=True, text=True, timeout=12))
                with self.proxy(during_copy):
                    result = self.prepare()
                self.assertEqual(len(writers), 1)
                self.assertEqual(writers[0].returncode, 0, writers[0].stderr)
                created = writers[0].stdout.strip()
                with closing(sqlite3.connect(self.target / 'missions.sqlite3')) as db:
                    self.assertEqual(db.execute('PRAGMA quick_check').fetchall(), [('ok',)])
                    self.assertEqual(db.execute('SELECT count(*) FROM missions WHERE id=?', (created,)).fetchone()[0], 1)
                    self.assertEqual(db.execute("SELECT count(*) FROM events WHERE mission_id=? AND kind='CREATED'", (created,)).fetchone()[0], 1)
                self.assertFalse(result['execution_authority'])
                with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'): Store(self.target)

    def test_source_identity_changed_during_backup_is_rejected(self):
        changed = []
        def change_identity(status, remaining, total):
            if not changed:
                # A callback on the final step is too late for the copied image;
                # use a large source so this happens before the final step.
                with closing(sqlite3.connect(self.store.path, timeout=0.1)) as db:
                    db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ('s-'+'a'*32,))
                    db.commit()
                changed.append(True)
        with self.store.connection() as db:
            db.execute('CREATE TABLE filler (body BLOB)')
            db.execute('INSERT INTO filler VALUES (zeroblob(2097152))')
        with self.proxy(change_identity), self.assertRaisesRegex(ContractError, 'RECOVERY_SOURCE_CHANGED'):
            self.prepare()
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'): Store(self.target)

    def test_repeated_restarts_keep_deadline_and_no_publication(self):
        with self.store.connection() as db:
            db.execute('CREATE TABLE filler (body BLOB)')
            db.execute('INSERT INTO filler VALUES (zeroblob(2097152))')
        writes = []
        def write_each_step(status, remaining, total):
            with closing(sqlite3.connect(self.store.path, timeout=0.1)) as db:
                db.execute('INSERT INTO filler VALUES (?)', (b'x',))
                db.commit()
            writes.append(remaining)
        with self.proxy(write_each_step), patch.object(recovery.time, 'monotonic', side_effect=[0, 1, 2, 31]):
            with self.assertRaisesRegex(ContractError, 'RECOVERY_BACKUP_LIMIT'): self.prepare()
        self.assertEqual(len(writes), 3)
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'): Store(self.target)

    def test_pending_copy_blocks_store_even_without_marker(self):
        with patch.object(recovery.os, 'link', side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError): self.prepare()
        (self.target / 'RECOVERY-REVIEW-ONLY').unlink()
        before = (self.target / 'review.pending.sqlite3').read_bytes()
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'): Store(self.target)
        self.assertFalse((self.target / 'missions.sqlite3').exists())
        self.assertEqual((self.target / 'review.pending.sqlite3').read_bytes(), before)

    def test_incomplete_inspection_and_cli_are_specific_and_do_not_create_database(self):
        self.target.mkdir()
        (self.target / 'review.pending.sqlite3').write_bytes(b'incomplete synthetic file')
        with self.assertRaisesRegex(ContractError, 'RECOVERY_INCOMPLETE'):
            recovery.inspect_review(self.target)
        with patch('sys.stderr', new_callable=io.StringIO) as error:
            self.assertEqual(main(['--state', str(self.target), 'recovery-inspect']), 2)
        self.assertIn('RECOVERY_INCOMPLETE', json.loads(error.getvalue())['message'])
        self.assertNotIn('Traceback', error.getvalue())
        self.assertFalse((self.target / 'missions.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
