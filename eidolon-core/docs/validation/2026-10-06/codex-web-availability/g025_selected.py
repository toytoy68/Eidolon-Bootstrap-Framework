# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : g025_selected.py
# Description : Rejouer W07/W14/W15 sans réécrire le corpus ni ses oracles
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core with PYTHONPATH=src:. ; synthetic, no network."""
import importlib.util
import json
from pathlib import Path


path = Path(__file__).resolve().parents[1] / 'claude-g025/run_g007_on_head.py'
spec = importlib.util.spec_from_file_location('g025', path)
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)
results = []
for identity, expected in [('W07', 'HITS_FOUND'), ('W14', 'UNAVAILABLE'), ('W15', 'EMPTY')]:
    case = next(c for c in corpus.CORPUS['cases'] if c['id'] == identity)
    coordinator, _ = corpus.coordinator(case, corpus.Clock(), [])
    report = coordinator.run(case['setup']['query'], required_pages=2 if identity == 'W07' else 1)
    assert report['discovery_status'] == expected
    results.append({
        'case': identity, 'status': report['status'],
        'discovery_status': report['discovery_status'], 'readable_pages': report['readable_pages'],
        'states': [s['state'] for s in report['sources']],
        'note': ('W07 HTML original reste non pris en charge ; oracle une seule requete non satisfait'
                 if identity == 'W07' else 'Diagnostic global distingue'),
    })
print(json.dumps(results, indent=2))
