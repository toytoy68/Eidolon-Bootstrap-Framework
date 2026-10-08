# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : catalog-capacity.py
# Description : Capacité réelle du lecteur sur mille exports synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Temporary catalog derived from one real synthetic export; no runtime activation."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

src = str(Path('eidolon-core/src').resolve())
sys.argv = ['catalog-capacity', src]
sys.path[:0] = [src, str(Path('eidolon-core/docs/proposals/2026-10-07-research-retention').resolve())]
import probes_g057 as fixtures
import rotation
from eidolon_core import research_archive as reader
from eidolon_core.contracts import digest, encode

with tempfile.TemporaryDirectory(prefix='c046-capacity-') as tmp:
    root = Path(tmp)
    guard, seed_dir = fixtures.build(root / 'seed')
    rotation.rotate(guard, seed_dir, count=1, guard_src=src, clock_ms=1)
    seed = json.loads(next(seed_dir.glob('*.json')).read_bytes())
    catalog = root / 'catalog'; catalog.mkdir(mode=0o700)
    previous = '0' * 64
    total = 0
    for index in range(1, reader.MAX_ARCHIVES + 1):
        meta = copy.deepcopy(seed)
        identity = 'r-' + format(index, '032x')
        row = meta['runs'][0]; row['id'] = identity
        value = json.loads(row['body']); value['id'] = identity
        row['body'] = encode(value)
        for position, event in enumerate(row['events']):
            value = json.loads(event[2]); value['id'] = identity
            event[0] = index * 2 - 1 + position
            event[2] = encode(value)
        meta.update(chain_index=index, previous_chain_sha256=previous, created_at_ms=index,
                    removed_ids_sha256=digest([identity]))
        data = encode(meta).encode()
        filename = f'research-archive-{index:06d}.json'
        validated = reader.validate_export(data, filename)
        previous = digest(validated['entry'])
        path = catalog / filename; path.write_bytes(data); path.chmod(0o600)
        total += len(data)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in catalog.iterdir()}
    start = time.monotonic()
    result = reader.read_catalog(catalog, time_budget_seconds=5)
    elapsed = time.monotonic() - start
    assert result['archive_count'] == 1000 and result['run_count'] == 1000
    refused = None
    try:
        rotation._catalog_budget(catalog, candidate=b'candidate')
    except rotation.RotationError as exc:
        refused = str(exc)
    assert refused == 'TOO_MANY_EXPORTS'
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in catalog.iterdir()} == before
    print(json.dumps({'status':'PASS', 'archives':result['archive_count'], 'runs':result['run_count'],
                      'total_bytes':total, 'reader_seconds':elapsed, 'next_publication_refused':refused,
                      'catalog_unchanged':True, 'synthetic_only':True}, indent=2))
