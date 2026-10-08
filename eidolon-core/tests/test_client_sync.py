# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_client_sync.py
# Description : Captures SQLite, curseurs, reconnexion et absence d'effets
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync, SyncError, project_mission
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class ClientSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = Runtime(self.store)
        self.m = self.runtime.create(DEMO_REQUEST)
        self.sync = ClientSync(self.store)
        self.identity = self.m['id']

    def append(self, count=1):
        for i in range(count):
            m = self.store.get(self.identity)
            self.store.save(m, 'SYNTHETIC_PROGRESS', {'private_detail': 'PRIVATE-MARKER'})

    def test_snapshot_and_idle_poll_do_not_modify_mission_or_events(self):
        before = (self.store.get(self.identity), self.store.events(self.identity))
        capture = self.sync.snapshot(self.identity)
        response = self.sync.poll(self.identity, capture['cursor'])
        self.assertEqual(response['status'], 'DELTA')
        self.assertEqual(response['events'], [])
        self.assertFalse(response['has_more'])
        self.assertFalse(response['authorizes_execution'])
        self.assertEqual(capture['cursor'], response['cursor'])
        self.assertEqual(before, (self.store.get(self.identity), self.store.events(self.identity)))

    def test_pages_are_bounded_and_repeated_requests_return_same_references(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        self.append(5)
        first = self.sync.poll(self.identity, cursor, limit=2)
        repeated = self.sync.poll(self.identity, cursor, limit=2)
        self.assertEqual(first['events'], repeated['events'])
        self.assertEqual(first['cursor'], repeated['cursor'])
        self.assertTrue(first['has_more'])
        self.assertGreater(first['snapshot']['as_of_sequence'], first['cursor']['sequence'])
        events = list(first['events'])
        response = first
        while response['has_more']:
            response = self.sync.poll(self.identity, response['cursor'], limit=2)
            self.assertLessEqual(len(response['events']), 2)
            events.extend(response['events'])
        self.assertEqual(len(events), 5)
        self.assertEqual(len({e['sequence'] for e in events}), 5)
        self.assertEqual(response['cursor']['sequence'], response['snapshot']['as_of_sequence'])

    def test_reopen_preserves_store_identity_and_cursor(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        self.append()
        restarted = ClientSync(Store(self.temp.name))
        response = restarted.poll(self.identity, cursor)
        self.assertEqual(response['store_id'], cursor['store_id'])
        self.assertEqual(len(response['events']), 1)

    def test_cancel_request_is_visible_even_without_revision_change(self):
        original = self.sync.snapshot(self.identity)
        self.store.request_cancel(self.identity)
        response = self.sync.poll(self.identity, original['cursor'])
        self.assertTrue(response['snapshot']['mission']['cancel_requested'])
        self.assertEqual(response['snapshot']['mission']['revision'], original['snapshot']['mission']['revision'])
        self.assertGreater(response['snapshot']['as_of_sequence'], original['snapshot']['as_of_sequence'])
        self.assertEqual(response['events'][0]['kind'], 'CANCEL_REQUESTED')
        self.assertEqual(response['snapshot']['mission']['status'], 'NEW')  # request is not acknowledgement

    def test_interleaved_other_mission_events_do_not_leak_or_make_false_gaps(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        other = self.runtime.create('PRIVATE-MARKER')
        self.append()
        self.store.request_cancel(other['id'])
        self.append()
        response = self.sync.poll(self.identity, cursor)
        self.assertEqual(response['status'], 'DELTA')
        self.assertEqual(len(response['events']), 2)
        self.assertNotIn(other['id'], json.dumps(response))
        self.assertNotIn('PRIVATE-MARKER', json.dumps(response))

    def test_malformed_or_wrong_mission_cursor_is_rejected(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        for change in ({'version': True}, {'sequence': True}, {'sequence': 2**53},
                       {'event_count': 0}, {'anchor_sha256': 'x'}, {'store_id': '../file'},
                       {'unexpected': 1}, {'mission_id': 'm-'+'a'*32}):
            with self.subTest(change=change), self.assertRaises(SyncError):
                self.sync.poll(self.identity, {**cursor, **change})
        for limit in (0, 101, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(SyncError):
                self.sync.poll(self.identity, cursor, limit=limit)

    def test_changed_store_identity_requires_explicit_reset(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        with self.store.connection() as db:
            db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ('s-'+'a'*32,))
        response = self.sync.poll(self.identity, cursor)
        self.assertEqual((response['status'], response['reason']), ('RESET_REQUIRED', 'STORE_CHANGED'))
        self.assertEqual(response['events'], [])
        self.assertNotEqual(response['cursor']['store_id'], cursor['store_id'])

    def test_restored_older_history_requires_reset(self):
        original = self.sync.snapshot(self.identity)
        self.append()
        cursor = self.sync.snapshot(self.identity)['cursor']
        with self.store.connection() as db:
            db.execute('DELETE FROM events WHERE sequence>?', (original['cursor']['sequence'],))
        response = self.sync.poll(self.identity, cursor)
        self.assertEqual(response['reason'], 'CURSOR_AHEAD')

    def test_changed_anchor_requires_reset(self):
        cursor = self.sync.snapshot(self.identity)['cursor']
        with self.store.connection() as db:
            db.execute('UPDATE events SET detail=? WHERE sequence=?', ('{"changed":true}', cursor['sequence']))
        self.assertEqual(self.sync.poll(self.identity, cursor)['reason'], 'ANCHOR_CHANGED')

    def test_deleted_prefix_requires_reset_even_if_anchor_is_unchanged(self):
        self.append(2)
        cursor = self.sync.snapshot(self.identity)['cursor']
        with self.store.connection() as db:
            db.execute('DELETE FROM events WHERE sequence=(SELECT min(sequence) FROM events WHERE mission_id=?)',
                       (self.identity,))
        self.assertEqual(self.sync.poll(self.identity, cursor)['reason'], 'HISTORY_CHANGED')

    def test_missing_history_or_mission_never_produces_a_valid_snapshot(self):
        with self.assertRaises(KeyError):
            self.sync.snapshot('m-'+'a'*32)
        with self.store.connection() as db:
            db.execute('DELETE FROM events WHERE mission_id=?', (self.identity,))
        with self.assertRaises(SyncError) as raised:
            self.sync.snapshot(self.identity)
        self.assertEqual(raised.exception.code, 'HISTORY_MISSING')

    def test_projection_excludes_private_payloads_and_cannot_change_store(self):
        m = self.store.get(self.identity)
        for key in ('request', 'context', 'model_output', 'configuration', 'result'):
            m[key] = {'PRIVATE-MARKER': True}
        # Projection is a allowlist; use an in-memory fixture, not a corrupt durable mission.
        projected = project_mission(m)
        self.assertNotIn('PRIVATE-MARKER', json.dumps(projected))
        projected['progress']['completed'] = 999
        self.assertNotEqual(m['progress']['completed'], 999)

    def test_transaction_does_not_mix_snapshot_with_concurrent_cancel(self):
        with self.store.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
        writer = Store(self.temp.name)
        connection = self.store.connection
        @contextmanager
        def interleaved_connection():
            with connection() as db:
                class Proxy:
                    def execute(_, sql, parameters=()):
                        result = db.execute(sql, parameters)
                        if sql.startswith('SELECT revision,cancel_requested,') and 'FROM missions WHERE id=?' in sql:
                            mission_row = result.fetchone()
                            writer.request_cancel(self.identity)  # commit between SELECTs
                            return SimpleNamespace(fetchone=lambda: mission_row)
                        return result
                yield Proxy()
        with patch.object(self.store, 'connection', interleaved_connection):
            before = self.sync.snapshot(self.identity)
        after = self.sync.poll(self.identity, before['cursor'])
        self.assertFalse(before['snapshot']['mission']['cancel_requested'])
        self.assertTrue(after['snapshot']['mission']['cancel_requested'])
        self.assertEqual(len(after['events']), 1)

    def test_legacy_store_upgrade_preserves_mission_history(self):
        before = self.store.events(self.identity)
        with self.store.connection() as db:
            db.execute('DROP TABLE sync_metadata')
            db.execute('DROP INDEX events_mission_sequence')
        upgraded = Store(self.temp.name)
        self.assertEqual(upgraded.events(self.identity), before)
        self.assertEqual(ClientSync(upgraded).snapshot(self.identity)['status'], 'SNAPSHOT')

    def test_cli_snapshot_and_poll_are_runtime_free(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from eidolon_core.cli import main
        output = StringIO()
        with patch('eidolon_core.cli.Runtime', side_effect=AssertionError('no runtime')), redirect_stdout(output):
            self.assertEqual(main(['--state', self.temp.name, 'client-snapshot', self.identity]), 0)
        cursor_file = Path(self.temp.name) / 'cursor.json'
        cursor_file.write_text(json.dumps(json.loads(output.getvalue())['cursor']))
        self.append()
        result = subprocess.run([sys.executable, '-m', 'eidolon_core', '--state', self.temp.name,
                                 'client-poll', self.identity, '--cursor', str(cursor_file)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['events']), 1)

    def test_cli_does_not_create_missing_store(self):
        missing = Path(self.temp.name) / 'absent'
        result = subprocess.run([sys.executable, '-m', 'eidolon_core', '--state', str(missing),
                                 'client-snapshot', self.identity], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(missing.exists())

    def test_pending_action_remains_pending_after_reconnect(self):
        runtime = ActionRuntime(self.store)
        mission = runtime.run(runtime.create_restart('nas')['id'])
        capture = self.sync.snapshot(mission['id'])
        response = ClientSync(Store(self.temp.name)).poll(mission['id'], capture['cursor'])
        view = response['snapshot']['mission']['action_view']
        self.assertEqual(view['decision']['status'], 'PENDING')
        self.assertEqual(view['effect']['code'], 'NOT_STARTED')
        self.assertFalse(view['authorizes_execution'])
        self.assertEqual(runtime.world.observe('sim-nas')['restarts'], 0)

    def test_sequence_outside_javascript_exact_range_fails_without_rounding(self):
        with self.store.connection() as db:
            db.execute('UPDATE events SET sequence=? WHERE mission_id=?', (2**53, self.identity))
        with self.assertRaises(SyncError) as raised:
            self.sync.snapshot(self.identity)
        self.assertEqual(raised.exception.code, 'UNSUPPORTED_INTEGER_RANGE')

    def test_revision_outside_javascript_exact_range_is_not_exported(self):
        with self.store.connection() as db:
            db.execute('UPDATE missions SET revision=? WHERE id=?', (2**53, self.identity))
        with self.assertRaises(SyncError) as raised:
            self.sync.snapshot(self.identity)
        self.assertEqual(raised.exception.code, 'UNSUPPORTED_INTEGER_RANGE')
