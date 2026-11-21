"""Offline durable signed feed receiver. No socket or privileged operations."""
import json
from pathlib import Path
from .darme_core_feed import CoreFeedVerifier
from .darme_ssh import atomic, read_bounded


class CoreFeedReceiver:
    def __init__(self, public_key, checkpoint, journal, *, now=None):
        self.checkpoint = Path(checkpoint)
        self.journal = journal
        state = {'sequence': 0, 'digest': None}
        if self.checkpoint.exists():
            state = json.loads(read_bounded(self.checkpoint, 2048))
            if (not isinstance(state, dict) or set(state) != {'sequence', 'digest'}
                    or type(state['sequence']) is not int or state['sequence'] < 1
                    or not isinstance(state['digest'], str) or len(state['digest']) != 64):
                raise ValueError('invalid Core receiver checkpoint')
        self.verifier = CoreFeedVerifier(public_key, sequence=state['sequence'],
                                         previous_digest=state['digest'], now=now)

    def accept(self, raw):
        payload, events, digest = self.verifier.verify(raw)
        if payload['sequence'] == self.verifier.sequence:
            return 0  # Exact signed retransmission, already committed.
        for event in events:
            self.journal.record(event)
        # Persist checkpoint only after all events are durable. Replay is idempotent.
        atomic(self.checkpoint, json.dumps({'sequence': payload['sequence'], 'digest': digest},
                                           sort_keys=True).encode())
        self.verifier.commit(payload, digest)
        return len(events)
