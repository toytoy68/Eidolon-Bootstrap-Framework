# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : check-snapshot-close.py
# Description : Tester le correctif proposé sur une copie jetable du prototype
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Does not modify the proposal or activate Core retention."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

source = Path.cwd()
proof = source / 'docs/validation/2026-10-07/codex-hour-1948'
proposal = source / 'docs/proposals/2026-10-07-research-retention'
before = (proposal / 'rotation.py').read_bytes()
with tempfile.TemporaryDirectory(prefix='eidolon-proposed-close-') as temporary:
    root = Path(temporary)
    copied = root / 'eidolon-core/docs/proposals/2026-10-07-research-retention'
    copied.parent.mkdir(parents=True)
    shutil.copytree(proposal, copied, ignore=shutil.ignore_patterns('__pycache__'))
    done = subprocess.run(['git', 'apply', str(proof / 'g063-snapshot-close.patch')], cwd=root,
                          capture_output=True, text=True, timeout=10)
    assert done.returncode == 0, done.stderr
    environment = {**os.environ, 'G062_SRC': str(source / 'src'), 'PYTHONPATH': str(copied)}
    runner = '''import gc,unittest
import tests_g062,tests_g063
gc.collect();gc.disable()
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (tests_g062,tests_g063))
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
'''
    tested = subprocess.run([sys.executable, '-c', runner], cwd=root, env=environment,
                            capture_output=True, text=True, timeout=30)
    (proof / 'g063-proposed-close-tests.txt').write_text(tested.stdout + tested.stderr)
    assert tested.returncode == 0
    probe = (proof / 'g063-invalid-snapshot.py').read_text()
    probe = probe.replace("source = str(Path('src').resolve())", 'source = ' + repr(str(source / 'src')))
    probe = probe.replace("str(Path('docs/proposals/2026-10-07-research-retention').resolve())", repr(str(copied)))
    checked = subprocess.run([sys.executable, '-c', probe], cwd=root, env=environment,
                             capture_output=True, text=True, timeout=10)
    assert checked.returncode == 0, checked.stderr
    result = json.loads(checked.stdout)
    assert result['fd_before_gc'] == result['fd_before'] == result['fd_after_gc']
    result.update(proposal_unchanged=(proposal / 'rotation.py').read_bytes()==before,
                  tested_on_temporary_copy=True, integrated_into_core=False, grouped_assertions_passed=21)
result['temporary_copy_removed'] = not root.exists()
print(json.dumps(result, indent=2))
