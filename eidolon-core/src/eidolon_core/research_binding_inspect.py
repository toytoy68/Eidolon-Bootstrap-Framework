# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_binding_inspect.py
# Description : Diagnostic sans écriture des identités Store, garde et pauses
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Identity samples only; never authenticate, migrate, release or resume.

The three databases are separate snapshots. Rechecks detect observed changes,
not an adversarial change-and-restore or a coherent rollback with the same IDs.
"""
from contextlib import closing, contextmanager
from pathlib import Path
import re
import sqlite3
import stat
import time

from .contracts import ContractError
from .presentation import header, message
from .readonly_sqlite import require_rollback_journal
from .store import now

PROTOCOL = 'eidolon-research-binding-inspect/1'
PATTERNS = {'store_id': r's-[0-9a-f]{32}', 'research_fixture_guard_id': r'g-[0-9a-f]{32}',
            'research_fixture_pause_id': r'pd-[0-9a-f]{32}'}


def _signature(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ContractError('RESEARCH_BINDING_FILE_TYPE')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _value(db, table, key, pattern, *, optional=False):
    # Table names come from this module, never from an argument or stored data.
    rows = db.execute('SELECT substr(CAST(value AS BLOB),1,129) FROM ' + table +
                      ' WHERE key=? LIMIT 2', (key,)).fetchall()
    if not rows and optional:
        return None
    if len(rows) != 1 or type(rows[0][0]) is not bytes or len(rows[0][0]) > 128:
        raise ContractError('INVALID_RESEARCH_BINDING_IDENTITY')
    try:
        identity = rows[0][0].decode('ascii')
    except UnicodeError:
        raise ContractError('INVALID_RESEARCH_BINDING_IDENTITY') from None
    if re.fullmatch(pattern, identity) is None:
        raise ContractError('INVALID_RESEARCH_BINDING_IDENTITY')
    return identity


@contextmanager
def _read_connection(path):
    require_rollback_journal(path)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        deadline = time.monotonic() + 2
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db


def _store_sample(path):
    before = _signature(path)
    for name in ('BETA-PREPARATION-INCOMPLETE', 'RECOVERY-REVIEW-ONLY', 'review.pending.sqlite3'):
        if (path.parent / name).exists():
            raise ContractError('RESEARCH_BINDING_REVIEW_ONLY')
    with _read_connection(path) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ContractError('UNSUPPORTED_RESEARCH_BINDING_SCHEMA')
        db.execute('SELECT id,body FROM missions LIMIT 0')
        db.execute('SELECT sequence,mission_id,detail FROM events LIMIT 0')
        if db.execute("SELECT 1 FROM sync_metadata WHERE key='recovery_mode'").fetchone():
            raise ContractError('RESEARCH_BINDING_REVIEW_ONLY')
        result = {key: _value(db, 'sync_metadata', key, pattern, optional=key != 'store_id')
                  for key, pattern in PATTERNS.items()}
    if _signature(path) != before:
        raise ContractError('RESEARCH_BINDING_CHANGED_DURING_INSPECTION')
    return result, before


def _component(path, kind):
    try:
        before = _signature(path)
    except FileNotFoundError:
        return {'state': 'MISSING', 'database_id': None}, None
    # mode=ro and query_only: inspection cannot create a SQLite database or DDL.
    with _read_connection(path) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                          "AND name NOT LIKE 'sqlite_%'").fetchmany(5)}
        if kind == 'guard':
            if version != 2 or tables != {'metadata', 'runs', 'run_events', 'cleaned_queries'}:
                raise ContractError('UNSUPPORTED_RESEARCH_BINDING_SCHEMA')
            db.execute('SELECT id,body FROM runs LIMIT 0')
            db.execute('SELECT sequence,run_id,kind,body FROM run_events LIMIT 0')
            db.execute('SELECT run_id,body FROM cleaned_queries LIMIT 0')
            identity = _value(db, 'metadata', 'guard_id', PATTERNS['research_fixture_guard_id'])
        else:
            if (version not in (1, 2) or tables != ({'pauses', 'pause_events'} |
                    ({'pause_metadata'} if version == 2 else set()))):
                raise ContractError('UNSUPPORTED_RESEARCH_BINDING_SCHEMA')
            db.execute('SELECT id,body FROM pauses LIMIT 0')
            db.execute('SELECT sequence,pause_id,at_ms,kind,body FROM pause_events LIMIT 0')
            identity = (None if version == 1 else _value(
                db, 'pause_metadata', 'database_id', PATTERNS['research_fixture_pause_id']))
    if _signature(path) != before:
        raise ContractError('RESEARCH_BINDING_CHANGED_DURING_INSPECTION')
    return {'state': 'LEGACY_NO_ID' if identity is None else 'IDENTITY_OBSERVED',
            'database_id': identity}, before


def inspect_research_binding(directory):
    try:
        directory = Path(directory).resolve(strict=True)
        mission_path = directory / 'missions.sqlite3'
        metadata, store_signature = _store_sample(mission_path)
        paths = {'guard': directory / 'research-fixture/guard/research-runs.sqlite3',
                 'pauses': directory / 'research-fixture/pauses.sqlite3'}
        samples = {kind: _component(path, kind) for kind, path in paths.items()}
        latest, latest_signature = _store_sample(mission_path)
        changed = latest != metadata or latest_signature != store_signature
        for kind, path in paths.items():
            # Re-read identities too: a WAL commit need not change the main file.
            changed |= _component(path, kind) != samples[kind]
        guard, pauses = samples['guard'][0], samples['pauses'][0]
        expected_guard = metadata['research_fixture_guard_id']
        expected_pause = metadata['research_fixture_pause_id']
        status = 'BOUND'
        if changed:
            status = 'CHANGED_DURING_INSPECTION'
        elif guard['state'] == 'MISSING' or pauses['state'] == 'MISSING':
            status = 'MISSING_EVIDENCE'
        elif ((expected_guard is not None and guard['database_id'] != expected_guard)
              or (expected_pause is not None and pauses['database_id'] != expected_pause)):
            status = 'IDENTITY_MISMATCH'
        elif expected_guard is None or expected_pause is None:
            status = 'MIGRATION_REVIEW_REQUIRED'
        return {'protocol': PROTOCOL, 'status': status, 'observed_at': now(),
                'store_id': metadata['store_id'],
                'guard': {**guard, 'expected_id': expected_guard},
                'pauses': {**pauses, 'expected_id': expected_pause},
                'snapshot_only': True, 'snapshots_atomic': False,
                'histories_verified': False, 'rollback_detection_supported': False,
                'authorizes_execution': False, 'request_sent': False, 'state_modified': False}
    except ContractError:
        raise
    except (sqlite3.Error, OSError, ValueError, TypeError):
        raise ContractError('RESEARCH_BINDING_INSPECTION_UNAVAILABLE') from None


def render_binding_inspection(report):
    explanations = {
        'BOUND': 'Identités liées. Examiner les missions et les pauses avant toute reprise.',
        'MIGRATION_REVIEW_REQUIRED': 'Liaison incomplète : examiner l’origine des bases avant une migration explicite.',
        'IDENTITY_MISMATCH': 'Une identité diffère : conserver les preuves et examiner les copies, sans réadoption.',
        'MISSING_EVIDENCE': 'Preuve manquante : conserver l’état et retrouver une copie cohérente.',
        'CHANGED_DURING_INSPECTION': 'État modifié pendant la lecture : refaire une inspection explicite.'}
    text = header(title='Liaison des bases de recherche')
    text += message('INFO', explanations[report['status']])
    for kind, label in (('guard', 'Garde'), ('pauses', 'Pauses')):
        item = report[kind]
        text += message('INFO', f"{label} : {item['state']} ; attendue {item['expected_id'] or 'absente'} ; observée {item['database_id'] or 'absente'}")
    return text + message('ATTENTION', 'Identités seulement, historique non vérifié. Aucune migration, levée ou reprise autorisée par ce diagnostic.')
