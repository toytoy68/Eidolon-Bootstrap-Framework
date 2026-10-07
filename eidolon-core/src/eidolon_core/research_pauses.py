# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_pauses.py
# Description : Suspensions Web locales persistantes et levée explicite tracée
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Optional local gate, not authentication or a network sandbox.

Committed pauses never expire automatically. Release only makes a later call
eligible for the normal policy checks; it never makes the call itself.
"""
from contextlib import contextmanager
import ipaddress
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from .contracts import ContractError, digest, encode

PROTOCOL = 'eidolon-research-pauses/1'
MAX_RECORDS = 256  # ACTIVE scopes only; released records retain revision/history.
MAX_INTEGER = 2**53 - 1
REASONS = {'RATE_LIMITED', 'RETRY_WAIT', 'ACCESS_DENIED', 'CHALLENGE',
           'CHALLENGE_SUSPECTED', 'LOGIN_SUSPECTED', 'PAYWALL_SUSPECTED'}


class PauseStorageError(ContractError):
    """Fatal to the research operation, never interpreted as an empty gate."""


class PauseCapacityError(PauseStorageError):
    """Known capacity refusal; a read-only preflight has no uncertain commit."""


def provider_scope(identity):
    return _scope({'kind': 'provider', 'provider_id': identity})


def origin_scope(host, port):
    return _scope({'kind': 'origin', 'host': host, 'port': port})


def _scope(value):
    if type(value) is not dict:
        raise ContractError('INVALID_PAUSE_SCOPE')
    if value.get('kind') == 'provider' and set(value) == {'kind', 'provider_id'}:
        identity = value['provider_id']
        if type(identity) is str and re.fullmatch(r'[A-Za-z0-9._/-]{1,100}', identity):
            return dict(value)
    if value.get('kind') == 'origin' and set(value) == {'kind', 'host', 'port'}:
        host, port = value['host'], value['port']
        if type(host) is str and host == host.lower() and 1 <= len(host) <= 253 and type(port) is int and 1 <= port <= 65535:
            try:
                ipaddress.ip_address(host)
                valid = True
            except ValueError:
                valid = re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) is not None
            if valid:
                return dict(value)
    raise ContractError('INVALID_PAUSE_SCOPE')


def _operator(value, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ContractError('INVALID_PAUSE_REVIEW')
    encode(value)  # UTF-8/finite JSON contract


class ResearchPauses:
    def __init__(self, path, *, clock=time.time, create=True):
        if not callable(clock):
            raise ContractError("INVALID_PAUSE_CLOCK")
        self.path = Path(path).resolve()
        self.clock = clock
        if type(create) is not bool:
            raise ContractError("INVALID_PAUSE_INITIALIZATION")
        if not create:
            with self._connection() as db:
                db.execute('PRAGMA query_only=ON')
                version = db.execute('PRAGMA user_version').fetchone()[0]
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                if version != 1 or tables != {'pauses', 'pause_events'}:
                    raise PauseStorageError('UNSUPPORTED_PAUSE_DATABASE')
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection(create=True) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if version not in (0, 1) or (version == 0 and tables):
                raise PauseStorageError('UNSUPPORTED_PAUSE_DATABASE')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pauses (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pause_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, pause_id TEXT NOT NULL,
                    at_ms INTEGER NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def _connection(self, *, create=False):
        db = None
        try:
            db = (sqlite3.connect(self.path, timeout=5) if create else
                  sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5))
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ContractError):
                raise
            raise PauseStorageError('PAUSE_STORAGE_UNAVAILABLE') from exc
        finally:
            if db is not None:
                db.close()

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= (MAX_INTEGER - 86_400_000) / 1000:
            raise PauseStorageError('INVALID_PAUSE_CLOCK')
        return math.ceil(value * 1000)

    def _decode(self, identity, raw):
        try:
            row = json.loads(raw)
            if (type(row) is not dict or row.get('id') != identity
                    or identity != 'p-' + digest(_scope(row['scope']))
                    or row['status'] not in {'ACTIVE', 'RELEASED'} or row['reason'] not in REASONS
                    or type(row['revision']) is not int or not 1 <= row['revision'] < MAX_INTEGER
                    or type(row['observed_at_ms']) is not int or not 0 <= row['observed_at_ms'] <= MAX_INTEGER
                    or type(row['review_required']) is not bool
                    or (row['not_before_ms'] is not None and (type(row['not_before_ms']) is not int
                        or not row['observed_at_ms'] <= row['not_before_ms'] <= MAX_INTEGER))):
                raise PauseStorageError('INVALID_PAUSE_RECORD')
            return row
        except PauseStorageError:
            raise
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise PauseStorageError('INVALID_PAUSE_RECORD') from exc

    def active(self, scope):
        identity = 'p-' + digest(_scope(scope))
        with self._connection() as db:
            row = db.execute('SELECT body FROM pauses WHERE id=?', (identity,)).fetchone()
            value = self._decode(identity, row[0]) if row else None
            return value if value and value['status'] == 'ACTIVE' else None

    def inspect(self):
        with self._connection() as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            rows = [self._decode(identity, body) for identity, body in db.execute('SELECT id,body FROM pauses ORDER BY id')]
            count = db.execute('SELECT count(*) FROM pause_events').fetchone()[0]
            return {'protocol': PROTOCOL, 'authorizes_execution': False, 'automatic_release': False,
                    'pauses': rows, 'audit_events': count}

    def _active_count(self, db):
        # Validate rather than treating corrupt/unknown states as free capacity.
        # Stream historical rows; retention/indexing is a separate future lot.
        return sum(self._decode(identity, body)['status'] == 'ACTIVE'
                   for identity, body in db.execute('SELECT id,body FROM pauses'))

    def check_capacity(self, scopes):
        """Read-only preflight, not a reservation across concurrent requests."""
        if type(scopes) not in (list, tuple) or not 1 <= len(scopes) <= 2:
            raise ContractError('INVALID_PAUSE_SCOPE')
        identities = {'p-' + digest(_scope(scope)) for scope in scopes}
        with self._connection() as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            total = self._active_count(db)
            missing = 0
            for identity in identities:
                row = db.execute('SELECT body FROM pauses WHERE id=?', (identity,)).fetchone()
                if row is None or self._decode(identity, row[0])['status'] == 'RELEASED':
                    missing += 1
            if total + missing > MAX_RECORDS:
                raise PauseCapacityError('PAUSE_CAPACITY_REACHED: review and release active pauses')

    def pause(self, scopes, *, reason, retry_after=None, review=False):
        if (type(scopes) not in (list, tuple) or not 1 <= len(scopes) <= 2 or type(reason) is not str or reason not in REASONS
                or type(review) is not bool or (retry_after is not None and
                    (type(retry_after) is not int or not 0 <= retry_after <= 86400))):
            raise ContractError('INVALID_PAUSE_OBSERVATION')
        identities = {'p-' + digest(_scope(s)): _scope(s) for s in scopes}
        stamp = self._now()
        delay = retry_after if retry_after is not None else 60 if reason == 'RATE_LIMITED' else None
        deadline = stamp + delay * 1000 if delay is not None else None
        result = []
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            total = self._active_count(db)
            for identity, scope in identities.items():
                existing = db.execute('SELECT body FROM pauses WHERE id=?', (identity,)).fetchone()
                old = self._decode(identity, existing[0]) if existing else None
                needs_slot = old is None or old['status'] == 'RELEASED'
                if needs_slot and total >= MAX_RECORDS:
                    raise PauseCapacityError('PAUSE_CAPACITY_REACHED: review and release active pauses')
                if old and stamp < old['observed_at_ms']:
                    raise PauseStorageError('PAUSE_CLOCK_REGRESSION')
                revision = old['revision'] + 1 if old else 1
                if revision >= MAX_INTEGER:
                    raise PauseStorageError('PAUSE_REVISION_EXHAUSTED')
                active_old = old if old and old['status'] == 'ACTIVE' else None
                previous_deadline = active_old['not_before_ms'] if active_old else None
                until = max(v for v in (deadline, previous_deadline, stamp) if v is not None) if deadline is not None or previous_deadline is not None else None
                record = {'id': identity, 'scope': scope, 'revision': revision, 'status': 'ACTIVE',
                          'reason': reason, 'observed_at_ms': stamp, 'not_before_ms': until,
                          'review_required': review or bool(active_old and active_old['review_required'])}
                db.execute('INSERT OR REPLACE INTO pauses (id,body) VALUES (?,?)', (identity, encode(record)))
                db.execute('INSERT INTO pause_events (pause_id,at_ms,kind,body) VALUES (?,?,?,?)',
                           (identity, stamp, 'OBSERVED', encode(record)))
                total += needs_slot
                result.append(record)
        return result

    def release(self, identity, *, expected_revision, actor, reason):
        if (type(identity) is not str or re.fullmatch(r'p-[0-9a-f]{64}', identity) is None
                or type(expected_revision) is not int or not 1 <= expected_revision < MAX_INTEGER - 1):
            raise ContractError('INVALID_PAUSE_REVIEW')
        _operator(actor, 200); _operator(reason, 4000)
        stamp = self._now()
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM pauses WHERE id=?', (identity,)).fetchone()
            if row is None:
                raise ContractError('PAUSE_NOT_FOUND')
            record = self._decode(identity, row[0])
            if record['revision'] != expected_revision:
                raise ContractError('STALE_PAUSE: inspect the new observation before release')
            if record['status'] != 'ACTIVE':
                raise ContractError('PAUSE_NOT_ACTIVE')
            if stamp < record['observed_at_ms']:
                raise ContractError('PAUSE_CLOCK_REGRESSION')
            if record['not_before_ms'] is not None and stamp < record['not_before_ms']:
                raise ContractError('RETRY_DELAY_PENDING')
            record.update(status='RELEASED', revision=record['revision'] + 1, released_at_ms=stamp)
            db.execute('UPDATE pauses SET body=? WHERE id=?', (encode(record), identity))
            db.execute('INSERT INTO pause_events (pause_id,at_ms,kind,body) VALUES (?,?,?,?)',
                       (identity, stamp, 'RELEASED', encode({'revision': record['revision'], 'actor': actor, 'reason': reason})))
        return {'protocol': PROTOCOL, 'status': 'RELEASED', 'pause_id': identity,
                'revision': record['revision'], 'authorizes_execution': False, 'request_sent': False}
