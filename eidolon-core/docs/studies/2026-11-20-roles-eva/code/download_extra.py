# Eidolon Core Technologies (ECT) - pinned auxiliary weights
from pathlib import Path
import urllib.request,json,hashlib,concurrent.futures
P=Path(__file__).resolve().parent
repos=[('tencent/WeVisOne-VL-2B','wevis-model',None),('prism-ml/Ternary-Bonsai-2-2B-gguf','prism-models',['Ternary-Bonsai-2-2B-PTQ1_0.gguf','Ternary-Bonsai-2-2B-PQ2_0.gguf','Ternary-Bonsai-2-2B-mmproj-Q8_0.gguf'])]
results=[]
for repo,folder,names in repos:
 d=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=20));rev=d['sha'];out=P/folder;out.mkdir(exist_ok=True)
 (out/'source.json').write_text(json.dumps(d,indent=2))
 files=[f for f in d['siblings'] if (f['rfilename'] in names if names else f['rfilename'].endswith(('.json','.safetensors','.txt','.jinja','.md','.pt')))]
 def dl(f):
  name=f['rfilename'];dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
  with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+rev+'/'+name,timeout=60) as src,dest.with_suffix('.part').open('wb') as target:
   for chunk in iter(lambda:src.read(8388608),b''):target.write(chunk);h.update(chunk)
  expected=f.get('lfs',{}).get('sha256')
  if expected:assert expected==h.hexdigest(),name
  dest.with_suffix('.part').rename(dest)
  return dict(file=name,sha256=h.hexdigest(),lfs_verified=bool(expected),bytes=dest.stat().st_size)
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(dl,files))
  r=dict(repo=repo,revision=rev,files=rows,complete=True)
 except Exception as e:r=dict(repo=repo,error=repr(e),complete=False)
 results.append(r);(P/'extra-downloads.json').write_text(json.dumps(results,indent=2));print(repo,r['complete'],flush=True)
