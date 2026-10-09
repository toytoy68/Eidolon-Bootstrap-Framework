# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_read_storage_bounds.py
# Description : Limites de lecture SQL et refus WAL sans fichiers annexes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import client_sync as sync
from eidolon_core.contracts import ContractError
from eidolon_core.http_api import ReadOnlyStore
from eidolon_core.mission_list import MissionList
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class ReadStorageBoundsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root)
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create('synthetic fixture')
        self.reader = ReadOnlyStore(self.root)

    def update(self, sql, args=()):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute(sql, args)

    def files(self):
        return {p.name: (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes())
                for p in self.root.iterdir() if p.is_file()}

    def consumers(self):
        return (lambda: MissionList(self.reader).page(),
                lambda: sync.ClientSync(self.reader).snapshot(self.mission['id']))

    def test_mission_size_is_refused_before_materializing_or_decoding_text(self):
        self.update('UPDATE missions SET body=CAST(zeroblob(1000000) AS TEXT)')
        before = self.files()
        original = sync._stored_text
        def decode(storage_type, raw, maximum, code):
            if code == 'MISSION':
                self.fail('oversized mission materialized before refusal')
            return original(storage_type, raw, maximum, code)
        with patch.object(sync, 'MAX_MISSION_BYTES', 16384), patch.object(sync, '_stored_text', side_effect=decode):
            for consumer in self.consumers():
                with self.assertRaisesRegex(sync.SyncError, '^MISSION_SIZE_LIMIT$'):
                    consumer()
        self.assertEqual(self.files(), before)

    def test_cell_is_readonly_closed_and_never_read_when_oversized(self):
        class Cell:
            closed = False
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def __len__(self): return 10**9
            def read(self, size): raise AssertionError('oversized cell read')
        class Connection:
            def blobopen(self, table, column, rowid, *, readonly):
                self.args = (table, column, rowid, readonly)
                self.cell = Cell(); return self.cell
        db = Connection()
        with self.assertRaisesRegex(sync.SyncError, '^MISSION_SIZE_LIMIT$'):
            sync._cell_text(db, 'missions', 'body', 1, 'text', 1024, 'MISSION')
        self.assertEqual(db.args, ('missions', 'body', 1, True))
        self.assertTrue(db.cell.closed)

    def test_unsupported_incremental_io_has_no_unbounded_fallback(self):
        with self.assertRaisesRegex(sync.SyncError, '^BOUNDED_READ_UNAVAILABLE$'):
            sync._cell_text(object(), 'missions', 'body', 1, 'text', 1024, 'MISSION')

    def test_incremental_read_preserves_actual_row_identity_after_id_reordering(self):
        second = self.runtime.create('second')
        third = self.runtime.create('third')
        with self.reader.connection() as db:
            db.execute('BEGIN')
            for expected in (third, self.mission, second):
                row = sync.read_mission_row(db, expected['id'])
                actual = sync.decode_mission(expected['id'], *row)
                self.assertEqual(actual['id'], expected['id'])

    def test_event_anchor_read_is_bounded_and_error_does_not_expose_detail(self):
        self.update('UPDATE events SET detail=CAST(zeroblob(1000000) AS TEXT)')
        before = self.files()
        with patch.object(sync, 'MAX_EVENT_BYTES', 16384):
            for consumer in self.consumers():
                with self.assertRaisesRegex(sync.SyncError, '^EVENT_SIZE_LIMIT$'):
                    consumer()
        self.assertEqual(self.files(), before)

    def test_blob_json_is_not_silently_decoded_as_utf16_or_accepted_as_text(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            body = db.execute('SELECT body FROM missions').fetchone()[0]
        for encoding in ('utf-16', 'utf-8'):
            self.update('UPDATE missions SET body=?', (sqlite3.Binary(body.encode(encoding)),))
            for consumer in self.consumers():
                with self.subTest(encoding=encoding), self.assertRaisesRegex(sync.SyncError, '^INVALID_MISSION_STORAGE_TYPE$'):
                    consumer()
        self.update('UPDATE missions SET body=?', (body,))
        self.update('UPDATE events SET detail=?', (sqlite3.Binary(b'private-canary'),))
        for consumer in self.consumers():
            with self.assertRaisesRegex(sync.SyncError, '^INVALID_EVENT_STORAGE_TYPE$'):
                consumer()

    def test_utf8_boundary_is_byte_based_without_rejecting_valid_multibyte_text(self):
        self.mission = self.runtime.create('été 😀')
        with closing(sqlite3.connect(self.store.path)) as db:
            raw = db.execute('SELECT body FROM missions WHERE id=?', (self.mission['id'],)).fetchone()[0]
        size = len(raw.encode('utf-8'))
        with patch.object(sync, 'MAX_MISSION_BYTES', size):
            self.assertEqual(sync.ClientSync(self.reader).snapshot(self.mission['id'])['status'], 'SNAPSHOT')
        with patch.object(sync, 'MAX_MISSION_BYTES', size - 1):
            with self.assertRaisesRegex(sync.SyncError, '^MISSION_SIZE_LIMIT$'):
                sync.ClientSync(self.reader).snapshot(self.mission['id'])

    def test_large_event_metadata_is_refused_before_any_page_is_returned(self):
        self.update('UPDATE events SET kind=?', ('x' * 1000000,))
        for consumer in self.consumers():
            with self.assertRaisesRegex(sync.SyncError, '^INVALID_EVENT_REFERENCE$'):
                consumer()

    def test_poll_does_not_load_detail_of_every_event_and_cursor_hash_remains_exact(self):
        client = sync.ClientSync(self.reader)
        first = client.snapshot(self.mission['id'])
        for _ in range(3):
            self.store.save(self.mission, 'SYNTHETIC')
        # Intermediate event bodies are not part of the public event references.
        self.update('UPDATE events SET detail=CAST(zeroblob(1000000) AS TEXT) WHERE sequence=2')
        with patch.object(sync, 'MAX_EVENT_BYTES', 16384):
            page = client.poll(self.mission['id'], first['cursor'])
            self.assertEqual([r['sequence'] for r in page['events']], [2, 3, 4])
            self.assertEqual(client.poll(self.mission['id'], page['cursor'])['events'], [])
            with self.assertRaisesRegex(sync.SyncError, '^EVENT_SIZE_LIMIT$'):
                client.poll(self.mission['id'], first['cursor'], limit=1)  # this event becomes the anchor

    def test_wal_read_refused_before_sqlite_can_create_sidecars(self):
        self.update('PRAGMA journal_mode=WAL')
        self.assertFalse((self.root / 'missions.sqlite3-wal').exists())
        self.assertFalse((self.root / 'missions.sqlite3-shm').exists())
        before = self.files()
        with self.assertRaisesRegex(ContractError, '^READ_ONLY_WAL_UNSUPPORTED$'):
            ReadOnlyStore(self.root)
        for consumer in self.consumers():
            with self.assertRaisesRegex(ContractError, '^READ_ONLY_WAL_UNSUPPORTED$'):
                consumer()
        self.assertEqual(self.files(), before)

    def test_corrupt_header_and_nonregular_database_never_repaired(self):
        self.store.path.write_bytes(b'private-canary')
        before = self.files()
        with self.assertRaises(sqlite3.DatabaseError):
            ReadOnlyStore(self.root)
        self.assertEqual(self.files(), before)
