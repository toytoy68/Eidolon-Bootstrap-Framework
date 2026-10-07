# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_archive.py
# Description : Vérification locale des exports et index privé des recherches
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Bounded archive catalog; no journal mutation, rotation, replay or HTTP route.

File hashes and a self-contained chain establish consistency, not authenticity
or an archive's committed status in the live guard. liste.md is a generated view.
"""
from contextlib import contextmanager
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
from types import SimpleNamespace
import uuid

from .contracts import ContractError, digest, encode
from .presentation import header, message
from .query_history import validate_payload
from .research_guard import MAX_INTEGER, ResearchGuard

PROTOCOL = 'eidolon-research-archive-catalog/1'
EXPORT_PROTOCOL = 'eidolon-research-archive/1'
MAX_ARCHIVES = 1000
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 2048
MAX_INDEX_BYTES = 1024 * 1024
NAME = re.compile(r'research-archive-([0-9]{6})\.json')
SHA = re.compile(r'[0-9a-f]{64}')
INDEX_HEADER = '<!-- eidolon-research-archive-index/1; generated; private -->\n'


class ArchiveError(ContractError):
    pass


def _json(raw):
    def unique(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise ValueError()
            value[key] = child
        return value
    def nonfinite(_):
        raise ValueError()
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def _integer(value, minimum=0, maximum=MAX_INTEGER):
    return type(value) is int and minimum <= value <= maximum


def validate_export(data, filename):
    """Validate every retained record and binding, returning private internal data."""
    try:
        match = NAME.fullmatch(filename) if type(filename) is str else None
        if (type(data) is not bytes or len(data) > MAX_ARCHIVE_BYTES or match is None):
            raise ValueError()
        meta = _json(data.decode('utf-8'))
        fields = {'protocol', 'guard_id', 'chain_index', 'previous_chain_sha256', 'created_at_ms',
                  'runs', 'removed_ids_sha256', 'authorizes_execution'}
        if (type(meta) is not dict or not fields <= set(meta) or not set(meta) <= fields | {'released_operations'}
                or meta['protocol'] != EXPORT_PROTOCOL
                or type(meta['guard_id']) is not str or re.fullmatch(r'g-[0-9a-f]{32}', meta['guard_id']) is None
                or not _integer(meta['chain_index'], 1, 999999) or meta['chain_index'] != int(match[1])
                or not _integer(meta['created_at_ms']) or meta['authorizes_execution'] is not False
                or type(meta['previous_chain_sha256']) is not str or not SHA.fullmatch(meta['previous_chain_sha256'])
                or type(meta['removed_ids_sha256']) is not str or not SHA.fullmatch(meta['removed_ids_sha256'])
                or type(meta['runs']) is not list or not 1 <= len(meta['runs']) <= 256):
            raise ValueError()
        validator = SimpleNamespace(guard_id=meta['guard_id'])
        ids, sequences, records, queries = set(), set(), [], {}
        previous_order = None
        for row in meta['runs']:
            if (type(row) is not dict or set(row) != {'id', 'body', 'events', 'cleaned_query'}
                    or type(row['id']) is not str or row['id'] in ids or type(row['body']) is not str):
                raise ValueError()
            _json(row['body'].encode('utf-8'))  # strict nested JSON, not only the outer envelope
            record = ResearchGuard._decode(validator, row['id'], row['body'])
            if record['state'] not in {'COMPLETED', 'RESOLVED_UNKNOWN'}:
                raise ValueError()
            order = (record['started_at_ms'], record['id'])
            if previous_order is not None and order <= previous_order:
                raise ValueError()
            previous_order = order
            events = row['events']
            if type(events) is not list or len(events) != 2:
                raise ValueError()
            prior_sequence = 0
            decoded = []
            for event in events:
                if (type(event) is not list or len(event) != 3 or not _integer(event[0], 1)
                        or event[0] <= prior_sequence or event[0] in sequences or type(event[2]) is not str):
                    raise ValueError()
                _json(event[2].encode('utf-8'))
                value = ResearchGuard._decode(validator, row['id'], event[2])
                if event[1] != value['state']:
                    raise ValueError()
                prior_sequence = event[0]
                sequences.add(event[0])
                decoded.append(value)
            if (decoded[0]['state'] != 'INTENT' or events[-1][2] != row['body']
                    or any(decoded[0][key] != record[key] for key in ('guard_id', 'descriptor', 'started_at_ms'))):
                raise ValueError()
            bound = record['descriptor'].get('query_history_sha256')
            if bound is None:
                if row['cleaned_query'] is not None:
                    raise ValueError()
            else:
                if type(row['cleaned_query']) is not str or len(row['cleaned_query']) > 16000:
                    raise ValueError()
                payload = validate_payload(_json(row['cleaned_query'].encode('utf-8')))
                if (digest(payload) != bound or payload['cleanup']['cleaned_sha256'] != record['descriptor']['query_sha256']):
                    raise ValueError()
                queries[record['id']] = payload
            ids.add(row['id'])
            records.append(record)
        if 'released_operations' in meta:
            released = meta['released_operations']
            linked = sorted({r['descriptor']['operation_id'] for r in records if 'operation_id' in r['descriptor']})
            if (type(released) is not list or len(released) > 256
                    or any(type(value) is not str or re.fullmatch(r'm-[0-9a-f]{32}', value) is None for value in released)
                    or released != linked):
                raise ValueError()
        if digest([r['id'] for r in records]) != meta['removed_ids_sha256']:
            raise ValueError()
        file_sha = hashlib.sha256(data).hexdigest()
        entry = {'index': meta['chain_index'], 'file': filename, 'export_sha256': file_sha,
                 'previous_chain_sha256': meta['previous_chain_sha256'],
                 'removed_ids_sha256': meta['removed_ids_sha256'], 'count': len(records)}
        return {'meta': meta, 'records': records, 'queries': queries, 'entry': entry,
                'summary': {'file': filename, 'index': meta['chain_index'], 'sha256': file_sha,
                            'created_at_ms': meta['created_at_ms'], 'count': len(records),
                            'queries_with_text': len(queries), 'legacy_runs_without_text': len(records) - len(queries),
                            'linked_missions': sum('operation_id' in r['descriptor'] for r in records)}}
    except (ContractError, ValueError, TypeError, KeyError, IndexError, UnicodeError, RecursionError):
        raise ArchiveError('INVALID_RESEARCH_ARCHIVE') from None


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _private(info, *, directory=False):
    return ((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            and info.st_uid == os.getuid() and not info.st_mode & 0o077)


@contextmanager
def _directory(path):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not _private(os.fstat(fd), directory=True):
            raise ArchiveError('ARCHIVE_DIRECTORY_NOT_PRIVATE')
        yield fd
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    finally:
        if fd is not None:
            os.close(fd)


def _read(fd, name, maximum, checkpoint=lambda: None):
    handle = None
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        initial = os.fstat(handle)
        if not _private(initial):
            raise ArchiveError('ARCHIVE_FILE_NOT_PRIVATE')
        if initial.st_size > maximum:
            raise ArchiveError('ARCHIVE_SIZE_LIMIT')
        chunks, size = [], 0
        while True:
            checkpoint()
            block = os.read(handle, min(65536, maximum + 1 - size))
            if not block:
                break
            chunks.append(block)
            size += len(block)
            if size > maximum:
                raise ArchiveError('ARCHIVE_SIZE_LIMIT')
        if (_signature(initial) != _signature(os.fstat(handle))
                or _signature(initial) != _signature(os.stat(name, dir_fd=fd, follow_symlinks=False))):
            raise ArchiveError('ARCHIVE_CHANGED_DURING_READ')
        return b''.join(chunks), _signature(initial)
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
    finally:
        if handle is not None:
            os.close(handle)


def _names(fd):
    names = []
    count = 0
    with os.scandir(fd) as entries:
        for entry in entries:
            count += 1
            if count > MAX_DIRECTORY_ENTRIES:
                raise ArchiveError('ARCHIVE_COUNT_LIMIT')
            if entry.name.endswith('.partial'):
                raise ArchiveError('PARTIAL_EXPORT_PRESENT')
            if entry.name.startswith('research-archive-'):
                if not NAME.fullmatch(entry.name):
                    raise ArchiveError('INVALID_ARCHIVE_FILENAME')
                names.append(entry.name)
                if len(names) > MAX_ARCHIVES:
                    raise ArchiveError('ARCHIVE_COUNT_LIMIT')
    return sorted(names)


def _catalog(fd, checkpoint=lambda: None):
    checkpoint()
    names = _names(fd)
    previous, guard_id, total = '0' * 64, None, 0
    seen, event_sequences, signatures, files = set(), set(), {}, []
    for index, name in enumerate(names, 1):
        checkpoint()
        data, signature = _read(fd, name, min(MAX_ARCHIVE_BYTES, MAX_TOTAL_BYTES - total), checkpoint)
        total += len(data)
        archive = validate_export(data, name)
        checkpoint()
        meta = archive['meta']
        if (meta['chain_index'] != index or meta['previous_chain_sha256'] != previous
                or guard_id is not None and meta['guard_id'] != guard_id):
            raise ArchiveError('ARCHIVE_CHAIN_BROKEN')
        for record in archive['records']:
            if record['id'] in seen:
                raise ArchiveError('ARCHIVED_RUN_REPEATED')
            seen.add(record['id'])
        for row in meta['runs']:
            for event in row['events']:
                if event[0] in event_sequences:
                    raise ArchiveError('ARCHIVE_EVENT_REPEATED')
                event_sequences.add(event[0])
        guard_id = meta['guard_id']
        previous = digest(archive['entry'])
        signatures[name] = signature
        files.append(archive['summary'])
    if names != _names(fd) or any(_signature(os.stat(name, dir_fd=fd, follow_symlinks=False)) != sig
                                  for name, sig in signatures.items()):
        raise ArchiveError('ARCHIVE_CHANGED_DURING_READ')
    checkpoint()
    return {'protocol': PROTOCOL, 'guard_id': guard_id, 'files': files,
            'archive_count': len(files), 'run_count': len(seen), 'chain_head': previous,
            'catalog_sha256': digest(files), 'consistency_verified': True,
            'authenticity_verified': False, 'live_journal_checked': False,
            'committed_status_known': False, 'snapshot_only': True,
            'authorizes_execution': False, 'request_sent': False}


def read_catalog(directory, *, time_budget_seconds=None):
    """Optional cooperative deadline; cannot interrupt a syscall or one JSON decode."""
    deadline = None
    if time_budget_seconds is not None:
        if (type(time_budget_seconds) not in (int, float) or not math.isfinite(time_budget_seconds)
                or not 0 < time_budget_seconds <= 60):
            raise ArchiveError('INVALID_ARCHIVE_READ_BUDGET')
        deadline = time.monotonic() + time_budget_seconds

    def checkpoint():
        if deadline is not None and time.monotonic() >= deadline:
            raise ArchiveError('ARCHIVE_READ_BUDGET_EXHAUSTED')

    try:
        with _directory(directory) as fd:
            return _catalog(fd, checkpoint)
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None


def render_index(catalog):
    # Values below are generated constants, validated filenames, integers and hashes.
    # Never interpolate query text, actors, provider labels or arbitrary Markdown.
    lines = [INDEX_HEADER.rstrip(), '# Archives de recherche — Eidolon Core', '',
             'Catalogue privé généré. Cohérence vérifiée, authenticité non établie.',
             'Le journal actif n’est pas consulté : le commit des exports reste inconnu.',
             'Ce fichier ne permet aucune exécution, reprise ou suppression.', '',
             f"Archives : {catalog['archive_count']} ; recherches : {catalog['run_count']}.",
             f"Empreinte du catalogue : {catalog['catalog_sha256']}",
             f"Tête de chaîne décrite : {catalog['chain_head']}", '',
             '| Archive | Recherches | Avec texte nettoyé | Sans texte historique |',
             '| --- | ---: | ---: | ---: |']
    for item in catalog['files']:
        name = item['file']
        lines.append(f"| [{name}]({name}) | {item['count']} | {item['queries_with_text']} | {item['legacy_runs_without_text']} |")
    lines.append('')
    return '\n'.join(lines)


def write_index(directory):
    """Rebuild only the generated private liste.md; no changes to archive/journal."""
    temp, lock = None, None
    try:
        with _directory(directory) as fd:
            try:
                lock = os.open('.archive-index.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
                if not _private(os.fstat(lock)):
                    raise ArchiveError('ARCHIVE_FILE_NOT_PRIVATE')
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ArchiveError('ARCHIVE_INDEX_BUSY') from None
                old = None
                try:
                    os.stat('liste.md', dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    old, old_signature = _read(fd, 'liste.md', MAX_INDEX_BYTES)
                    if not old.startswith(INDEX_HEADER.encode()):
                        raise ArchiveError('ARCHIVE_INDEX_NOT_GENERATED')
                catalog = _catalog(fd)
                content = render_index(catalog).encode('utf-8')
                if len(content) > MAX_INDEX_BYTES:
                    raise ArchiveError('ARCHIVE_SIZE_LIMIT')
                if old != content:
                    candidate = '.liste-' + uuid.uuid4().hex + '.tmp'
                    out = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                    temp = candidate
                    with os.fdopen(out, 'wb') as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    if old is None:
                        os.link(temp, 'liste.md', src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                        os.unlink(temp, dir_fd=fd)
                    else:
                        if _signature(os.stat('liste.md', dir_fd=fd, follow_symlinks=False)) != old_signature:
                            raise ArchiveError('ARCHIVE_INDEX_CHANGED')
                        os.replace(temp, 'liste.md', src_dir_fd=fd, dst_dir_fd=fd)
                    temp = None
                    os.fsync(fd)
                return {**catalog, 'index_file': 'liste.md', 'index_changed': old != content}
            finally:
                if temp is not None:
                    os.unlink(temp, dir_fd=fd)
                if lock is not None:
                    os.close(lock)
    except OSError:
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Vérifier les archives privées et générer leur liste locale.')
    parser.add_argument('--directory', required=True)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    parser.add_argument('command', choices=('inspect', 'index'))
    args = parser.parse_args(argv)
    try:
        result = read_catalog(args.directory) if args.command == 'inspect' else write_index(args.directory)
    except (ArchiveError, ValueError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ArchiveError) else 'INVALID_ARCHIVE_ARGUMENT'
        print(encode({'protocol': PROTOCOL, 'error': code, 'request_sent': False}), file=sys.stderr)
        return 2
    if args.format == 'json':
        print(encode(result))
    else:
        print(header(title='Archives locales de recherche'))
        print(message('INFO', f"{result['archive_count']} archives ; {result['run_count']} recherches."))
        print(message('ATTENTION', 'Cohérence seulement ; commit du journal et authenticité non vérifiés.'))
        if args.command == 'index':
            print(message('INFO', 'liste.md généré ; aucun journal ni export modifié.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
