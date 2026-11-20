# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g341.py
# Description : Préparation vérifiée de Klein base 4B
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib,json,os,pathlib,subprocess,urllib.request
w=pathlib.Path(__file__).parent
model=pathlib.Path('/srv/eidolon/data/media-models-20261113/klein-base-4b')
old=pathlib.Path('/srv/eidolon/data/media-models-20261113/klein-4b')
repo='black-forest-labs/FLUX.2-klein-base-4B'
rev='a3b4f4849157f664bdbc776fd7453c2783562f4d'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
meta=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/revision/'+rev+'?blobs=true',timeout=30))
assert meta['sha']==rev
(w/'author-metadata.json').write_text(json.dumps(meta,indent=2))
model.mkdir(mode=0o700,exist_ok=True)
large=[];small=[]
for row in meta['siblings']:
 path=row['rfilename']
 if not (path in ['README.md','LICENSE.md','model_index.json'] or path.split('/')[0] in ['text_encoder','tokenizer','transformer','vae','scheduler']):continue
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
