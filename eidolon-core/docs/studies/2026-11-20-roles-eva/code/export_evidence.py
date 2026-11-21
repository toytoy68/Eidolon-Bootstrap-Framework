# Eidolon Core Technologies (ECT) - public synthetic evidence, private weights retained locally
from pathlib import Path
import json,re,hashlib,shutil
P=Path(__file__).resolve().parent;D=P/'core/eidolon-core/docs/studies/2026-11-20-roles-eva'
def safe(s):
 s=re.sub(r'GPU-[0-9a-fA-F-]{36}', 'GPU-REDACTED',s)
 s=re.sub(r'192\.168\.\d+\.\d+', 'LAN-REDACTED',s)
 return s
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(safe(src.read_text()))
for n in ['benchmark-summary.json','structured-summary.json','extended-summary.json','extended-structured-summary.json','qwen30-summary.json','qwen30-structured-summary.json','qwen30-thinking-summary.json','prism-quality-summary.json','prism-perf.json','prism-perf-clean.json','prism-packing-equivalence.json','model-integrity.json','gguf-identities.json','protocol-frozen.json','harness-verification.json','schema-correction.json','metadata-reader-stop.json','qwen30-review.json','chat-review.json','closure-preflight.json','energy-summary.json','runtime-manifest.json','verification.json']:
 if (P/n).exists():copy(P/n,D/n)
for folder in ['wevis-results','wevis-fp32-decoder','wevis-full-fp32']:
 for name in ['results.json','assessment.json','status.json','protocol.json']:
  if (P/folder/name).exists():copy(P/folder/name,D/folder/name)
for folder in ['responses','structured','extended','extended-structured','qwen30','qwen30-structured','qwen30-thinking','prism-quality']:
 for model in (P/folder).glob('*'):
  if not model.is_dir():continue
  records=[]
  for f in sorted(model.glob('*.json')):
   if f.name=='props.json':continue
   x=json.loads(f.read_text());row={k:x[k] for k in ['id','role','expected','content','strict','semantic','critical','finish_reason','seconds','ttft_content_s','usage','error'] if k in x}
   if 'reasoning'in x:row['reasoning_characters']=len(x['reasoning'])
   records.append(row)
  if records:
   out=D/'responses'/(folder+'--'+model.name+'.jsonl');out.parent.mkdir(exist_ok=True);out.write_text(safe('\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in records)+'\n'))
for f in (D/'code').glob('*.py'):f.write_text(safe(f.read_text()))
E=Path('/srv/eidolon/work/eva-learning-cycle13-lowdose-20261120')
for name in ['config.json','lineage.json','source-manifest.json','launch-manifest.json','cpu-preflight.json','self-check.json','dataset-preparation.json','campaign-status.json','experiment-decision.json','baseline-scores.json','resultat-final.json','role-transfer-summary.json','canary-review.json','cpu-preflight-status.json']:
 if (E/name).exists():copy(E/name,D/'eva'/name)
for folder in ['qualification-dual','phase1','phase2','eval1','eval2']:
 for name in ['passed.json','training-summary.json','assessment.json','guard-trip.json','status.json']:
  if (E/folder/name).exists():copy(E/folder/name,D/'eva'/folder/name)
if (E/'result-saved.json').exists():
 x=json.loads((E/'result-saved.json').read_text())
 out=dict(state=x['state'],epoch=x['epoch'],verified_files=len(x['files']),automatic_promotion=x['automatic_promotion'],checkpoints={k:v for k,v in x['files'].items() if k.startswith('checkpoints/') and k.endswith(('safetensors','complete.json'))})
 (D/'eva/saved-checkpoints.json').write_text(json.dumps(out,indent=2))
for name in [f.name for f in E.glob('*.py')]:
 copy(E/name,D/'eva/code'/name)
index=[]
for f in D.rglob('*'):
 if f.is_file() and f.name!='SOURCE-INDEX.json':index.append(dict(path=str(f.relative_to(D)),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
(D/'SOURCE-INDEX.json').write_text(json.dumps(index,indent=2))
print(json.dumps(dict(files=len(index),bytes=sum(x['bytes'] for x in index))))
