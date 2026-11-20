# Eidolon Core Technologies (ECT) - content-addressed campaign assets
from pathlib import Path
import json,hashlib,time
P=Path(__file__).resolve().parent
paths=set()
for row in map(json.loads,(P/'downloads.jsonl').read_text().splitlines()):
 if row.get('verified'):paths.add(row['file'])
for row in json.loads((P/'extended-models.json').read_text()):paths.add(row['path'])
paths.update([str(P.parent/'backlog-20261120/candidates/LFM3-1.7B-Q4_K_M.gguf'),str(P.parent/'backlog-20261120/candidates/Ternary-Bonsai-2-2B-Q2_0.gguf'),str(P.parent/'campaign-20261120/qwen2.5-1.5b-instruct-q4_k_m.gguf')])
for folder in ['prism-models','wevis-model']:
 paths.update(str(f) for f in (P/folder).iterdir() if f.suffix in ['.gguf','.pt','.safetensors'])
root=Path('/srv/eidolon/models/ollama')
for f in (root/'manifests').rglob('*'):
 if f.is_file() and 'Qwen3-4B-Element8-Eva-Hermes-Heretic' in str(f):
  d=json.loads(f.read_text());paths.add(str(root/'blobs'/next(x['digest'] for x in d['layers'] if x['mediaType']=='application/vnd.ollama.image.model').replace(':','-')))
rows=[]
for s in sorted(paths):
 p=Path(s);h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 digest=h.hexdigest()
 if p.name.startswith('sha256-'):assert digest==p.name[7:]
 rows.append(dict(path=s,bytes=p.stat().st_size,sha256=digest))
(P/'model-integrity.json').write_text(json.dumps(dict(verified=True,epoch=time.time(),files=rows),indent=2))
