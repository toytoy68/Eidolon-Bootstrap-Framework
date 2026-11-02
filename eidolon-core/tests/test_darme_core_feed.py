import base64
from datetime import datetime, timezone, timedelta
import json
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from eidolon_core.darme_core_feed import CoreFeedVerifier, SCHEMA, canonical


class CoreFeedTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.verifier = CoreFeedVerifier(public)
        self.payload = dict(schema=SCHEMA, sequence=1, generated_at=datetime.now(timezone.utc).isoformat(), events=[])

    def signed(self):
        return canonical({'payload': self.payload, 'signature': base64.b64encode(self.key.sign(canonical(self.payload))).decode()})

    def test_valid_and_idempotent(self):
        payload, events, digest = self.verifier.verify(self.signed())
        self.assertEqual(events, [])
        self.verifier.commit(payload, digest)
        self.verifier.verify(self.signed())

    def test_tampering_rejected(self):
        raw = json.loads(self.signed())
        raw['payload']['sequence'] = 2
        with self.assertRaises(ValueError):
            self.verifier.verify(canonical(raw))

    def test_missing_sequence_rejected(self):
        self.payload['sequence'] = 3
        with self.assertRaisesRegex(ValueError, 'missing sequence'):
            self.verifier.verify(self.signed())

    def test_stale_feed_rejected(self):
        self.payload['generated_at'] = (datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()
        with self.assertRaisesRegex(ValueError, 'stale feed'):
            self.verifier.verify(self.signed())

    def test_untrusted_event_rejected(self):
        self.payload['events'] = [dict(event_id='fake', source='core-tool-policy', category='tool_policy_denied', severity='warning', observed_at=datetime.now(timezone.utc).isoformat(), subject='x')]
        with self.assertRaisesRegex(ValueError, 'invalid event'):
            self.verifier.verify(self.signed())

class SignedProducerTests(unittest.TestCase):
    def test_producer_verifier_roundtrip(self):
        from eidolon_core.darme_core_feed import signed_envelope
        from eidolon_core.darme_tool_audit import denied_tool_event
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        event = denied_tool_event(request_id='m-123', tool_name='tool-test', policy_id='policy-test', parameters={'secret':'CANARY'})
        raw = signed_envelope(key, 1, [event])
        payload, events, digest = CoreFeedVerifier(public).verify(raw)
        self.assertEqual(events[0].event_id, event.event_id)
        self.assertNotIn(b'CANARY', raw)

    def test_producer_refuses_untrusted_event(self):
        from eidolon_core.darme_core_feed import signed_envelope
        with self.assertRaises(ValueError):
            signed_envelope(Ed25519PrivateKey.generate(), 1, ['fake'])
