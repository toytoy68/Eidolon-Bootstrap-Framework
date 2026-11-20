# Eidolon Core Technologies (ECT) - reproducible model acquisition
from pathlib import Path
import urllib.request,json,hashlib,time,concurrent.futures
P=Path(__file__).resolve().parent; D=P/'models';D.mkdir(exist_ok=True)
specs=[
('LiquidAI/LFM2.5-1.2B-Instruct-GGUF','LFM2.5-1.2B-Instruct-Q4_K_M.gguf'),
('ggml-org/SmolLM3-3B-GGUF','SmolLM3-3B-Q4_K_M.gguf'),
('unsloth/Phi-4-mini-instruct-GGUF','Phi-4-mini-instruct-Q4_K_M.gguf'),
('tiiuae/Falcon3-3B-Instruct-GGUF','Falcon3-3B-Instruct-q4_k_m.gguf')]
def get(repo,name):
 try:
  info=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=20))
  names=[f['rfilename'] for f in info['siblings']]
  if name not in names:
   opts=[f for f in names if 'q4_k_m.gguf' in f.lower()]
   assert len(opts)==1,opts
   name=opts[0]
  rev=info['sha']; row=next(f for f in info['siblings'] if f['rfilename']==name)
  (D/(repo.replace('/','--')+'.json')).write_text(json.dumps(info,indent=2))
  for f in ['README.md']:
   try:(D/(repo.replace('/','--')+'.md')).write_bytes(urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+rev+'/'+f,timeout=20).read())
   except Exception:pass
  dst=D/Path(name).name
  h=hashlib.sha256();count=0
  with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+rev+'/'+name,timeout=60) as src,dst.with_suffix('.part').open('wb') as out:
   while True:
    chunk=src.read(8*1024*1024)
    if not chunk:break
    out.write(chunk);h.update(chunk);count+=len(chunk)
  expected=row.get('lfs',{}).get('sha256')
  assert expected and h.hexdigest()==expected,(repo,h.hexdigest(),expected)
  dst.with_suffix('.part').rename(dst)
  return dict(repo=repo,revision=rev,file=str(dst),sha256=h.hexdigest(),bytes=count,verified=True,license=info.get('cardData',{}).get('license'))
 except Exception as e:return dict(repo=repo,error=repr(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(lambda s:get(*s),specs):
  with (P/'downloads.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
  print(result,flush=True)
