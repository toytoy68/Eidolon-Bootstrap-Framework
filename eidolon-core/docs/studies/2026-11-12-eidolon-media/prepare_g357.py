# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g357.py
# Description : Poids et provenance SDXL Inpainting G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import requests,json,hashlib,subprocess,time,shutil
R=Path('/srv/eidolon/workspaces/media-20261112');W=R/'sdxl-inpaint-g357';M=Path('/srv/eidolon/data/media-models-20261113/sdxl-inpaint-g357')
REPO='diffusers/stable-diffusion-xl-1.0-inpainting-0.1';REV='115134f363124c53c7d878647567d04daf26e41e';PY=R/'preference-lab/venv/bin/python'
W.mkdir(exist_ok=True);M.mkdir(exist_ok=True)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,d):(W/n).write_text(json.dumps(d,indent=2))
def get(url):
 r=requests.get(url,timeout=25);r.raise_for_status();return r
j=get(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true').json();assert j['sha']==REV and not j['gated'];write('author-metadata.json',j)
lic=R/'checkpoints-g333/sdxl-base-LICENSE.md';assert sha(lic)=='19b6998b569b53ac1fc2158a8a3202c8699a9a4605b47075715d9c96be7fb6d0';shutil.copy2(lic,W/'LICENSE.md')
write('license-provenance.json',{'source':str(lic),'sha256':sha(lic),'author_url':'https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md','license':'CreativeML Open RAIL++-M','usage':'private research evaluation; no weights redistributed','attribution':'Diffusers team / Stability AI'})
rows=[];start=time.monotonic()
for e in j['siblings']:
 name=e['rfilename']
 if not (name.endswith('.json') or name.endswith('/merges.txt') or name=='README.md' or name.endswith('.fp16.safetensors')):continue
 dest=M/name;dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists():
  part=dest.with_suffix(dest.suffix+'.partial');h=hashlib.sha256();total=0
  with requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}',stream=True,timeout=(20,120)) as response:
   response.raise_for_status()
   with part.open('wb') as f:
    for b in response.iter_content(8*1024*1024):
     f.write(b);h.update(b);total+=len(b)
     write('download-progress.json',{'file':name,'bytes':total,'total':e['size'],'elapsed':time.monotonic()-start})
  assert total==e['size']
  if e.get('lfs'):assert h.hexdigest()==e['lfs']['sha256']
  else:assert hashlib.sha1(b'blob '+str(total).encode()+b'\0'+part.read_bytes()).hexdigest()==e['blobId']
  part.rename(dest)
 assert dest.stat().st_size==e['size'];digest=sha(dest)
 if e.get('lfs'):assert digest==e['lfs']['sha256']
 else:assert hashlib.sha1(b'blob '+str(e['size']).encode()+b'\0'+dest.read_bytes()).hexdigest()==e['blobId']
 rows.append({'name':name,'path':str(dest),'sha256':digest,'bytes':e['size'],'blobId':e['blobId']})
 if not name.endswith('.safetensors'):
  out=W/'model-config'/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,out)
 write('download-manifest.json',rows)
assert json.loads((M/'unet/config.json').read_text())['in_channels']==9
(W/'runtime-before.txt').write_text(subprocess.check_output([str(PY),'-m','pip','freeze'],text=True))
runtime=R/'preference-lab/venv/lib/python3.12/site-packages'
paths=['diffusers/pipelines/stable_diffusion_xl/pipeline_stable_diffusion_xl_inpaint.py','diffusers/schedulers/scheduling_euler_discrete.py','diffusers/models/unets/unet_2d_condition.py','diffusers/models/autoencoders/autoencoder_kl.py','diffusers/image_processor.py','transformers/models/clip/modeling_clip.py']
write('runtime-provenance.json',[{'path':str(runtime/n),'sha256':sha(runtime/n)} for n in paths])
write('manifest.json',{'id':'sdxl_inpaint','repo':REPO,'revision':REV,'path':str(M),'files':rows})
write('prepare-complete.json',{'seconds':time.monotonic()-start,'files':len(rows),'bytes':sum(x['bytes'] for x in rows)})
print('Preparation verified',flush=True)
