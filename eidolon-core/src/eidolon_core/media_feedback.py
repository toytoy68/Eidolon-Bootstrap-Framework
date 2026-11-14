# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_feedback.py
# Description : Jugements locaux révisables et paires de préférences vérifiables
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Offline experimental ledger; no evaluator, training or network is invoked."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

from .media_agents import MediaError

SCORES = {'fidelity', 'structure', 'composition', 'finish'}
FIELDS = {'asset_id', 'image_sha256', 'prompt', 'config_sha256', 'model_sha256',
          'width', 'height', 'split', 'decision', 'reason', 'reviewer', 'confidence', 'scores'}
IDENTITY = {'asset_id', 'image_sha256', 'prompt', 'config_sha256', 'model_sha256', 'width', 'height', 'split'}

def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()

def validate(record):
    if type(record) is not dict or set(record) != FIELDS:
        raise MediaError('INVALID_FEEDBACK_FIELDS')
    if not isinstance(record['asset_id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', record['asset_id']):
        raise MediaError('INVALID_ASSET_ID')
    for key in ('image_sha256', 'config_sha256', 'model_sha256'):
        if not isinstance(record[key], str) or not re.fullmatch('[0-9a-f]{64}', record[key]):
            raise MediaError('INVALID_FEEDBACK_HASH')
    for key in ('prompt', 'reason'):
        if not isinstance(record[key], str) or not record[key].strip() or len(record[key].encode()) > 4000:
            raise MediaError('INVALID_FEEDBACK_TEXT')
    for key in ('width', 'height'):
        if type(record[key]) is not int or not 256 <= record[key] <= 2048:
            raise MediaError('INVALID_FEEDBACK_GEOMETRY')
    if record['split'] not in ('train', 'holdout') or record['decision'] not in ('ACCEPT', 'REJECT', 'UNCERTAIN'):
        raise MediaError('INVALID_FEEDBACK_DECISION')
    if record['reviewer'] not in ('gpt', 'user') or record['confidence'] not in ('high', 'medium', 'low'):
        raise MediaError('INVALID_REVIEWER')
    scores = record['scores']
    if type(scores) is not dict or set(scores) != SCORES or any(type(v) is not int or not 0 <= v <= 4 for v in scores.values()):
        raise MediaError('INVALID_FEEDBACK_SCORES')
    if record['decision'] == 'ACCEPT' and min(scores.values()) < 3:
        raise MediaError('ACCEPTANCE_CRITERIA_NOT_MET')
    return record

def pair_records(records):
    """Only high-confidence, same-prompt/configuration pairs; no all-bad winner."""
    groups = {}; seen_hashes = {}; prompt_splits = {}
    for raw in records:
        r = validate(raw)
        # A prompt and an image cannot leak between learning and confirmation.
        ph = hashlib.sha256(r['prompt'].encode()).hexdigest()
        for table, key in ((prompt_splits, ph), (seen_hashes, r['image_sha256'])):
            if key in table and table[key] != r['split']:
                raise MediaError('TRAIN_HOLDOUT_LEAKAGE')
            table[key] = r['split']
        if r['split'] != 'train' or r['confidence'] != 'high' or r['decision'] == 'UNCERTAIN':
            continue
        group = (r['prompt'], r['config_sha256'], r['model_sha256'], r['width'], r['height'])
        groups.setdefault(group, {'ACCEPT': [], 'REJECT': []})[r['decision']].append(r)
    pairs = []; used = set()
    for group in sorted(groups):
        rows = groups[group]
        chosen = sorted(rows['ACCEPT'], key=lambda r: r['asset_id'])
        rejected = sorted(rows['REJECT'], key=lambda r: r['asset_id'])
        for winner, loser in zip(chosen, rejected):
            hashes = {winner['image_sha256'], loser['image_sha256']}
            if len(hashes) != 2 or hashes & used:
                continue
            used |= hashes
            pairs.append({'chosen': winner['asset_id'], 'rejected': loser['asset_id'],
                          'prompt': group[0], 'config_sha256': group[1], 'model_sha256': group[2],
                          'width': group[3], 'height': group[4],
                          'chosen_sha256': winner['image_sha256'], 'rejected_sha256': loser['image_sha256']})
    return pairs

class FeedbackLedger:
    """Append-only revision chain. Hashes detect corruption, not malicious admins."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise MediaError('PRIVATE_ROOT_REQUIRED')
        self.path = self.root/'reviews.jsonl'

    def read(self):
        if not self.path.exists() and not self.path.is_symlink(): return []
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            events = []; previous = '0'*64
            for line in stream:
                event = json.loads(line)
                unsigned = {k:v for k,v in event.items() if k != 'hash'}
                if event['revision'] != len(events)+1 or event['previous'] != previous or checksum(unsigned) != event['hash']:
                    raise MediaError('FEEDBACK_CHAIN_CORRUPT')
                validate(event['record']); events.append(event); previous = event['hash']
        return events

    def append(self, record, *, expected_revision):
        validate(record)
        fd = os.open(self.root/'reviews.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            events = self.read()
            if type(expected_revision) is not int or expected_revision != len(events):
                raise MediaError('FEEDBACK_REVISION_CONFLICT')
            old = next((e['record'] for e in reversed(events) if e['record']['asset_id'] == record['asset_id']), None)
            if old:
                if any(old[k] != record[k] for k in IDENTITY): raise MediaError('ASSET_IDENTITY_CHANGED')
                if old['reviewer'] == 'user' and record['reviewer'] != 'user':
                    raise MediaError('USER_REVIEW_TAKES_PRECEDENCE')
            event = {'revision': len(events)+1, 'previous': events[-1]['hash'] if events else '0'*64,
                     'time': time.time(), 'record': record}
            event['hash'] = checksum(event)
            out = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(out, 'w') as stream:
                stream.write(json.dumps(event, allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
            return event
        finally: os.close(fd)

    def snapshot(self):
        events = self.read(); latest = {}
        for event in events: latest[event['record']['asset_id']] = event['record']
        records = list(latest.values())
        return {'revision': len(events), 'ledger_hash': events[-1]['hash'] if events else '0'*64,
                'records': records, 'pairs': pair_records(records)}

def verify_pair_files(pair, assets):
    """Recheck bytes immediately before using the frozen dataset for training."""
    assets = Path(assets).resolve()
    paths = []
    for role in ('chosen', 'rejected'):
        asset = pair[role]
        if not isinstance(asset, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', asset):
            raise MediaError('INVALID_ASSET_ID')
        path = assets/(asset+'.png')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != pair[role+'_sha256']:
                raise MediaError('FEEDBACK_IMAGE_CHANGED')
        paths.append(path)
    return paths
