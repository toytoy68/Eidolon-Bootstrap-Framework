# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : archive-scaling.py
# Description : Mesure bornée de catalogues synthétiques 10/100/1000 exports
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with PYTHONPATH=src:. from eidolon-core/. No real history or retention."""
from contextlib import closing
from copy import deepcopy
from http.client import HTTPConnection
import hashlib
import json
from pathlib import Path
import resource
import tempfile
import threading
import time

from eidolon_core.contracts import digest, encode
from eidolon_core.http_api import ReadServer
from eidolon_core.research_archive import read_catalog, validate_export
from eidolon_core.store import Store
from tests import test_research_archive

fixture = test_research_archive.ArchiveTests()
fixture.setUp()
try:
    template = fixture.export([fixture.records[0]])
finally:
    fixture.doCleanups()

results = []
with tempfile.TemporaryDirectory(prefix='eidolon-catalog-scaling-') as temporary:
    root = Path(temporary)
    directory = root / 'archives'; directory.mkdir(mode=0o700)
    state = Store(root / 'state')
    token = 'synthetic_catalog_scaling_' + 'x' * 32
    previous = '0' * 64
    total_bytes = 0
    for index in range(1, 1001):
        export = deepcopy(template)
        identity = 'r-' + f'{index:032x}'
        row = export['runs'][0]; row['id'] = identity
        body = json.loads(row['body']); body['id'] = identity
        row['body'] = encode(body)
        for offset, event in enumerate(row['events']):
            event[0] = index * 2 - 1 + offset
            event_body = json.loads(event[2]); event_body['id'] = identity
            event[2] = encode(event_body)
        export.update(chain_index=index, previous_chain_sha256=previous, removed_ids_sha256=digest([identity]))
        name = f'research-archive-{index:06d}.json'
        data = encode(export).encode()
        checked = validate_export(data, name)
        previous = digest(checked['entry'])
        path = directory / name; path.write_bytes(data); path.chmod(0o600)
        total_bytes += len(data)
        if index not in (10, 100, 1000):
            continue
        before = hashlib.sha256(state.path.read_bytes()).hexdigest()
        started = time.monotonic()
        catalog = read_catalog(directory, time_budget_seconds=2)
        catalog_ms = (time.monotonic() - started) * 1000
        assert catalog['archive_count'] == index and catalog['run_count'] == index
        with ReadServer(state.directory, token, port=0, research_archives=directory) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}); thread.start()
            try:
                started = time.monotonic()
                with closing(HTTPConnection('127.0.0.1', server.server_port, timeout=5)) as connection:
                    connection.request('POST', '/v1/research-archives', body='{"limit":100}',
                                       headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                    response = connection.getresponse(); raw = response.read()
                    page = json.loads(raw)
                    assert response.status == 200 and len(page['items']) == min(index, 100)
                    assert page['archive_count'] == index
                http_ms = (time.monotonic() - started) * 1000
            finally:
                server.shutdown(); thread.join(5)
        assert hashlib.sha256(state.path.read_bytes()).hexdigest() == before
        results.append({'archives': index, 'synthetic_runs': index, 'export_bytes': total_bytes,
                        'catalog_ms': round(catalog_ms, 3), 'http_page_ms': round(http_ms, 3),
                        'response_bytes': len(raw), 'page_items': len(page['items']),
                        'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
print(json.dumps({'status': 'PASS', 'synthetic_format_copies_only': True, 'rotation_tested': False,
                  'samples_per_size': 1, 'not_a_latency_guarantee': True, 'results': results,
                  'temporary_files_removed': not root.exists()}, indent=2))
