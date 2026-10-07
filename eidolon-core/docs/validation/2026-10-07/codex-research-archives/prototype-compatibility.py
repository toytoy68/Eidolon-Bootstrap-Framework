# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prototype-compatibility.py
# Description : Lecture C-028 des exports G057 sur corpus synthétique isolé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path.cwd()
SRC = str(ROOT / 'src')
HERE = ROOT / 'docs/proposals/2026-10-07-research-retention'
sys.argv = [__file__, SRC]
spec = importlib.util.spec_from_file_location('g057_probes', HERE / 'probes_g057.py')
g057 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g057)
from eidolon_core.research_archive import read_catalog, write_index

with tempfile.TemporaryDirectory(prefix='eidolon-archive-compat-') as directory:
    guard, archive = g057.build(Path(directory))
    for count, operations in ((3, ()), (256, ()), (256, (g057.OPERATION,))):
        g057.rotation.rotate(guard, archive, count=count, operations=operations, guard_src=SRC, clock_ms=1)
    before = {p: p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
    catalog = read_catalog(archive)
    assert catalog['run_count'] == 7 and catalog['archive_count'] == 3
    assert sum(item['queries_with_text'] for item in catalog['files']) == 7
    assert sum(item['linked_missions'] for item in catalog['files']) == 1
    assert all(p.read_bytes() == data for p, data in before.items())
    result = write_index(archive)
    assert result['index_changed'] is True
    assert all(p.read_bytes() == data for p, data in before.items())
    assert 'jean@example.invalid' not in (archive / 'liste.md').read_text()
    assert result['committed_status_known'] is False
    output = {'status': 'PASS', 'actual_g057_exports_verified': 3, 'archived_runs': 7,
              'cleaned_query_bindings_verified': 7, 'linked_mission_count': 1,
              'original_files_unchanged': True, 'index_private': (archive / 'liste.md').stat().st_mode & 0o777 == 0o600,
              'active_rotation_enabled': False}
output['temporary_files_removed'] = not Path(directory).exists()
print(json.dumps(output, indent=2))
