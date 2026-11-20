"""Signed durable receiver acknowledgement, independently verified by Core."""
import base64
import hashlib
from .darme_core_feed import canonical


def sign_receipt(key, sequence, digest):
    if type(sequence) is not int or sequence < 1 or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('invalid receipt fields')
    body = {'schema':'eidolon-darme-core-receipt/1', 'sequence':sequence, 'digest':digest}
    return canonical({'payload':body, 'signature':base64.b64encode(key.sign(canonical(body))).decode()})


def verify_receipt(raw, public_key, sequence, digest):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    import json
    if len(raw) > 2048:
        raise ValueError('oversized receipt')
    envelope = json.loads(raw)
    if not isinstance(envelope, dict) or set(envelope) != {'payload','signature'}:
        raise ValueError('invalid receipt envelope')
    body = envelope['payload']
    if (not isinstance(body, dict) or body != {'schema':'eidolon-darme-core-receipt/1',
                                              'sequence':sequence, 'digest':digest}):
        raise ValueError('receipt binding mismatch')
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            base64.b64decode(envelope['signature'], validate=True), canonical(body))
    except InvalidSignature as exc:
        raise ValueError('invalid receipt signature') from exc
    return True
