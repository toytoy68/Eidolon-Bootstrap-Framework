# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : independent-probes.py
# Description : Contre-sondes G057 isolées, jamais sur un journal utilisateur
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
rotation = g057.rotation

with tempfile.TemporaryDirectory(prefix='eidolon-counter-g057-') as directory:
    root = Path(directory)
    for change in ('cleaned_query_removed', 'wrong_guard_id', 'prior_archive_missing'):
        guard, archive = g057.build(root / change)
        if change == 'prior_archive_missing':
            rotation.rotate(guard, archive, count=1, guard_src=SRC, clock_ms=1)
        code, _ = g057.rotate_sub(guard, archive, 1, 'after_publish')
        assert code == 9
        export = sorted(archive.glob('*.json'))[-1]
        value = json.loads(export.read_bytes())
        if change == 'cleaned_query_removed':
            value['runs'][0]['cleaned_query'] = None
            export.write_bytes(rotation._canon(value))
        elif change == 'wrong_guard_id':
            value['guard_id'] = 'g-' + 'f' * 32
            export.write_bytes(rotation._canon(value))
        else:
            sorted(archive.glob('*.json'))[0].unlink()
        before = g057.state(guard)
        result = g057.attempt(rotation.resume_uncommitted, guard, archive, guard_src=SRC)
        after = g057.state(guard)
        print(json.dumps({'case': change, 'resume_result': result,
                          'removed_active_runs': before['runs'] - after['runs'],
                          'removed_cleaned_queries': before['cleaned_queries'] - after['cleaned_queries']}))
