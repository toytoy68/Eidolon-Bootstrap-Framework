# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g345.py
# Description : Préparation vérifiée de Sana Sprint1.6B
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib,json,os,pathlib,subprocess,urllib.request
w=pathlib.Path('/srv/eidolon/workspaces/media-20261112/sana-sprint-g345')
model=pathlib.Path('/srv/eidolon/data/media-models-20261113/sana-sprint-1600m')
old=pathlib.Path('/srv/eidolon/data/media-models-20261113/sana-1600m')
repo='Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers'
rev='19683c58b7ea290e55cedd8950ae1d86ada7ef96'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
meta=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/revision/'+rev+'?blobs=true',timeout=30))
assert meta['sha']==rev
(w/'author-metadata.json').write_text(json.dumps(meta,indent=2))
model.mkdir(mode=0o700,exist_ok=True)
large=[];small=[]
for row in meta['siblings']:
 path=row['rfilename']
 if not (path in ['README.md','LICENSE','LICENSE.md','model_index.json'] or path.split('/')[0] in ['text_encoder','tokenizer','transformer','vae','scheduler']):continue
 dest=model/path;dest.parent.mkdir(parents=True,exist_ok=True)
 if path.endswith('.safetensors'):
  record=dict(repo=repo,revision=rev,path=path,name=dest.name,bytes=row['size'],sha256=row['lfs']['sha256'])
  large.append(record)
  if (old/path).is_file() and (old/path).stat().st_size==record['bytes'] and sha(old/path)==record['sha256']:
   if not dest.exists():os.link(old/path,dest)
   assert sha(dest)==record['sha256']
   print(json.dumps({'reused_verified':path}),flush=True)
  else:
   manifest=w/(path.split('/')[0]+'-downloads.json')
   manifest.write_text(json.dumps([record],indent=2))
   subprocess.run(['/usr/bin/python3','/srv/eidolon/workspaces/media-20261112/source/eidolon-core/docs/studies/2026-11-12-eidolon-media/download_candidates.py','--manifest',str(manifest),'--root',str(dest.parent)],check=True)
 else:
  content=urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+rev+'/'+path,timeout=60).read()
  assert len(content)==row['size']
  if 'lfs' in row:assert hashlib.sha256(content).hexdigest()==row['lfs']['sha256']
  else:assert hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()==row['blobId']
  dest.write_bytes(content);small.append(dict(path=path,sha256=sha(dest),bytes=len(content)))
(w/'downloads.json').write_text(json.dumps(large,indent=2))
(w/'small-files.json').write_text(json.dumps(small,indent=2))
(w/'prepare-complete.json').write_text(json.dumps({'revision':rev,'weights':len(large),'configs':len(small)}))
print('PREPARE_COMPLETE',flush=True)
