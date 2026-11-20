# Eidolon Core Technologies (ECT) — post-training diagnostics, no selection
from pathlib import Path
import time,json,subprocess
P=Path(__file__).resolve().parent;E=Path('/srv/eidolon/work/eva-learning-cycle13-lowdose-20261120')
deadline=time.time()+14400
while True:
 s=json.loads((E/'campaign-status.json').read_text())
 if s['phase'] in ['finished','failed']:break
 assert time.time()<deadline,'Waiting for Eva timed out'
 time.sleep(15)
assert s['phase']=='finished',s
# Wait until controller exits and releases its GPUs.
while subprocess.run(['systemctl','is-active','eidolon-eva-e5-20261120'],capture_output=True,text=True).stdout.strip()=='active':
 assert time.time()<deadline
 time.sleep(2)
r=subprocess.run(['/usr/bin/python3',str(P/'bench_prism_perf_clean.py')],stdout=(P/'prism-perf-clean-run.log').open('w'),stderr=subprocess.STDOUT)
assert r.returncode==0
cases={x['id']:x for x in json.loads((P/'cases.json').read_text())}
variants=[('baseline','parent')]+[(f'eval{i}',f'step{102*i}') for i in [1,2] if (E/f'eval{i}/assessment.json').exists()]
out={}
for folder,candidate in variants:
 rows=sum([json.loads((E/folder/f'roles-{candidate}-rank{r}.json').read_text())['rows'] for r in [0,1]],[])
 assert len(rows)==52 and len({x['id'] for x in rows})==52
 scores={};records=[]
 for x in rows:
  c=cases[x['id']];response=x['response'];correct=None
  if c['expected'] is not None:
   try:actual=json.loads(response.strip());correct=json.dumps(actual,sort_keys=True,ensure_ascii=False)==json.dumps(c['expected'],sort_keys=True,ensure_ascii=False)
   except Exception:correct=False
   z=scores.setdefault(c['role'],dict(n=0,strict=0,truncated=0));z['n']+=1;z['strict']+=int(correct);z['truncated']+=int(x['truncated'])
  records.append(dict(id=x['id'],role=c['role'],response=response,expected=c['expected'],strict=correct,truncated=x['truncated']))
 out[candidate]=dict(scores=scores,records=records)
(E/'role-transfer-summary.json').write_text(json.dumps(dict(scope='Post-hoc diagnostic, NF4 vs NF4, max_new_tokens 384, no checkpoint selection',variants=out),ensure_ascii=False,indent=2))
result=json.loads((E/'resultat-final.json').read_text())
t=result['telemetry'];energy=dict(scope='Whole X399 at wall; only sampled Eva stage intervals; excludes CPU preflight, model benchmarks and between-stage gaps',energy_wh=sum(x['energy_wh'] for x in t.values()),sampled_seconds=sum(x['energy_interval_seconds'] for x in t.values()),stages=t)
(P/'energy-summary.json').write_text(json.dumps(energy,indent=2))
(P/'post-eva-status.json').write_text(json.dumps(dict(finished=True,epoch=time.time(),last_step=result['decision']['last_step'])))
