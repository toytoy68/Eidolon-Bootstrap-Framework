# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : g063-backup-contention.py
# Description : Délai observé sous verrou SQLite externe du prototype isolé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic writer, owned child terminated after six seconds; no Core rotation."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

source = str(Path('src').resolve())
proposal = str(Path('docs/proposals/2026-10-07-research-retention').resolve())
sys.path[:0] = [source, proposal]
sys.argv = [sys.argv[0], source]
import probes_g057

with tempfile.TemporaryDirectory(prefix='eidolon-backup-contention-') as temporary:
    root = Path(temporary)
    guard, archives = probes_g057.build(root / 'fixture')
    before = (guard / 'research-runs.sqlite3').read_bytes()
    scratch = root / 'child-temporary'; scratch.mkdir()
    writer = sqlite3.connect(guard / 'research-runs.sqlite3')
    writer.execute('BEGIN EXCLUSIVE')
    code = ('import sys;sys.path[:0]=[sys.argv[1],sys.argv[2]];import rotation;'
            'rotation.verify(sys.argv[3],sys.argv[4],guard_src=sys.argv[1])')
    started = time.monotonic()
    child = subprocess.Popen([sys.executable, '-c', code, source, proposal, str(guard), str(archives)],
                             env={**os.environ, 'TMPDIR': str(scratch)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exceeded = False
    try:
        try:
            child.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            exceeded = True
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
        writer.rollback(); writer.close()
    result = {'synthetic_external_sqlite_writer': True, 'verification_still_running_after_six_seconds': exceeded,
              'elapsed_seconds': round(time.monotonic()-started, 3), 'owned_child_stopped': child.poll() is not None,
              'active_database_unchanged': (guard / 'research-runs.sqlite3').read_bytes() == before,
              'archives_created': len(list(archives.iterdir())), 'proves_infinite_wait': False,
              'active_core_rotation_enabled': False}
result['temporary_files_removed'] = not root.exists()
print(json.dumps(result, indent=2))
