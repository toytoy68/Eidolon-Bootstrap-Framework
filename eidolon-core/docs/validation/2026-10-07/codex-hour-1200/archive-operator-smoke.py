# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : archive-operator-smoke.py
# Description : Archive du commit publié et parcours opérateur isolé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def main():
    commit = sys.argv[1]
    source = Path.cwd().resolve()
    script = source / 'docs/validation/2026-10-07/codex-hour-1200/operator-smoke.py'
    def command(args, cwd=source):
        result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, 'archive operator verification failed'
        return json.loads(result.stdout)
    with tempfile.TemporaryDirectory(prefix='eidolon-archive-operator-') as directory:
        root = Path(directory)
        archive = root / 'sources.tar.gz'
        built = command([sys.executable, 'tools/build_beta_bundle.py', '--commit', commit, '--output', archive])
        verified = command([sys.executable, 'tools/build_beta_bundle.py', '--verify', archive])
        assert verified['verified'] is True and verified['commit'] == commit
        with tarfile.open(archive, 'r:gz') as tar:
            tar.extractall(root / 'extracted', filter='data')
        archived_core = root / 'extracted' / built['root'] / 'eidolon-core'
        for doc in ('RUNTIME-INSPECTION.md', 'RECOVERY-REVIEW.md', 'DIAGNOSTIC-WORKFLOW.md'):
            assert (archived_core / 'docs' / doc).is_file()
        modules = list((source / 'src/eidolon_core').glob('*.py'))
        assert all(p.read_bytes() == (archived_core / 'src/eidolon_core' / p.name).read_bytes() for p in modules)
        operator = command([sys.executable, script], cwd=archived_core)
        assert operator['status'] == 'PASS'
        output = {'status': 'PASS', 'commit': commit, 'archive_sha256': built['sha256'],
                  'files_verified': verified['files'], 'modules_match_checkout': len(modules),
                  'all_three_diagnostic_guides_included': True, 'operator': operator,
                  'authenticity_verified': verified['authenticity_verified']}
    output['temporary_files_removed'] = not root.exists()
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
