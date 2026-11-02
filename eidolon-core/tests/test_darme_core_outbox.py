import sqlite3
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from eidolon_core.darme_core_outbox import export_once
from eidolon_core.darme_core_feed import CoreFeedVerifier
from cryptography.hazmat.primitives import serialization
from eidolon_core.darme_tool_audit import denied_tool_event
import json

class OutboxTests(unittest.TestCase):
    def test_signed_export_from_durable_core_log(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = sqlite3.connect(root/'missions.sqlite3')
            db.execute('CREATE TABLE events(sequence INTEGER PRIMARY KEY,kind TEXT,detail TEXT)')
            event = denied_tool_event(request_id='r1', tool_name='tool-x', policy_id='p1', parameters={'secret':'CANARY'})
            db.execute('INSERT INTO events VALUES(1,?,?)', ('DARME_TOOL_POLICY_DENIED', json.dumps(event.__dict__, default=lambda x:x.value)))
            db.commit(); db.close()
            key = Ed25519PrivateKey.generate()
            self.assertEqual(export_once(root/'missions.sqlite3',root/'sender.json',root/'feed.json',key),1)
            public = key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            payload, events, _ = CoreFeedVerifier(public).verify((root/'feed.json').read_bytes())
            self.assertEqual(events[0].event_id,event.event_id)
            with self.assertRaises(FileExistsError):
                export_once(root/'missions.sqlite3',root/'sender.json',root/'feed.json',key)

class InterruptedExportTests(unittest.TestCase):
    def test_orphaned_pending_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'feed.pending').write_text('{"cursor":1,"sequence":1}')
            with self.assertRaisesRegex(ValueError, 'orphaned pending'):
                export_once(root/'missing.sqlite',root/'sender.json',root/'feed.json',Ed25519PrivateKey.generate())
