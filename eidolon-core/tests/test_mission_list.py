# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_mission_list.py
# Description : Pagination, cohérence, confidentialité et absence d'effets
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.cli import main
from eidolon_core.client_sync import SyncError
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.mission_list import MissionList, parse_cursor
from eidolon_core.recovery import prepare_review
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class MissionListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'source')
        self.runtime = Runtime(self.store)
        self.listing = MissionList(self.store)

    def create(self, count=1):
        return [self.runtime.create(DEMO_REQUEST) for _ in range(count)]

    def invoke_cli(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--state', str(self.store.directory), *arguments])
        return code, out.getvalue(), err.getvalue()

    def test_empty_existing_store_is_a_complete_empty_page(self):
        page = self.listing.page()
        self.assertEqual(page['status'], 'PAGE')
        self.assertEqual(page['items'], [])
        self.assertEqual(page['generation'], dict(sequence=0, event_count=0, mission_count=0, anchor_sha256=None))
        self.assertFalse(page['has_more'])
        self.assertIsNone(page['next_cursor'])
        self.assertFalse(page['authorizes_execution'])

    def test_pages_cover_sorted_ids_once_and_survive_reader_restart(self):
        missions = self.create(5)
        first = self.listing.page(limit=2)
        cursor = copy.deepcopy(first['next_cursor'])
        second = MissionList(Store(self.store.directory)).page(cursor=cursor, limit=2)
        repeated = self.listing.page(cursor=cursor, limit=2)
        self.assertEqual(second['items'], repeated['items'])
        self.assertEqual(second['next_cursor'], repeated['next_cursor'])
        self.assertEqual(cursor, first['next_cursor'])
        last = self.listing.page(cursor=second['next_cursor'], limit=2)
        self.assertFalse(last['has_more'])
        self.assertIsNone(last['next_cursor'])
        self.assertEqual([len(p['items']) for p in (first, second, last)], [2, 2, 1])
        self.assertEqual([i['mission']['id'] for p in (first, second, last) for i in p['items']],
                         sorted(m['id'] for m in missions))
        self.assertTrue(all(p['generation'] == first['generation'] for p in (second, last)))

    def test_projection_excludes_private_content_and_does_not_write(self):
        mission = self.runtime.create('PRIVATE-MARKER-request')
        self.runtime.run(mission['id'])
        before = self.store.path.read_bytes()
        with patch('eidolon_core.worker.invoke', side_effect=AssertionError('must not invoke')):
            page = self.listing.page()
        m = page['items'][0]['mission']
        self.assertIsNone(m['objective_kind'])
        self.assertEqual(m['outcome_status'], 'CLARIFICATION')
        self.assertEqual(m['status'], 'BLOCKED')
        self.assertEqual(set(m), {'id', 'revision', 'status', 'phase', 'cancel_requested',
                                  'progress', 'objective_kind', 'outcome_status', 'action_view'})
        self.assertNotIn('PRIVATE-MARKER', json.dumps(page))
        self.assertEqual(before, self.store.path.read_bytes())

    def test_cancel_invalidates_pages_even_without_revision_change(self):
        missions = self.create(2)
        first = self.listing.page(limit=1)
        m = missions[0]
        self.store.request_cancel(m['id'])
        self.assertEqual(m['revision'], self.store.get(m['id'])['revision'])
        reset = self.listing.page(cursor=first['next_cursor'])
        self.assertEqual(reset['status'], 'RESET_REQUIRED')
        self.assertEqual(reset['reason'], 'STATE_CHANGED')
        self.assertEqual(reset['items'], [])
        self.assertFalse(reset['has_more'])
        self.assertIsNone(reset['next_cursor'])
        fresh = self.listing.page()
        current = next(i['mission'] for i in fresh['items'] if i['mission']['id'] == m['id'])
        self.assertTrue(current['cancel_requested'])
        self.assertEqual(current['status'], 'NEW')

    def test_new_mission_and_progress_each_require_restart(self):
        missions = self.create(2)
        first = self.listing.page(limit=1)
        self.create()
        self.assertEqual(self.listing.page(cursor=first['next_cursor'])['status'], 'RESET_REQUIRED')
        cursor = self.listing.page(limit=1)['next_cursor']
        self.store.save(self.store.get(missions[0]['id']), 'SYNTHETIC_PROGRESS')
        self.assertEqual(self.listing.page(cursor=cursor)['reason'], 'STATE_CHANGED')

    def test_cursor_from_another_store_returns_reset_without_items(self):
        self.create(2)
        cursor = self.listing.page(limit=1)['next_cursor']
        other = MissionList(Store(self.root / 'other'))
        result = other.page(cursor=cursor)
        self.assertEqual(result['reason'], 'STORE_CHANGED')
        self.assertEqual(result['items'], [])

    def test_changed_head_or_removed_event_requires_reset(self):
        mission = self.create(2)[0]
        self.store.save(self.store.get(mission['id']), 'SYNTHETIC_PROGRESS')
        cursor = self.listing.page(limit=1)['next_cursor']
        with self.store.connection() as db:
            db.execute("UPDATE events SET kind='CHANGED' WHERE sequence=(SELECT max(sequence) FROM events)")
        self.assertEqual(self.listing.page(cursor=cursor)['reason'], 'STATE_CHANGED')
        cursor = self.listing.page(limit=1)['next_cursor']
        with self.store.connection() as db:
            db.execute('DELETE FROM events WHERE sequence=1')
        self.assertEqual(self.listing.page(cursor=cursor)['reason'], 'STATE_CHANGED')

    def test_wal_writer_cannot_mix_generation_and_mission_view(self):
        mission = self.create(2)[0]
        with self.store.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
        writer = Store(self.store.directory)
        connection = self.store.connection
        @contextmanager
        def interleaved():
            with connection() as db:
                class Proxy:
                    def blobopen(_, *args, **kwargs):
                        return db.blobopen(*args, **kwargs)
                    def execute(_, sql, parameters=()):
                        result = db.execute(sql, parameters)
                        if "FROM sync_metadata WHERE key='store_id'" in sql:
                            row = result.fetchone()  # first read pins the SQLite snapshot
                            writer.request_cancel(mission['id'])
                            return SimpleNamespace(fetchone=lambda: row)
                        return result
                yield Proxy()
        with patch.object(self.store, 'connection', interleaved):
            old = self.listing.page(limit=1)
        self.assertTrue(all(not i['mission']['cancel_requested'] for i in old['items']))
        self.assertEqual(old['generation']['event_count'], 2)
        self.assertEqual(self.listing.page(cursor=old['next_cursor'])['status'], 'RESET_REQUIRED')
        fresh = self.listing.page()
        self.assertEqual(fresh['generation']['event_count'], 3)
        self.assertTrue(next(i['mission']['cancel_requested'] for i in fresh['items']
                             if i['mission']['id'] == mission['id']))

    def test_invalid_limit_rejected_before_opening_store(self):
        with patch.object(self.store, 'connection', side_effect=AssertionError('no DB')):
            for limit in (True, False, 0, -1, 101, 1.0, None, '2'):
                with self.subTest(limit=limit), self.assertRaisesRegex(SyncError, 'INVALID_PAGE_LIMIT'):
                    self.listing.page(limit=limit)

    def test_cursor_fields_types_and_ranges_are_strict(self):
        self.create(2)
        valid = self.listing.page(limit=1)['next_cursor']
        bad = [None, [], {}, {**valid, 'version': True}, {**valid, 'version': 1.0},
               {**valid, 'after_id': 'bad'}, {**valid, 'store_id': 'bad'}, {**valid, 'extra': 1}]
        for key in ('sequence', 'event_count', 'mission_count'):
            for value in (True, 1.0, 0, -1, 2**53, float('inf')):
                bad.append({**valid, 'generation': {**valid['generation'], key: value}})
        bad.append({**valid, 'generation': {**valid['generation'], 'anchor_sha256': '\ud800'}})
        for cursor in bad:
            with self.subTest(cursor=repr(cursor)), self.assertRaisesRegex(SyncError, 'INVALID_LIST_CURSOR'):
                parse_cursor(json.dumps(cursor).encode())
        self.assertEqual(parse_cursor(json.dumps(valid).encode()), valid)

    def test_cursor_parser_rejects_duplicates_deep_invalid_utf8_and_oversize(self):
        self.create(2)
        valid = json.dumps(self.listing.page(limit=1)['next_cursor']).encode()
        bad = [valid[:-1]+b',"version":1}', b'\xef\xbb\xbf'+valid, b'\xff',
               b'['*2000+b']'*2000, b'x'*4097, b'NaN', valid.replace(b'"version": 1', b'"version": 1e999')]
        for raw in bad:
            with self.subTest(raw=raw[:50]), self.assertRaisesRegex(SyncError, 'INVALID_LIST_CURSOR'):
                parse_cursor(raw)

    def test_unknown_anchor_id_is_not_a_silent_skip(self):
        self.create(2)
        cursor = self.listing.page(limit=1)['next_cursor']
        cursor['after_id'] = 'm-' + '0'*32
        with self.assertRaisesRegex(SyncError, 'INVALID_LIST_CURSOR'):
            self.listing.page(cursor=cursor)

    def test_no_history_and_unsafe_integer_fail_without_partial_page(self):
        mission = self.create()[0]
        with self.store.connection() as db:
            db.execute('UPDATE missions SET revision=?', (2**53,))
        with self.assertRaisesRegex(SyncError, 'UNSUPPORTED_INTEGER_RANGE'):
            self.listing.page()
        with self.store.connection() as db:
            db.execute('UPDATE missions SET revision=0')
            db.execute('DELETE FROM events WHERE mission_id=?', (mission['id'],))
        with self.assertRaisesRegex(SyncError, 'HISTORY_MISSING'):
            self.listing.page()

    def test_action_view_is_read_only_and_does_not_expire_pending(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart('nas')['id'])
        before = self.store.path.read_bytes()
        page = self.listing.page()
        view = page['items'][0]['mission']['action_view']
        self.assertEqual(view['decision']['status'], 'PENDING')
        self.assertFalse(view['authorizes_execution'])
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(mission['proposal']['status'], 'PENDING')

    def test_review_copy_cannot_be_listed_by_stale_store(self):
        self.create()
        target = self.root / 'review'
        prepare_review(self.store.path, target, actor='synthetic', reason='test')
        self.store.directory, self.store.path = target, target / 'missions.sqlite3'
        with self.assertRaisesRegex(ContractError, 'RECOVERY_REVIEW_ONLY'):
            self.listing.page()

    def test_cli_no_runtime_json_human_and_explicit_reset_exit(self):
        self.create(2)
        with patch('eidolon_core.cli.Runtime', side_effect=AssertionError('no runtime')):
            code, out, err = self.invoke_cli('client-missions', '--limit', '1')
            self.assertEqual((code, err), (0, ''))
            page = json.loads(out)
            file = self.root / 'cursor.json'
            file.write_text(json.dumps(page['next_cursor']))
            self.create()
            code, out, err = self.invoke_cli('client-missions', '--cursor', str(file))
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out)['status'], 'RESET_REQUIRED')
            code, out, err = self.invoke_cli('--format', 'human', 'client-missions')
            self.assertEqual(code, 0)
            self.assertIn('Eidolon Core', out)
            self.assertIn('[INFO]', out)

    def test_cli_missing_store_does_not_create_it(self):
        missing = self.root / 'absent'
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--state', str(missing), 'client-missions']), 2)
        self.assertFalse(missing.exists())

    def test_cli_sqlite_failure_keeps_diagnostic_without_raw_message(self):
        with patch.object(MissionList, 'page', side_effect=sqlite3.OperationalError('SECRET-SQL')):
            code, out, err = self.invoke_cli('client-missions')
        self.assertEqual((code, out), (2, ''))
        self.assertEqual(json.loads(err)['error'], 'STORAGE_UNAVAILABLE')
        self.assertNotIn('SECRET-SQL', err)
