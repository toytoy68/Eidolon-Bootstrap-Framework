"""Authenticated, offline Core denial feed verification (not deployed)."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from .darme import SecurityEvent, Severity, _instant

SCHEMA = 'eidolon-darme-core-feed/1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


class CoreFeedVerifier:
    def __init__(self, public_key, *, sequence=0, previous_digest=None, now=None):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        self.key = Ed25519PublicKey.from_public_bytes(public_key)
        self.sequence = sequence
        self.previous_digest = previous_digest
        self.now = now or (lambda: datetime.now(timezone.utc))

    def verify(self, raw):
        from cryptography.exceptions import InvalidSignature
        if len(raw) > 65536:
            raise ValueError('oversized feed')
        envelope = json.loads(raw)
        if not isinstance(envelope, dict) or set(envelope) != {'payload', 'signature'}:
            raise ValueError('invalid envelope')
        payload = envelope['payload']
        encoded = canonical(payload)
        signature = base64.b64decode(envelope['signature'], validate=True)
        try:
            self.key.verify(signature, encoded)
        except InvalidSignature as exc:
            raise ValueError('invalid signature') from exc
        if (not isinstance(payload, dict) or set(payload) != {'schema', 'sequence', 'generated_at', 'events'}
                or payload['schema'] != SCHEMA or type(payload['sequence']) is not int
                or payload['sequence'] < 1 or not isinstance(payload['events'], list)
                or len(payload['events']) > 64):
            raise ValueError('invalid payload')
        age = (self.now() - _instant(payload['generated_at'])).total_seconds()
        if not -5 <= age <= 60:
            raise ValueError('stale feed')
        digest = hashlib.sha256(encoded).hexdigest()
        if payload['sequence'] < self.sequence or (payload['sequence'] == self.sequence and digest != self.previous_digest):
            raise ValueError('replay')
        if payload['sequence'] > self.sequence + 1:
            raise ValueError('missing sequence')
        events = []
        seen = set()
        for row in payload['events']:
            if (not isinstance(row, dict) or set(row) != {'event_id', 'source', 'category', 'severity', 'observed_at', 'subject'}
                    or row['source'] != 'core-tool-policy' or row['category'] != 'tool_policy_denied'
                    or row['severity'] != 'warning' or not isinstance(row['event_id'], str)
                    or not re.fullmatch(r'tool-denial-[0-9a-f]{64}', row['event_id'])
                    or row['event_id'] in seen):
                raise ValueError('invalid event')
            event = SecurityEvent(row['event_id'], row['source'], row['category'], Severity.WARNING,
                                  row['observed_at'], row['subject'])
            if abs((self.now() - _instant(event.observed_at)).total_seconds()) > 300:
                raise ValueError('stale event')
            seen.add(event.event_id)
            events.append(event)
        return payload, events, digest

    def commit(self, payload, digest):
        # Call only AFTER events are durably stored and checkpoint persisted.
        self.sequence, self.previous_digest = payload['sequence'], digest


def signed_envelope(private_key, sequence, events, *, now=None):
    """Create an authenticated bounded feed from trusted Core audit records."""
    if type(sequence) is not int or sequence < 1 or not isinstance(events, list) or len(events) > 64:
        raise ValueError('invalid outgoing batch')
    from .darme import SecurityEvent
    rows = []
    for event in events:
        if not isinstance(event, SecurityEvent) or event.source != 'core-tool-policy' or event.category != 'tool_policy_denied':
            raise ValueError('untrusted outgoing event')
        rows.append(dict(event_id=event.event_id, source=event.source, category=event.category,
                         severity=event.severity.value, observed_at=event.observed_at, subject=event.subject))
    payload = dict(schema=SCHEMA, sequence=sequence,
                   generated_at=(now or datetime.now(timezone.utc)).isoformat(), events=rows)
    encoded = canonical(payload)
    result = canonical(dict(payload=payload, signature=base64.b64encode(private_key.sign(encoded)).decode()))
    if len(result) > 65536:
        raise ValueError('oversized outgoing feed')
    return result
