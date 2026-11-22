# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : summarize_eva.py
# Description : Post-run diagnostics, no model selection or inference
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json

P = Path('/srv/eidolon/ssd/work/followup-20261122')
E = P / 'eva'
S = P / 'core/eidolon-core/docs/studies/2026-11-22-followup'
read = lambda p: json.loads(p.read_text())
assert read(E / 'campaign-status.json')['phase'] == 'finished'
result = read(E / 'resultat-final.json')
cases = {x['id']: x for x in read(E / 'roles.json')}
variants = [('baseline', 'parent')] + [
    (f'eval{i}', f'step{102*i}') for i in (1, 2) if (E / f'eval{i}/assessment.json').exists()]
out = {}
for folder, candidate in variants:
    rows = sum([read(E / folder / f'roles-{candidate}-rank{r}.json')['rows'] for r in (0, 1)], [])
    assert len(rows) == len(cases) == 52
    assert {x['id'] for x in rows} == set(cases)
    scores, records = {}, []
    for row in rows:
        case = cases[row['id']]
        assert row['question'] == case['question']
        correct = None
        if case['expected'] is not None:
            try:
                actual = json.loads(row['response'].strip())
                correct = json.dumps(actual, sort_keys=True, ensure_ascii=False) == json.dumps(case['expected'], sort_keys=True, ensure_ascii=False)
            except ValueError:
                correct = False
            score = scores.setdefault(case['role'], dict(n=0, strict=0, truncated=0))
            score['n'] += 1
            score['strict'] += int(correct)
            score['truncated'] += int(row['truncated'])
        records.append(dict(id=row['id'], role=case['role'], response=row['response'],
                            expected=case['expected'], strict=correct, truncated=row['truncated']))
    out[candidate] = dict(scores=scores, records=records)
transfer = dict(scope='Post-hoc diagnostic only; NF4 vs NF4, max_new_tokens 384; no checkpoint selection', variants=out)
(P / 'eva-role-transfer.json').write_text(json.dumps(transfer, ensure_ascii=False, indent=2))
(S / 'eva-role-transfer.json').write_text(json.dumps(transfer, ensure_ascii=False, indent=2))
t = result['telemetry']
energy = dict(scope='Whole X399 at wall; successful sampled E6 stage intervals only; excludes CPU preflight, failed launches, other model benchmarks and gaps. Other session work can contribute to wall power.',
              energy_wh=sum(v['energy_wh'] for v in t.values()),
              sampled_seconds=sum(v['energy_interval_seconds'] for v in t.values()),
              max_gpu_c=max(g['gpu_c']['max'] for v in t.values() for g in v['gpu']),
              max_hbm_c=max(g['hbm_c']['max'] for v in t.values() for g in v['gpu']),
              max_cpu_c=max(g['cpu_c']['max'] for v in t.values() for g in v['gpu']),
              stages=t)
(P / 'eva-energy.json').write_text(json.dumps(energy, indent=2))
(S / 'eva-energy.json').write_text(json.dumps(energy, indent=2))
(S / 'eva-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(dict(decision=result['decision'], role_scores={k:v['scores'] for k,v in out.items()},
                      energy_wh=energy['energy_wh'], max_gpu_c=energy['max_gpu_c'],
                      max_hbm_c=energy['max_hbm_c'], max_cpu_c=energy['max_cpu_c']), indent=2))
