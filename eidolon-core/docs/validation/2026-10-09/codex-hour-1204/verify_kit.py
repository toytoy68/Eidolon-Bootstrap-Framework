# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : verify_kit.py
# Description : Archive documentaire reproductible, code installé identique et six demandes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with the already-tested installed Python, after build_beta_bundle --verify."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import eidolon_core

repo = Path(__file__).resolve().parents[4]
first, second = map(Path, sys.argv[1:3])
assert first.read_bytes() == second.read_bytes()
installed = Path(eidolon_core.__file__).parent
assert 'site-packages' in str(installed)
with tempfile.TemporaryDirectory(prefix='eidolon-media-kit-') as folder:
    with tarfile.open(first) as archive:
        archive.extractall(folder, filter='data')
    root, = Path(folder).iterdir()
    core = root / 'eidolon-core'
    files = sorted((core / 'src/eidolon_core').glob('*.py'))
    assert len(files) == 72
    assert all(p.read_bytes() == (installed / p.name).read_bytes() == (repo / 'src/eidolon_core' / p.name).read_bytes()
               for p in files)
    for name in ('MEDIA-REAL-RECIPE.md','MEDIA-AGENTS.md','CONVERSATION-API.md'):
        assert (core/'docs'/name).read_bytes() == (repo/'docs'/name).read_bytes()
    assert (core/'desktop/connected/app.js').read_bytes() == (repo/'desktop/connected/app.js').read_bytes()
    requests = sorted((core/'examples/media').glob('*.json'))
    assert len(requests) == 6
    modes = []
    for path in requests:
        assert path.read_bytes() == (repo/'examples/media'/path.name).read_bytes()
        done = subprocess.run([str(Path(sys.executable).parent/'eidolon-media'),'prepare','--request',str(path)],
                              cwd=folder, env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'},
                              capture_output=True,text=True,timeout=10)
        assert done.returncode == 0, done.stderr
        value = json.loads(done.stdout)
        assert value['state'] == 'LOCAL_DRAFT' and value['submitted'] is False
        modes.append(value['request']['agent']+'.'+value['request']['operation'])
print(json.dumps({'status':'PASS', 'kit_commit':'bbf679c8b99b9170c7912600a11fee1f671ca912',
                  'installed_code_commit':'f02187830c64fc9c42cfa726d968e37cebf00fae',
                  'identical_archives':True,'sha256':hashlib.sha256(first.read_bytes()).hexdigest(),
                  'bytes':first.stat().st_size,'identical_installed_source_modules':len(files),
                  'same_conversation_bundle':True,'prepared_from_extracted_archive':modes,
                  'engine_calls_requested':False,'hardware_tests_run':False},indent=2))
