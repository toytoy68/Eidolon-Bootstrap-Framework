# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_cli_readonly.py
# Description : Lectures CLI sans initialisation, migration ou mutation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.client_sync import ClientSync
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class ReadOnlyCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.mission = Runtime(self.store).create(DEMO_REQUEST)
        self.cursor = self.root / 'cursor.json'
        self.cursor.write_text(json.dumps(ClientSync(self.store).snapshot(self.mission['id'])['cursor']))
        self.commands = [('client-missions',), ('client-snapshot', self.mission['id']),
                         ('client-poll', self.mission['id'], '--cursor', str(self.cursor))]

    def invoke(self, args, state=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--state', str(state or self.store.directory), *args])
        return code, out.getvalue(), err.getvalue()

    def files(self):
        return {p.relative_to(self.store.directory): p.read_bytes()
                for p in self.store.directory.rglob('*') if p.is_file()}

    def test_all_three_reads_preserve_bytes_without_initializing_store_or_runtime(self):
        before = self.files()
        with patch.object(Store, '__init__', side_effect=AssertionError('initialization')), \
                patch.object(Runtime, '__init__', side_effect=AssertionError('runtime')):
            for command in self.commands:
                with self.subTest(command=command[0]):
                    code, out, err = self.invoke(command)
                    self.assertEqual(code, 0, err)
                    self.assertFalse(json.loads(out)['authorizes_execution'])
                    self.assertEqual(self.files(), before)

    def test_old_schema_is_refused_without_migration(self):
        with sqlite3.connect(self.store.path) as db:
            db.execute('DROP TABLE command_receipts')
            db.execute('PRAGMA user_version=0')
        before = self.files()
        for command in self.commands:
            with self.subTest(command=command[0]):
                code, out, err = self.invoke(command)
                self.assertEqual(code, 2)
                self.assertEqual(out, '')
                self.assertIn('UNSUPPORTED_READ_SCHEMA', err)
                self.assertEqual(self.files(), before)

    def test_current_schema_missing_required_table_is_not_repaired(self):
        with sqlite3.connect(self.store.path) as db:
            db.execute('DROP TABLE command_receipts')
        before = self.files()
        for command in self.commands:
            code, out, err = self.invoke(command)
            self.assertEqual(code, 2)
            self.assertEqual(out, '')
            self.assertIn('UNSUPPORTED_READ_SCHEMA', err)
            self.assertEqual(self.files(), before)

    def test_absent_state_remains_absent_for_all_three_reads(self):
        missing = self.root / 'absent'
        for command in self.commands:
            code, out, err = self.invoke(command, missing)
            self.assertEqual(code, 2)
            self.assertEqual(out, '')
            self.assertFalse(missing.exists())

    def test_incomplete_beta_state_is_refused_without_mutation(self):
        (self.store.directory / 'BETA-PREPARATION-INCOMPLETE').write_text('synthetic incomplete')
        before = self.files()
        for command in self.commands:
            code, out, err = self.invoke(command)
            self.assertEqual(code, 2)
            self.assertEqual(out, '')
            self.assertIn('BETA_PREPARATION_INCOMPLETE', err)
            self.assertEqual(self.files(), before)

    def test_human_listing_is_also_read_only(self):
        before = self.files()
        code, out, err = self.invoke(('--format', 'human', 'client-missions'))
        self.assertEqual(code, 0, err)
        self.assertIn('Eidolon Core Technologies', out)
        self.assertEqual(self.files(), before)


if __name__ == '__main__':
    unittest.main()
