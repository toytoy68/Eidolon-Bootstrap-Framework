# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : independent-probes.py
# Description : Écriture courte et retrait de partiel, prototype isolé G062
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

SRC = str(Path('src').resolve())
HERE = Path('docs/proposals/2026-10-07-research-retention').resolve()
sys.argv = [__file__, SRC]
spec = importlib.util.spec_from_file_location('g057', HERE / 'probes_g057.py')
g057 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g057)
rotation = g057.rotation
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research_guard import ResearchGuard

class Interrupted(BaseException):
    pass

def interrupted():
    raise Interrupted()

with tempfile.TemporaryDirectory(prefix='eidolon-counter-g062-') as temporary:
    root = Path(temporary)
    guard, archive = g057.build(root / 'short-write')
    before = g057.state(guard)
    write = rotation.os.write
    def short_write(fd, payload):
        return write(fd, payload[:max(1, len(payload) // 2)])
    with patch.object(rotation.os, 'write', side_effect=short_write):
        result = rotation.rotate(guard, archive, count=2, guard_src=SRC, clock_ms=1)
    after = g057.state(guard)
    file = next(archive.glob('*.json'))
    try:
        json.loads(file.read_bytes())
        readable = True
    except ValueError:
        readable = False
    print(json.dumps({'case': 'short_write', 'reported_archived': result['archived'],
                      'removed_active_runs': before['runs'] - after['runs'], 'published_json_readable': readable}))
    guard, archive = g057.build(root / 'partial-before-refusal')
    partial = archive / 'research-archive-unrecognized.partial'
    partial.write_text('Synthetic notes that are not a valid archive')
    partial.chmod(0o600)
    g = ResearchGuard(guard, create=False)
    query = clean_query('synthetic uncertain')
    try:
        g.execute(interrupted, descriptor={'query_sha256': query.cleaned_sha256,
                  'policy_id': 'synthetic', 'providers': ['synthetic']}, cleaned_query=query)
    except Interrupted:
        pass
    result = g057.attempt(rotation.auto_rotate, guard, archive, target=1, guard_src=SRC, clock_ms=1)
    print(json.dumps({'case': 'partial_before_uncertain_refusal', 'result': result,
                      'unrecognized_partial_preserved': partial.exists()}))
