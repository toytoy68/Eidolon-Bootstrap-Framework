# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : g063-invalid-snapshot.py
# Description : Fermeture du snapshot prototype lors d'un refus de métadonnées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/. Only synthetic journals in a temporary directory."""
import gc
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

source = str(Path('src').resolve())
sys.path[:0] = [source, str(Path('docs/proposals/2026-10-07-research-retention').resolve())]
sys.argv = [sys.argv[0], source]
import probes_g057
import rotation

with tempfile.TemporaryDirectory(prefix='g063-invalid-snapshot-') as temporary:
    guard, archives = probes_g057.build(Path(temporary) / 'fixture')
    db = sqlite3.connect(guard / 'research-runs.sqlite3')
    try:
        db.execute("DELETE FROM metadata WHERE key='guard_id'")
        db.commit()
    finally:
        db.close()
    before_bytes = (guard / 'research-runs.sqlite3').read_bytes()
    gc.collect()
    gc.disable()
    try:
        before = len(os.listdir('/proc/self/fd'))
        errors = []
        for _ in range(10):
            try:
                rotation.verify(guard, archives, guard_src=source)
            except Exception as exc:
                errors.append(type(exc).__name__)
        after = len(os.listdir('/proc/self/fd'))
    finally:
        gc.enable()
    gc.collect()
    final = len(os.listdir('/proc/self/fd'))
    print(json.dumps({'refusals': errors, 'fd_before': before, 'fd_before_gc': after, 'fd_after_gc': final,
                      'active_database_unchanged': (guard / 'research-runs.sqlite3').read_bytes() == before_bytes,
                      'archives_created': len(list(archives.iterdir()))}))
