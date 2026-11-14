"""Read-only mission evidence exporter; signed atomic local feed."""
import json
import sqlite3
from pathlib import Path
from .darme import SecurityEvent, Severity
from .darme_core_feed import signed_envelope
from .darme_ssh import atomic


def export_once(database, state_file, feed_file, key):
    state_file, feed_file = Path(state_file), Path(feed_file)
    state = {'cursor': 0, 'sequence': 0}
    if state_file.exists():
        state = json.loads(state_file.read_text())
        if (set(state) != {'cursor', 'sequence'} or any(type(v) is not int or v < 0 for v in state.values())):
            raise ValueError('invalid sender checkpoint')
    # A pending feed must be delivered before a new one can be emitted.
    if feed_file.with_suffix('.pending').exists() and not feed_file.exists():
        raise ValueError('orphaned pending metadata: manual reconciliation required')
    if feed_file.exists():
        raise FileExistsError('pending signed feed requires acknowledgement')
    db = sqlite3.connect('file:' + str(Path(database).resolve()) + '?mode=ro', uri=True)
    try:
        rows = db.execute('SELECT sequence,detail FROM events WHERE kind=? AND sequence>? ORDER BY sequence LIMIT 65',
                          ('DARME_TOOL_POLICY_DENIED', state['cursor'])).fetchall()
    finally:
        db.close()
    if not rows:
        return 0
    if len(rows) > 64:
        rows = rows[:64]
    events = []
    for _, detail in rows:
        record = json.loads(detail)
        if set(record) != {'event_id','source','category','severity','observed_at','subject'}:
            raise ValueError('invalid durable Core evidence')
        events.append(SecurityEvent(record['event_id'], record['source'], record['category'],
                                    Severity(record['severity']), record['observed_at'], record['subject']))
    raw = signed_envelope(key, state['sequence'] + 1, events)
    atomic(feed_file.with_suffix('.pending'), json.dumps({'cursor': rows[-1][0],
        'sequence': state['sequence'] + 1}, sort_keys=True).encode())
    atomic(feed_file, raw, mode=0o640)
    # Sender cursor is advanced only after a receiver acknowledgement in a later phase.
    return len(events)


def acknowledge(feed_file, state_file, pending_file, receipt, receiver_public_key):
    """Advance only on a signed receipt bound to the exact durable feed."""
    from .darme_core_receipt import verify_receipt
    from .darme_core_feed import canonical
    import hashlib
    feed_file, state_file, pending_file = map(Path, (feed_file, state_file, pending_file))
    payload = json.loads(feed_file.read_bytes())['payload']
    pending = json.loads(pending_file.read_text())
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    verify_receipt(receipt, receiver_public_key, payload['sequence'], digest)
    if pending['sequence'] != payload['sequence'] or type(pending['cursor']) is not int:
        raise ValueError('pending cursor mismatch')
    atomic(state_file, json.dumps({'cursor': pending['cursor'], 'sequence': pending['sequence']},
                                  sort_keys=True).encode())
    feed_file.unlink()
    pending_file.unlink()
