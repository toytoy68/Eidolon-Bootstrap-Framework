# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : source-bundle-smoke.py
# Description : Archive publiée vérifiée et recette depuis son extraction isolée
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core with a full published commit argument; no persistent archive."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

source = Path.cwd()
spec = importlib.util.spec_from_file_location('builder', source / 'tools/build_beta_bundle.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
commit = sys.argv[1]
with tempfile.TemporaryDirectory(prefix='eidolon-published-source-') as temporary:
    directory = Path(temporary)
    archive = directory / 'source.tar.gz'
    built = builder.build(source.parent, commit, archive)
    verified = builder.verify(archive)
    assert verified['verified'] is True
    # Only extract after the strict allow-list/regular-file verifier succeeded.
    with tarfile.open(archive) as handle:
        handle.extractall(directory, filter='data')
    core = directory / built['root'] / 'eidolon-core'
    for name in ('HTTP-RESEARCH-ARCHIVES.md', 'BETA-RESEARCH-FIXTURE.md', 'LOCAL-MODEL-CLI.md',
                 'PROJECT-STATUS-2026-10-07.md'):
        assert (core / 'docs' / name).is_file()
    env = dict(os.environ)
    env['PYTHONPATH'] = str(core / 'src')
    done = subprocess.run([sys.executable, '-m', 'eidolon_core.beta_check', '--web-root',
                           str(core / 'desktop/connected'), '--profile', 'research-archives'],
                          cwd=directory, env=env, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, 'extracted recipe failed'
    recipe = json.loads(done.stdout)
    assert recipe['checks_passed'] == 25
    result = {'status': 'PASS', 'commit': commit, 'source_files': built['files'],
              'archive_bytes': built['bytes'], 'archive_sha256': built['sha256'],
              'verification': verified, 'new_guides_present': True, 'extracted_recipe_checks': 25,
              'browser_or_user_server_tested': False}
result['temporary_files_removed'] = not directory.exists()
print(json.dumps(result, indent=2))
