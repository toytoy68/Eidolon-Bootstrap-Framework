# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : compatibility.py
# Description : Rejouer le banc G068 sans son oracle historique des écarts
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from repository root; synthetic journals only, no production activation."""
from pathlib import Path
import runpy
import sys
import tempfile

sys.argv = ['bench', str(Path('eidolon-core/src').resolve())]
bench = runpy.run_path('eidolon-core/docs/proposals/2026-10-07-retention-integration/bench_g068.py')
with tempfile.TemporaryDirectory(prefix='c046-') as directory:
    for scenario in ('nominal', 'wal', 'crashes', 'reversible'):
        bench[scenario](Path(directory))
print('Failures:', bench['FAILED'])
raise SystemExit(bool(bench['FAILED']))
