# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_ssh.py
# Description : Collecteur SSH local reduit, signature et anti-rejeu
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""No raw journal message, address or username leaves the collector."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import time

from .darme import SecurityEvent, Severity, _instant

SCHEMA = 'eidolon-darme-ssh-feed/1'
MAX_FEED = 128 * 1024
MAX_EVENTS = 128
FAILED = re.compile(r'^(?:Failed (?:password|publickey|keyboard-interactive)|Invalid user )|authentication failure')

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

def read_bounded(path, limit=MAX_FEED):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('not a regular feed')
        value = handle.read(limit+1)
        if len(value) > limit:
            raise ValueError('feed too large')
        return value

def atomic(path, value, mode=0o600):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.darme-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def event_from_row(row):
    if (not isinstance(row, dict) or row.get('_SYSTEMD_UNIT') != 'ssh.service'
            or row.get('_COMM') not in ('sshd','sshd-session') or row.get('_UID') != '0'):
        return None
    message = row.get('MESSAGE')
    if not isinstance(message, str) or not FAILED.search(message):
        return None
    cursor, instant = row.get('__CURSOR'), row.get('__REALTIME_TIMESTAMP')
    if not isinstance(cursor, str) or not cursor or len(cursor) > 2048:
        raise ValueError('invalid journal cursor')
    if not isinstance(instant, str) or not instant.isdigit() or len(instant) > 20:
        raise ValueError('invalid journal timestamp')
    observed = datetime.fromtimestamp(int(instant)/1_000_000, timezone.utc).isoformat()
    return {'event_id': hashlib.sha256(cursor.encode()).hexdigest(), 'source':'ssh-auth',
            'category':'ssh_auth_failure', 'severity':'warning', 'observed_at':observed,
            'subject':'SSH authentication failure'}

class FeedVerifier:
    def __init__(self, public_key, checkpoint, *, now=lambda: datetime.now(timezone.utc)):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        self.key = Ed25519PublicKey.from_public_bytes(read_bounded(public_key, 32))
        self.checkpoint, self.now = Path(checkpoint), now
        self.sequence, self.digest = 0, None
        if self.checkpoint.exists():
            state = json.loads(read_bounded(self.checkpoint, 1024))
            if (set(state) != {'sequence','digest'} or type(state['sequence']) is not int
                    or state['sequence'] < 1 or not re.fullmatch('[0-9a-f]{64}',state['digest'])):
                raise ValueError('invalid receiver checkpoint')
            self.sequence, self.digest = state['sequence'], state['digest']

    def verify(self, raw):
        from cryptography.exceptions import InvalidSignature
        if len(raw) > MAX_FEED:
            raise ValueError('feed too large')
        envelope = json.loads(raw)
        if not isinstance(envelope, dict) or set(envelope) != {'payload','signature'}:
            raise ValueError('invalid envelope')
        payload = envelope['payload']
        encoded = canonical(payload)
        try:
            signature = base64.b64decode(envelope['signature'], validate=True)
            self.key.verify(signature, encoded)
        except (InvalidSignature, TypeError, ValueError) as exc:
            raise ValueError('signature refused') from exc
        if (not isinstance(payload, dict) or set(payload) != {'schema','source','sequence','generated_at','healthy','events'}
                or payload['schema'] != SCHEMA or payload['source'] != 'ssh-auth'
                or type(payload['sequence']) is not int or payload['sequence'] < 1
                or type(payload['healthy']) is not bool or not isinstance(payload['events'], list)
                or len(payload['events']) > MAX_EVENTS):
            raise ValueError('invalid signed payload')
        age = (self.now() - _instant(payload['generated_at'])).total_seconds()
        if not -5 <= age <= 60:
            raise ValueError('stale or future feed')
        digest = hashlib.sha256(encoded).hexdigest()
        if payload['sequence'] < self.sequence or (payload['sequence']==self.sequence and digest != self.digest):
            raise ValueError('replay or sequence collision')
        events, identities = [], set()
        for value in payload['events']:
            if not isinstance(value, dict) or set(value) != {'event_id','source','category','severity','observed_at','subject'}:
                raise ValueError('invalid feed event')
            if (value['source'] != 'ssh-auth' or value['category'] != 'ssh_auth_failure'
                    or value['severity'] != 'warning' or value['subject'] != 'SSH authentication failure'
                    or not isinstance(value['event_id'], str) or not re.fullmatch('[0-9a-f]{64}',value['event_id'])):
                raise ValueError('untrusted event semantics')
            event = SecurityEvent(value['event_id'],value['source'],value['category'],Severity(value['severity']),
                                  value['observed_at'],value['subject'])
            if event.event_id in identities:
                raise ValueError('duplicate feed event')
            identities.add(event.event_id)
            events.append(event)
        return payload, events, digest

    def commit(self, payload, digest):
        # Called only after all events are durable; retry after a crash is idempotent.
        atomic(self.checkpoint, canonical({'sequence':payload['sequence'],'digest':digest}))
        self.sequence, self.digest = payload['sequence'], digest

def rows(cursor):
    argv = ['/usr/bin/journalctl','--no-pager','--quiet','-u','ssh.service','-n','513','-o','json',
            '--output-fields=MESSAGE,_COMM,_SYSTEMD_UNIT,_UID']
    argv += ['--after-cursor='+cursor] if cursor else ['-n','1']
    with tempfile.TemporaryFile() as output:
        subprocess.run(argv, stdout=output, stderr=subprocess.DEVNULL, timeout=5, check=True,
                       env={'PATH':'/usr/bin:/bin','LANG':'C'})
        if output.tell() > 2*1024*1024:
            raise ValueError('journal batch too large')
        output.seek(0)
        entries = [json.loads(line) for line in output if line.strip()]
    if len(entries) >= 513:
        raise ValueError('journal backlog exceeds bound')
    return entries

def collect(key_file, state_dir, runtime_dir):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.from_private_bytes(read_bounded(key_file,32))
    state_path = Path(state_dir)/'checkpoint.json'
    state = {'sequence':0,'cursor':None,'events':[],'overflow':False}
    if state_path.exists():
        state = json.loads(read_bounded(state_path))
    if (set(state) != {'sequence','cursor','events','overflow'} or type(state['sequence']) is not int
            or state['sequence'] < 0 or type(state['overflow']) is not bool
            or not isinstance(state['events'],list) or len(state['events'])>MAX_EVENTS
            or (state['cursor'] is not None and (not isinstance(state['cursor'],str) or len(state['cursor'])>2048))):
        raise ValueError('invalid collector checkpoint')
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    while running:
        healthy = False
        try:
            batch = rows(state['cursor'])
            existing = {e['event_id'] for e in state['events']}
            for row in batch:
                event = event_from_row(row)
                if state['cursor'] is not None and event and event['event_id'] not in existing:
                    if len(state['events']) >= MAX_EVENTS:
                        state['overflow'] = True
                    else:
                        state['events'].append(event)
                        existing.add(event['event_id'])
                cursor = row.get('__CURSOR')
                if not isinstance(cursor,str) or not cursor or len(cursor)>2048:
                    raise ValueError('invalid cursor')
                state['cursor'] = cursor
            healthy = state['cursor'] is not None and not state['overflow']
        except (OSError, ValueError, subprocess.SubprocessError):
            healthy = False
        state['sequence'] += 1
        # Persist before publication: a crash cannot reuse a sequence for different data.
        atomic(state_path, canonical(state))
        payload = {'schema':SCHEMA,'source':'ssh-auth','sequence':state['sequence'],
                   'generated_at':datetime.now(timezone.utc).isoformat(),
                   'healthy':healthy,'events':state['events']}
        envelope = {'payload':payload,'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
        atomic(Path(runtime_dir)/'feed.json', canonical(envelope),0o640)
        for _ in range(100):
            if not running:
                break
            time.sleep(.1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--runtime',required=True)
    args = parser.parse_args()
    os.umask(0o077)
    collect(args.key,args.state,args.runtime)

if __name__ == '__main__':
    main()
