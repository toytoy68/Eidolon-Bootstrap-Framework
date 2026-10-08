# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : installed-pauses.py
# Description : Recette isolée du paquet, migration et refus des pauses remplacées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core. Temporary synthetic state only, no network or GPU."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


def main():
    source = Path.cwd().resolve()
    environment = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        environment.pop(name, None)
    environment['PIP_NO_INDEX'] = '1'
    with tempfile.TemporaryDirectory(prefix='core-installed-pauses-') as tmp:
        root = Path(tmp)
        project = root / 'project'; project.mkdir()
        shutil.copy2(source / 'pyproject.toml', project)
        shutil.copytree(source / 'src', project / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))

        def command(args, expected=0):
            result = subprocess.run(list(map(str, args)), cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=90)
            assert result.returncode == expected, (result.returncode, result.stdout[:200], result.stderr[:300])
            return result

        command([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                 '--wheel-dir', root / 'wheels', project])
        wheel, = (root / 'wheels').glob('*.whl')
        venv.EnvBuilder(with_pip=True).create(root / 'venv')
        python, cli = root / 'venv/bin/python', root / 'venv/bin/eidolon-core'
        command([python, '-m', 'pip', 'install', '--no-deps', wheel])
        installed = Path(command([python, '-c', 'import eidolon_core;print(eidolon_core.__file__)']).stdout.strip()).parent
        assert installed.is_relative_to(root / 'venv')
        modules = list((source / 'src/eidolon_core').glob('*.py'))
        assert all(p.read_bytes() == (installed / p.name).read_bytes() for p in modules)

        seed = '''from pathlib import Path
from contextlib import closing
import sqlite3, sys
from eidolon_core.store import Store
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.research_pauses import ResearchPauses, provider_scope
store=Store(sys.argv[1]); runtime=ResearchRuntime(store)
runtime.create_research('synthetic pending')
path=store.directory/'research-fixture/pauses.sqlite3'
ResearchPauses(path,create=False).pause([provider_scope('synthetic-research-provider/1')],reason='ACCESS_DENIED')
with closing(sqlite3.connect(path)) as db, db:
 db.execute('DROP TABLE pause_metadata');db.execute('PRAGMA user_version=1')
with closing(sqlite3.connect(store.path)) as db, db:
 db.execute("DELETE FROM sync_metadata WHERE key='research_fixture_pause_id'")
'''
        state = root / 'state'
        command([python, '-c', seed, state])
        base = [cli, '--state', state, '--profile', 'research-sim']
        diagnostic = json.loads(command([cli, '--state', state, 'research-binding-inspect'], expected=2).stdout)
        assert diagnostic['status'] == 'MIGRATION_REVIEW_REQUIRED'
        before = json.loads(command([*base, 'research-pauses']).stdout)
        assert before['database_id'] is None and before['pauses'][0]['status'] == 'ACTIVE'
        refusal = command([*base, 'research', 'new synthetic', '--create-only'], expected=2)
        assert 'RESEARCH_PAUSES_MIGRATION_REQUIRED' in refusal.stderr
        migration = [*base, 'research-pauses-migrate', '--actor', 'synthetic-operator', '--reason', 'installed review']
        result = json.loads(command(migration).stdout)
        assert result['status'] == 'BOUND' and not result['authorizes_execution'] and not result['pauses_released']
        diagnostic = json.loads(command([cli, '--state', state, 'research-binding-inspect']).stdout)
        assert diagnostic['status'] == 'BOUND' and not diagnostic['authorizes_execution']
        after = json.loads(command([*base, 'research-pauses']).stdout)
        assert before['pauses'] == after['pauses'] and before['audit_events'] == after['audit_events']
        snapshot = {p.name: p.read_bytes() for p in state.rglob('*.sqlite3')}
        assert json.loads(command(migration).stdout) == result
        assert {p.name: p.read_bytes() for p in state.rglob('*.sqlite3')} == snapshot
        command([*base, 'research', 'synthetic inspected', '--create-only'])
        human = command([cli, '--state', state, '--profile', 'research-sim', '--format', 'human',
                         'research-pauses-migrate', '--actor', 'op', '--reason', 'review']).stdout
        assert 'Eidolon Core Technologies' in human
        replace = '''from pathlib import Path
import sys
from eidolon_core.research_pauses import ResearchPauses
path=Path(sys.argv[1])/'research-fixture/pauses.sqlite3'
path.unlink(); ResearchPauses(path)
'''
        command([python, '-c', replace, state])
        rejected = command([*base, 'research', 'not sent', '--create-only'], expected=2)
        assert 'RESEARCH_PAUSES_CHANGED' in rejected.stderr
        diagnostic = json.loads(command([cli, '--state', state, 'research-binding-inspect'], expected=2).stdout)
        assert diagnostic['status'] == 'IDENTITY_MISMATCH'
        rejected_migration = command(migration, expected=2)
        assert 'RESEARCH_PAUSES_CHANGED' in rejected_migration.stderr
        beta = json.loads(command([python, '-m', 'eidolon_core.beta_check', '--web-root',
                                   source / 'desktop/connected', '--profile', 'research-archives']).stdout)
        assert beta['status'] == 'PASS', beta
        print(json.dumps({'status': 'PASS', 'installed_modules_identical': len(modules),
                          'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                          'legacy_refused_before_migration': True, 'pause_and_audit_preserved': True,
                          'migration_idempotent': True, 'replacement_and_readoption_refused': True,
                          'beta': beta, 'synthetic_only': True, 'hardware_qualified': False}, indent=2))


if __name__ == '__main__':
    main()
