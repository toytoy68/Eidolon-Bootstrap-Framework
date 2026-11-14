import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from eidolon_core.darme_core_feed import signed_envelope
from eidolon_core.darme_core_receiver import CoreFeedReceiver
from eidolon_core.darme_store import DarmeJournal
from eidolon_core.darme_tool_audit import denied_tool_event
from eidolon_core.darme import DarmeMonitor


class ReceiverTests(unittest.TestCase):
    def test_persist_restart_retransmission_and_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = Ed25519PrivateKey.generate()
            public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            journal = DarmeJournal(root / 'journal.sqlite')
            event = denied_tool_event(request_id='r1', tool_name='tool-a', policy_id='policy-a', parameters={'secret':'CANARY'})
            raw = signed_envelope(key, 1, [event])
            receiver = CoreFeedReceiver(public, root / 'checkpoint.json', journal)
            self.assertEqual(receiver.accept(raw), 1)
            receiver = CoreFeedReceiver(public, root / 'checkpoint.json', journal)
            self.assertEqual(receiver.accept(raw), 0)
            monitor = journal.replay(DarmeMonitor(('core-tool-policy',)))
            self.assertEqual(monitor.snapshot()['unacknowledged_alerts'], 1)
            self.assertEqual(len(monitor.events), 1)
            journal.close()

    def test_invalid_signature_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trusted = Ed25519PrivateKey.generate()
            other = Ed25519PrivateKey.generate()
            public = trusted.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            journal = DarmeJournal(root / 'journal.sqlite')
            receiver = CoreFeedReceiver(public, root / 'checkpoint.json', journal)
            with self.assertRaises(ValueError):
                receiver.accept(signed_envelope(other, 1, []))
            self.assertEqual(len(journal.replay(DarmeMonitor(('core-tool-policy',))).events), 0)
            journal.close()
