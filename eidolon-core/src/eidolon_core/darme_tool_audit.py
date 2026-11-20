"""Offline policy-denial evidence adapter; no privileged actions or network I/O."""
from datetime import datetime, timezone
import hashlib
import json
from .darme import SecurityEvent, Severity


def denied_tool_event(*, request_id, tool_name, policy_id, parameters):
    """Build bounded evidence from trusted Core dispatch metadata only."""
    for value in (request_id, tool_name, policy_id):
        if not isinstance(value, str) or not value or len(value) > 100 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError('invalid audit identifier')
    encoded = json.dumps(parameters, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    if len(encoded) > 65536:
        raise ValueError('audit parameters too large')
    fingerprint = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
    identity = hashlib.sha256((request_id + '\0' + tool_name + '\0' + policy_id + '\0' + fingerprint).encode()).hexdigest()
    return SecurityEvent('tool-denial-' + identity, 'core-tool-policy', 'tool_policy_denied',
                         Severity.WARNING, datetime.now(timezone.utc).isoformat(),
                         'tool=' + tool_name[:80] + ';args_sha256=' + fingerprint[:24])
