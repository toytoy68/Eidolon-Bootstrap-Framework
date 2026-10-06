# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : mission_list.py
# Description : Inventaire paginé local, captures cohérentes sans exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Bounded read-only pages. A changing store requires an explicit fresh listing.

No persistent snapshots, transport, authentication or execution permissions.
The generation detects normal Core writes, not arbitrary SQL/history rewrites.
"""
import json
import re

from .client_sync import MAX_SAFE_INTEGER, SyncError, project_mission
from .contracts import digest
from .store import now

PROTOCOL = "eidolon-mission-list/1"
GENERATION_FIELDS = {"sequence", "event_count", "mission_count", "anchor_sha256"}
CURSOR_FIELDS = {"version", "store_id", "generation", "after_id"}


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= MAX_SAFE_INTEGER


def _match(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def validate_cursor(cursor):
    if (type(cursor) is not dict or set(cursor) != CURSOR_FIELDS
            or type(cursor['version']) is not int or cursor['version'] != 1
            or not _match(r's-[0-9a-f]{32}', cursor['store_id'])
            or not _match(r'm-[0-9a-f]{32}', cursor['after_id'])):
        raise SyncError('INVALID_LIST_CURSOR')
    generation = cursor['generation']
    if (type(generation) is not dict or set(generation) != GENERATION_FIELDS
            or any(not _integer(generation[k], 1) for k in ('sequence', 'event_count', 'mission_count'))
            or generation['event_count'] > generation['sequence']
            or generation['mission_count'] > generation['event_count']
            or not _match(r'[0-9a-f]{64}', generation['anchor_sha256'])):
        raise SyncError('INVALID_LIST_CURSOR')


def parse_cursor(raw):
    """Strict bounded JSON for the CLI; duplicates must not select a hidden value."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('non-finite number')

    try:
        if type(raw) is not bytes or len(raw) > 4096:
            raise ValueError('cursor too large or not bytes')
        cursor = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
        validate_cursor(cursor)
        return cursor
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SyncError('INVALID_LIST_CURSOR') from exc


def _safe_projection(value):
    if type(value) is int and not _integer(value):
        raise SyncError('UNSUPPORTED_INTEGER_RANGE')
    if type(value) is dict:
        for child in value.values():
            _safe_projection(child)
    elif type(value) is list:
        for child in value:
            _safe_projection(child)


class MissionList:
    def __init__(self, store):
        self.store = store

    def page(self, *, cursor=None, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SyncError('INVALID_PAGE_LIMIT')
        if cursor is not None:
            validate_cursor(cursor)
        with self.store.connection() as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
            if row is None or not _match(r's-[0-9a-f]{32}', row[0]):
                raise SyncError('INVALID_STORE_ID')
            store_id = row[0]
            head = db.execute('SELECT sequence,mission_id,at,kind,detail FROM events '
                              'ORDER BY sequence DESC LIMIT 1').fetchone()
            event_count = db.execute('SELECT count(*) FROM events').fetchone()[0]
            mission_count = db.execute('SELECT count(*) FROM missions').fetchone()[0]
            generation = {'sequence': head[0] if head else 0, 'event_count': event_count,
                          'mission_count': mission_count, 'anchor_sha256': digest(list(head)) if head else None}
            if any(not _integer(generation[k]) for k in ('sequence', 'event_count', 'mission_count')):
                raise SyncError('UNSUPPORTED_INTEGER_RANGE')
            if mission_count > event_count or event_count > generation['sequence']:
                raise SyncError('HISTORY_MISSING')
            response = {'protocol': PROTOCOL, 'snapshot_only': True, 'authorizes_execution': False,
                        'store_id': store_id, 'status': 'PAGE', 'observed_at': now(),
                        'generation': generation, 'items': [], 'has_more': False, 'next_cursor': None}
            if cursor is not None:
                reason = ('STORE_CHANGED' if cursor['store_id'] != store_id else
                          'STATE_CHANGED' if cursor['generation'] != generation else None)
                if reason:
                    response.update(status='RESET_REQUIRED', reason=reason)
                    return response  # No mixed-generation partial replacement.
                if db.execute('SELECT 1 FROM missions WHERE id=?', (cursor['after_id'],)).fetchone() is None:
                    raise SyncError('INVALID_LIST_CURSOR')
            after = cursor['after_id'] if cursor is not None else ''
            # Fetch IDs first: don't hold 101 potentially large raw mission bodies.
            identities = db.execute('SELECT id FROM missions WHERE id>? ORDER BY id LIMIT ?',
                                    (after, limit + 1)).fetchall()
            for (identity,) in identities[:limit]:
                self.store.check_id(identity)
                revision, cancel, body = db.execute(
                    'SELECT revision,cancel_requested,body FROM missions WHERE id=?', (identity,)).fetchone()
                mission = json.loads(body)
                if mission['id'] != identity:
                    raise SyncError('INVALID_MISSION_IDENTITY')
                mission.update(revision=revision, cancel_requested=bool(cancel))
                sequence = db.execute('SELECT max(sequence) FROM events WHERE mission_id=?',
                                      (identity,)).fetchone()[0]
                if sequence is None:
                    raise SyncError('HISTORY_MISSING')
                projection = project_mission(mission)
                _safe_projection(projection)
                response['items'].append({'as_of_sequence': sequence, 'mission': projection})
            response['has_more'] = len(identities) > limit
            if response['has_more']:
                response['next_cursor'] = {'version': 1, 'store_id': store_id,
                                           'generation': dict(generation), 'after_id': identities[limit - 1][0]}
            return response
