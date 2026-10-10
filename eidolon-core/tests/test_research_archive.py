# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_archive.py
# Description : Contrats d'archive, lectures bornées et publication de liste.md
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing, redirect_stdout, redirect_stderr
from copy import deepcopy
import fcntl
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import research_archive as archives
from eidolon_core.contracts import digest, encode
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research_guard import ResearchGuard


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.guard = ResearchGuard(self.root / 'guard', retain_queries=True)
        self.directory = self.root / 'archives'
        self.directory.mkdir(mode=0o700)
        self.ids = []
        for index in range(3):
            cleaned = clean_query(f'PRIVATE_QUERY_CANARY étude {index} jean@example.invalid')
            result = self.guard.execute(lambda: {'status': 'NO_READABLE_SOURCE'},
                descriptor={'query_sha256': cleaned.receipt()['cleaned_sha256'],
                            'policy_id': 'synthetic', 'providers': ['synthetic'],
                            **({'operation_id': 'm-' + 'b' * 32} if index == 2 else {})}, cleaned_query=cleaned)
            self.ids.append(result['research_guard']['run_id'])
        self.records = sorted(self.guard.inspect()['runs'], key=lambda r: (r['started_at_ms'], r['id']))
        self.meta = self.export(self.records)
        self.name = 'research-archive-000001.json'
        self.save(self.meta)

    def export(self, records, index=1, previous='0' * 64):
        rows = []
        with closing(sqlite3.connect(self.guard.path)) as db:
            for record in records:
                identity = record['id']
                body = db.execute('SELECT body FROM runs WHERE id=?', (identity,)).fetchone()[0]
                events = [list(row) for row in db.execute('SELECT sequence,kind,body FROM run_events WHERE run_id=? ORDER BY sequence', (identity,))]
                query = db.execute('SELECT body FROM cleaned_queries WHERE run_id=?', (identity,)).fetchone()
                rows.append({'id': identity, 'body': body, 'events': events, 'cleaned_query': query[0] if query else None})
        return {'protocol': archives.EXPORT_PROTOCOL, 'guard_id': self.guard.guard_id, 'chain_index': index,
                'previous_chain_sha256': previous, 'created_at_ms': 1, 'runs': rows,
                'removed_ids_sha256': digest([r['id'] for r in records]), 'authorizes_execution': False}

    def save(self, meta, name=None):
        path = self.directory / (name or self.name)
        path.write_text(encode(meta))
        path.chmod(0o600)
        return path

    def files(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_valid_catalog_is_read_only_and_contains_no_query_or_authority_claim(self):
        before = self.files()
        with patch.object(ResearchGuard, '__init__', side_effect=AssertionError('guard construction')):
            catalog = archives.read_catalog(self.directory)
        self.assertEqual(self.files(), before)
        self.assertEqual(catalog['run_count'], 3)
        self.assertEqual(catalog['files'][0]['queries_with_text'], 3)
        self.assertEqual(catalog['files'][0]['linked_missions'], 1)
        for key in ('authorizes_execution', 'authenticity_verified', 'live_journal_checked', 'committed_status_known', 'request_sent'):
            self.assertIs(catalog[key], False)
        for canary in ('PRIVATE_QUERY_CANARY', 'jean@example.invalid', 'query_sha256', 'report_sha256', 'operation_id'):
            self.assertNotIn(canary, encode(catalog))
            self.assertNotIn(canary, archives.render_index(catalog))

    def test_cleaned_query_missing_or_changed_is_refused(self):
        for field in (None, '{}', self.meta['runs'][1]['cleaned_query']):
            with self.subTest(value=field is None):
                meta = deepcopy(self.meta); meta['runs'][0]['cleaned_query'] = field
                self.save(meta)
                with self.assertRaisesRegex(archives.ArchiveError, 'INVALID_RESEARCH_ARCHIVE'):
                    archives.read_catalog(self.directory)

    def test_wrong_guard_authority_and_removed_ids_are_refused(self):
        for changes in ({'guard_id': 'g-' + 'f' * 32}, {'authorizes_execution': True},
                        {'removed_ids_sha256': 'f' * 64}, {'chain_index': True}, {'chain_index': 2}):
            with self.subTest(changes=changes):
                self.save(dict(self.meta, **changes))
                with self.assertRaisesRegex(archives.ArchiveError, 'INVALID_RESEARCH_ARCHIVE'):
                    archives.read_catalog(self.directory)

    def test_intent_or_inconsistent_event_is_refused(self):
        for kind in ('intent', 'event', 'sequence', 'duplicate_run'):
            meta = deepcopy(self.meta)
            if kind == 'intent':
                meta['runs'][0]['body'] = meta['runs'][0]['events'][0][2]
            elif kind == 'event':
                meta['runs'][0]['events'][-1][1] = 'INTENT'
            elif kind == 'sequence':
                meta['runs'][1]['events'][0][0] = meta['runs'][0]['events'][0][0]
            else:
                meta['runs'].append(meta['runs'][0])
            self.save(meta)
            with self.subTest(kind=kind), self.assertRaisesRegex(archives.ArchiveError, 'INVALID_RESEARCH_ARCHIVE'):
                archives.read_catalog(self.directory)

    def test_duplicate_keys_nonfinite_and_invalid_utf8_are_refused(self):
        valid = encode(self.meta)
        for raw in ((valid[:-1]+',"authorizes_execution":false}').encode(), b'\xff', b'{"bad":NaN}'):
            with self.subTest(raw_length=len(raw)):
                (self.directory / self.name).write_bytes(raw)
                with self.assertRaisesRegex(archives.ArchiveError, 'INVALID_RESEARCH_ARCHIVE'):
                    archives.read_catalog(self.directory)

    def test_legacy_without_text_stays_explicit(self):
        meta = deepcopy(self.meta)
        for row in meta['runs']:
            value = json.loads(row['body']); value['descriptor'].pop('query_history_sha256')
            row['body'] = encode(value); row['cleaned_query'] = None
            for event in row['events']:
                value = json.loads(event[2]); value['descriptor'].pop('query_history_sha256'); event[2] = encode(value)
        self.save(meta)
        result = archives.read_catalog(self.directory)
        self.assertEqual(result['files'][0]['legacy_runs_without_text'], 3)
        self.assertEqual(result['files'][0]['queries_with_text'], 0)

    def test_complete_chain_and_missing_prior_export(self):
        first = self.export(self.records[:1]); self.save(first)
        checked = archives.validate_export(encode(first).encode(), self.name)
        second = self.export(self.records[1:], index=2, previous=digest(checked['entry']))
        self.save(second, 'research-archive-000002.json')
        self.assertEqual(archives.read_catalog(self.directory)['run_count'], 3)
        (self.directory / self.name).unlink()
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_CHAIN_BROKEN'):
            archives.read_catalog(self.directory)

    def test_repeated_run_across_archives_is_refused(self):
        first = archives.validate_export(encode(self.meta).encode(), self.name)
        repeated = self.export(self.records[:1], index=2, previous=digest(first['entry']))
        self.save(repeated, 'research-archive-000002.json')
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVED_RUN_REPEATED'):
            archives.read_catalog(self.directory)

    def test_archive_edit_breaks_following_chain(self):
        first = self.export(self.records[:1]); self.save(first)
        checked = archives.validate_export(encode(first).encode(), self.name)
        self.save(self.export(self.records[1:], 2, digest(checked['entry'])), 'research-archive-000002.json')
        first['created_at_ms'] = 2; self.save(first)
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_CHAIN_BROKEN'):
            archives.read_catalog(self.directory)

    def test_v2_released_operations_match_only_the_archived_missions(self):
        value = dict(self.meta, released_operations=['m-' + 'b' * 32])
        self.save(value)
        report = archives.read_catalog(self.directory)
        self.assertEqual(report['run_count'], 3)
        self.assertFalse(report['committed_status_known'])
        self.assertNotIn('released_operations', encode(report))

    def test_v2_missing_extra_duplicate_or_invalid_release_is_refused(self):
        for operations in ([], ['m-' + 'f' * 32], ['m-' + 'b' * 32] * 2, [True], 'all'):
            self.save(dict(self.meta, released_operations=operations))
            with self.subTest(operations=operations), self.assertRaisesRegex(archives.ArchiveError, 'INVALID_RESEARCH_ARCHIVE'):
                archives.read_catalog(self.directory)

    def test_missing_directory_not_created_and_nonprivate_directory_refused(self):
        missing = self.root / 'missing'
        with self.assertRaises(archives.ArchiveError):
            archives.read_catalog(missing)
        self.assertFalse(missing.exists())
        self.directory.chmod(0o755)
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_DIRECTORY_NOT_PRIVATE'):
            archives.read_catalog(self.directory)

    def test_symlink_fifo_and_nonprivate_file_are_refused_without_reading_target(self):
        path = self.directory / self.name
        path.chmod(0o644)
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_FILE_NOT_PRIVATE'):
            archives.read_catalog(self.directory)
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_FILE_NOT_PRIVATE'):
            archives.read_catalog(self.directory)
        path.unlink(); path.symlink_to(self.guard.path)
        with self.assertRaises(archives.ArchiveError):
            archives.read_catalog(self.directory)
        link = self.root / 'linked'; link.symlink_to(self.directory)
        with self.assertRaises(archives.ArchiveError):
            archives.read_catalog(link)

    def test_limits_and_partial_export_refuse_whole_catalog(self):
        for name, value in (('MAX_ARCHIVES', 0), ('MAX_DIRECTORY_ENTRIES', 0),
                            ('MAX_ARCHIVE_BYTES', 1), ('MAX_TOTAL_BYTES', 1)):
            with self.subTest(bound=name), patch.object(archives, name, value), self.assertRaises(archives.ArchiveError):
                archives.read_catalog(self.directory)
        (self.directory / 'attempt.partial').write_bytes(b'')
        with self.assertRaisesRegex(archives.ArchiveError, 'PARTIAL_EXPORT_PRESENT'):
            archives.read_catalog(self.directory)

    def test_change_between_file_read_and_final_sample_is_refused(self):
        original = archives._read
        def changed(*args):
            result = original(*args)
            (self.directory / self.name).write_bytes(encode(self.meta).encode() + b' ')
            return result
        with patch.object(archives, '_read', side_effect=changed), self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_CHANGED_DURING_READ'):
            archives.read_catalog(self.directory)

    def test_index_is_private_idempotent_and_does_not_modify_exports_or_guard(self):
        before = self.files()
        first = archives.write_index(self.directory)
        self.assertTrue(first['index_changed'])
        self.assertEqual((self.directory / 'liste.md').stat().st_mode & 0o777, 0o600)
        after = self.files()
        self.assertTrue(all(after[path] == value for path, value in before.items()))
        signature = archives._signature((self.directory / 'liste.md').stat())
        second = archives.write_index(self.directory)
        self.assertFalse(second['index_changed'])
        self.assertEqual(archives._signature((self.directory / 'liste.md').stat()), signature)
        self.assertTrue((self.directory / 'liste.md').read_text().startswith(archives.INDEX_HEADER))
        self.assertIn('Cohérence vérifiée à la génération', (self.directory / 'liste.md').read_text())
        self.assertIn('nouvelle inspection', (self.directory / 'liste.md').read_text())

    def test_handwritten_index_and_symlink_are_not_overwritten(self):
        index = self.directory / 'liste.md'; index.write_text('My notes'); index.chmod(0o600)
        with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_INDEX_NOT_GENERATED'):
            archives.write_index(self.directory)
        self.assertEqual(index.read_text(), 'My notes')
        index.unlink(); index.symlink_to(self.guard.path)
        before = self.guard.path.read_bytes()
        with self.assertRaises(archives.ArchiveError):
            archives.write_index(self.directory)
        self.assertEqual(self.guard.path.read_bytes(), before)

    def test_index_lock_contention_does_not_publish(self):
        lock = self.directory / '.archive-index.lock'; lock.touch(mode=0o600)
        with lock.open('r+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(archives.ArchiveError, 'ARCHIVE_INDEX_BUSY'):
                archives.write_index(self.directory)
        self.assertFalse((self.directory / 'liste.md').exists())

    def test_interruption_before_replace_retains_previous_complete_index(self):
        archives.write_index(self.directory)
        index = self.directory / 'liste.md'; before = index.read_bytes()
        changed = dict(self.meta, created_at_ms=2); self.save(changed)
        with patch.object(archives.os, 'replace', side_effect=OSError('synthetic')), self.assertRaises(archives.ArchiveError):
            archives.write_index(self.directory)
        self.assertEqual(index.read_bytes(), before)
        self.assertEqual(list(self.directory.glob('.liste-*.tmp')), [])
        self.assertTrue(archives.write_index(self.directory)['index_changed'])

    def test_cli_json_human_and_constant_private_error(self):
        for form in ('json', 'human'):
            out = io.StringIO()
            with redirect_stdout(out):
                code = archives.main(['--directory', str(self.directory), '--format', form, 'inspect'])
            self.assertEqual(code, 0)
            self.assertNotIn('PRIVATE_QUERY_CANARY', out.getvalue())
            if form == 'human':
                self.assertIn('Eidolon Core Technologies', out.getvalue())
        self.save(dict(self.meta, guard_id='PRIVATE_ERROR_CANARY'))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archives.main(['--directory', str(self.directory), 'inspect'])
        self.assertEqual(code, 2); self.assertEqual(out.getvalue(), '')
        self.assertEqual(json.loads(err.getvalue())['error'], 'INVALID_RESEARCH_ARCHIVE')
        self.assertNotIn('PRIVATE_ERROR_CANARY', err.getvalue())


if __name__ == '__main__':
    unittest.main()
