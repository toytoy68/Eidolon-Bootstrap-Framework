# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : summarize.py
# Description : Summarize completed N6000 qualification and RAPL package intervals
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,math,time,hashlib,bisect
P=Path('/home/toytoy/wall-e/qualification-20261122');Q=P/'compact-cool'
assert json.loads((Q/'status.json').read_text())['phase']=='finished'
raw=json.loads((Q/'summary-raw.json').read_text())
rapl=P/'rapl-export'
meta=json.loads((rapl/'rapl-meta.json').read_text());key=next(k for k,v in meta.items() if v['name']=='package-0');wrap=meta[key]['max_uj']
samples=[json.loads(x) for x in (rapl/'rapl.jsonl').read_text().splitlines()]
def energy(start,end):
 a=max((x for x in samples if x['epoch']<=start),key=lambda x:x['epoch'],default=None)
 b=min((x for x in samples if x['epoch']>=end),key=lambda x:x['epoch'],default=None)
 if not a or not b:return dict(measured=False)
 series=[x for x in samples if a['epoch']<=x['epoch']<=b['epoch']]
 joules=sum((b['energy_uj'][key]-a['energy_uj'][key])%wrap for a,b in zip(series,series[1:]))/1e6
 dt=b['epoch']-a['epoch'];gaps=[b['epoch']-a['epoch'] for a,b in zip(series,series[1:])]
 return dict(measured=True,scope='RAPL package-0 estimate, not whole system',wh=joules/3600,mean_w=joules/dt,seconds=dt,max_sample_gap_s=max(gaps,default=0),start_epoch=a['epoch'],end_epoch=b['epoch'])

def request_energy(rows):
 epochs=[x['epoch'] for x in samples];indices=set();missing=0
 for r in rows:
  if 'start_epoch' not in r or 'end_epoch' not in r:continue
  i=bisect.bisect_right(epochs,r['start_epoch'])-1;j=bisect.bisect_left(epochs,r['end_epoch'])
  if i<0 or j>=len(samples):missing+=1;continue
  indices.update(range(i,j))
 joules=sum((samples[i+1]['energy_uj'][key]-samples[i]['energy_uj'][key])%wrap for i in indices)/1e6
 dt=sum(epochs[i+1]-epochs[i] for i in indices)
 return dict(measured=bool(indices),scope='Union of request windows, RAPL package-0 including background; not AC energy',wh=joules/3600,mean_w=joules/dt if dt else None,seconds=dt,missing_intervals=missing,max_gap_s=max((epochs[i+1]-epochs[i] for i in indices),default=0))

def pct(v,p):
 return sorted(v)[max(0,math.ceil(p*len(v))-1)] if v else None
out=[]
for model in raw:
 rows=model['rows'];valid=[r for r in rows if 'error' not in r and r.get('finish') is not None]
 scores={}
 for role in ['robot','darme','systeme']:
  rr=[r for r in rows if r['role']==role]
  scores[role]=dict(attempted=len(rr),completed=sum('error' not in r and r.get('finish') is not None for r in rr),expected=12,correct=sum(r.get('strict') is True for r in rr),critical_failures=[r['id'] for r in rr if r['critical'] and r.get('strict') is not True],errors=[r['id'] for r in rr if 'error' in r])

  by_label={}
  confusion={}
  for r in rr:
   expected=next(iter(r['expected'].values()));item=by_label.setdefault(expected,dict(total=0,correct=0));item['total']+=1;item['correct']+=r.get('strict') is True
   try:actual=next(iter(json.loads(r.get('content','')).values()))
   except Exception:actual='INVALID_OR_MISSING'
   confusion[expected+' -> '+str(actual)]=confusion.get(expected+' -> '+str(actual),0)+1
  scores[role]['by_label']=by_label
  scores[role]['confusion']=confusion
  scores[role]['constant_majority_correct']=max((v['total'] for v in by_label.values()),default=0)
  scores[role]['balanced_accuracy']=statistics.mean(v['correct']/v['total'] for v in by_label.values()) if by_label else None
 ttft=[r['ttft_s'] for r in valid if r.get('ttft_s') is not None and r['role']!='chat']
 tel=json.loads((Q/model['name']/'telemetry.json').read_text())
 rss=[int(x['rss'].split()[1]) for x in tel if x.get('rss')]
 temps=[x['cpu_c'] for x in tel if x.get('cpu_c') is not None]
 chat=[{k:r.get(k) for k in ['id','content','ttft_s','seconds','usage','finish','error']} for r in rows if r['role']=='chat']
 result=dict(model=model['name'],sha256=model['sha256'],scores=scores,role_median_ttft_s=statistics.median(ttft) if ttft else None,role_p95_ttft_s=pct(ttft,.95),peak_rss_mib=max(rss)/1024 if rss else None,max_cpu_c=max(temps) if temps else None,load_s=model.get('load_seconds'),energy=energy(model['start_epoch'],model['end_epoch']),request_energy=request_energy(rows),resumed_rows=model.get('resumed_rows',0),chat=chat,errors=[r for r in rows if 'error' in r],truncated=sum(r.get('finish')=='length' for r in rows),run_error=model.get('error'))
 result['responses_completed']=len(valid)
 result['critical_cases']=sum(r.get('critical',False) for r in rows)
 result['critical_correct']=sum(r.get('critical',False) and r.get('strict') is True for r in rows)
 timing=[r.get('timings',{}) for r in valid]
 for label,nkey,tkey in [('prompt','prompt_n','prompt_ms'),('generation','predicted_n','predicted_ms')]:
  pairs=[(t[nkey],t[tkey]) for t in timing if t.get(tkey,0)>0 and nkey in t]
  result[label+'_aggregate_tokens_s']=sum(n for n,ms in pairs)*1000/sum(ms for n,ms in pairs) if pairs else None
 out.append(result)
report=dict(schema='eidolon-n6000-qualification/1',models=out,profile=dict(threads=3,max_freq_ghz=2,cpu_only=True,thermal_stop_c=85,compact_roles=36,chat_canaries=3,cooldown_c=70,pause_c=75,initial_33_responses_cooldown_c=65),role_authority='suggestions only; no actuation or autonomous security/system control',energy_limit='Package RAPL only; unmeasured AC power',original_profile='Uncapped compact attempt reached85C; incomplete responses excluded. First33 capped responses retained, cooldown65C/300s amended to70C/1200s; request energy excludes the recovery interval.')
(P/'final-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
