import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from eidolon_core.darme_core_receipt import sign_receipt, verify_receipt

class ReceiptTests(unittest.TestCase):
    def test_signed_receipt(self):
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        raw = sign_receipt(key,1,'a'*64)
        self.assertTrue(verify_receipt(raw,public,1,'a'*64))
        with self.assertRaises(ValueError):
            verify_receipt(raw,public,2,'a'*64)
        with self.assertRaises(ValueError):
            verify_receipt(raw,public,1,'b'*64)
        other = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        with self.assertRaises(ValueError):
            verify_receipt(raw,other,1,'a'*64)

class DurableAckTests(unittest.TestCase):
    def test_export_receive_acknowledge_restart(self):
        import json, sqlite3, tempfile
        from pathlib import Path
        from eidolon_core.darme_core_outbox import export_once, acknowledge
        from eidolon_core.darme_core_receiver import CoreFeedReceiver
        from eidolon_core.darme_store import DarmeJournal
        from eidolon_core.darme_tool_audit import denied_tool_event
        from eidolon_core.darme_core_feed import canonical
        from eidolon_core.darme import DarmeMonitor
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = sqlite3.connect(root/'missions.sqlite3')
            db.execute('CREATE TABLE events(sequence INTEGER PRIMARY KEY,kind TEXT,detail TEXT)')
            event = denied_tool_event(request_id='r1', tool_name='test-tool', policy_id='test-policy', parameters={})
            db.execute('INSERT INTO events VALUES(1,?,?)', ('DARME_TOOL_POLICY_DENIED',json.dumps(event.__dict__,default=lambda x:x.value)))
            db.commit(); db.close()
            sender, receiver = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
            pub = lambda key: key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            feed, state = root/'feed.json',root/'sender.json'
            self.assertEqual(export_once(root/'missions.sqlite3',state,feed,sender),1)
            journal = DarmeJournal(root/'journal.sqlite')
            target = CoreFeedReceiver(pub(sender),root/'receiver.json',journal)
            self.assertEqual(target.accept(feed.read_bytes()),1)
            self.assertEqual(target.accept(feed.read_bytes()),0)
            payload = json.loads(feed.read_bytes())['payload']
            digest = hashlib.sha256(canonical(payload)).hexdigest()
            receipt = sign_receipt(receiver,1,digest)
            acknowledge(feed,state,feed.with_suffix('.pending'),receipt,pub(receiver))
            self.assertEqual(json.loads(state.read_text()),{'cursor':1,'sequence':1})
            self.assertFalse(feed.exists())
            self.assertEqual(export_once(root/'missions.sqlite3',state,feed,sender),0)
            self.assertEqual(len(journal.replay(DarmeMonitor(('core-tool-policy',))).events),1)
            journal.close()
