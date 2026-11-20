# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g346.py
# Description : Préparation vérifiée de SD3.5 Medium pour G346
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json,hashlib,urllib.request,subprocess,os,shutil
from pathlib import Path
w=Path('/srv/eidolon/workspaces/media-20261112/sd35-medium-g346');dest=Path('/srv/eidolon/data/media-models-20261113/sd35-medium');dest.mkdir(exist_ok=True)
a=json.loads((w/'author-metadata.json').read_text());m=json.loads((w/'mirror-metadata.json').read_text());aa={f['rfilename']:f for f in a['siblings']};mm={f['rfilename']:f for f in m['siblings']}
assert not m['gated'];assert shutil.disk_usage(dest).free>30*1024**3
names=['text_encoder/model.safetensors','text_encoder_2/model.safetensors','text_encoder_3/model-00001-of-00002.safetensors','text_encoder_3/model-00002-of-00002.safetensors','transformer/diffusion_pytorch_model.safetensors','vae/diffusion_pytorch_model.safetensors']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
small=[]
for n,f in aa.items():
 if n=='LICENSE.md' or n=='model_index.json' or n.startswith(('tokenizer/','tokenizer_2/','tokenizer_3/','scheduler/')) or n in ['text_encoder/config.json','text_encoder_2/config.json','text_encoder_3/config.json','text_encoder_3/model.safetensors.index.json','transformer/config.json','vae/config.json']:
  assert f['blobId']==mm[n]['blobId'],n
  b=urllib.request.urlopen('https://huggingface.co/'+m['id']+'/resolve/'+m['sha']+'/'+n,timeout=45).read();assert (hashlib.sha256(b).hexdigest()==f['lfs']['sha256'] if f.get('lfs') else hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['blobId']),n
  p=dest/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);small.append({'path':n,'bytes':len(b),'sha256':sha(p),'author_blob':f['blobId']})
(w/'small-files.json').write_text(json.dumps(small,indent=2))
records=[]
for n in names:
 f=aa[n];assert f['lfs']['sha256']==mm[n]['lfs']['sha256'];h=f['lfs']['sha256'];p=dest/n;p.parent.mkdir(parents=True,exist_ok=True);source='download'
 if not p.exists():
  for root in [Path('/srv/eidolon/data/media-models-20261113')]:
   candidates=[q for q in root.rglob('*.safetensors') if q!=p and q.stat().st_size==f['size']]
   for q in candidates:
    if sha(q)==h:os.link(q,p);source=str(q);break
   if p.exists():break
 if not p.exists():
  part=p.with_suffix('.partial');url='https://huggingface.co/'+m['id']+'/resolve/'+m['sha']+'/'+n
  subprocess.run(['curl','--fail','--location','--retry','3','--connect-timeout','20','--max-time','1200','--silent','--show-error','--output',str(part),url],check=True)
  assert part.stat().st_size==f['size'] and sha(part)==h,n
  part.replace(p)
 assert p.stat().st_size==f['size'] and sha(p)==h,n
 records.append({'repo':m['id'],'revision':m['sha'],'author_repo':a['id'],'author_revision':a['sha'],'path':n,'bytes':f['size'],'sha256':h,'source':source});(w/'downloads.json').write_text(json.dumps(records,indent=2));print(json.dumps({'verified':n,'source':source}),flush=True)
(w/'prepare-complete.json').write_text(json.dumps({'weights':len(records),'small_files':len(small),'author_sha_identical':True,'licence':'Stability AI Community License July 5 2024'}));print('PREPARED',flush=True)
