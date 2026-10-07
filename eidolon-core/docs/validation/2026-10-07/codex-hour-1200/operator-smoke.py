# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : operator-smoke.py
# Description : Parcours documenté sur six missions synthétiques jetables
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    env = dict(os.environ, PYTHONPATH=str(Path('src').resolve()))
    with tempfile.TemporaryDirectory(prefix='eidolon-operator-') as directory:
        root = Path(directory)
        fixture = root / 'fixture'
        def command(*args):
            result = subprocess.run([sys.executable, '-m', *args], env=env,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, 'synthetic operator command failed'
            return json.loads(result.stdout)
        assert command('eidolon_core.beta_fixture', '--output', str(fixture))['status'] == 'READY'
        manifest = json.loads((fixture / 'manifest.json').read_text())
        state = fixture / 'state'
        before = {p.relative_to(state): p.read_bytes() for p in state.rglob('*') if p.is_file()}
        page = command('eidolon_core', '--state', str(state), 'client-missions')
        assert len(page['items']) == 6 and page['has_more'] is False
        observed = []
        for scenario in manifest['scenarios']:
            report = command('eidolon_core', '--state', str(state), 'runtime-inspect', scenario['mission_id'])
            assert report['status'] == scenario['expected_status']
            assert report['cancel_requested'] == scenario['cancel_requested']
            assert report['authorizes_execution'] is False and report['changed_during_sampling'] is False
            observed.append({'role': scenario['role'], 'status': report['status'], 'hints': report['hints']})
        after = {p.relative_to(state): p.read_bytes() for p in state.rglob('*') if p.is_file()}
        assert after == before
        review = root / 'review'
        prepared = command('eidolon_core', 'recovery-prepare', '--source', str(state / 'missions.sqlite3'),
                           '--destination', str(review), '--actor', 'synthetic operator', '--reason', 'documented walkthrough')
        assert prepared['counts']['missions'] == 6 and prepared['execution_authority'] is False
        historical = command('eidolon_core', '--state', str(review), 'recovery-inspect')
        assert historical['historical_only'] is True and historical['counts']['missions'] == 6
        assert {p.relative_to(state): p.read_bytes() for p in state.rglob('*') if p.is_file()} == before
        output = {'status': 'PASS', 'scenarios': observed, 'consultations_preserve_all_source_files': True,
                  'review_missions': 6, 'historical_only': True, 'source_preserved_by_copy': True}
    output['temporary_files_removed'] = not root.exists()
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
