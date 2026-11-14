# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g355.py
# Description : Préparation vérifiée du comparatif Juggernaut XI
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import requests,json,hashlib,subprocess,shutil,time
R=Path('/srv/eidolon/workspaces/media-20261112');W=R/'juggernaut-xi-g355'
M=Path('/srv/eidolon/data/media-models-20261113/juggernaut-xi-g355');M.mkdir(exist_ok=True)
REPO='RunDiffusion/Juggernaut-XI-v11';REV='f836518c7a75f47a9e26bc661ff9509ef2ceb7c0';PY=R/'preference-lab/venv/bin/python'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,d):(W/n).write_text(json.dumps(d,indent=2))
def get(url):
 r=requests.get(url,timeout=25);r.raise_for_status();return r
j=get(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true').json();assert j['sha']==REV and not j['gated'];write('author-metadata.json',j)
card=get(f'https://huggingface.co/{REPO}/resolve/{REV}/README.md').content;entry=next(x for x in j['siblings'] if x['rfilename']=='README.md');assert hashlib.sha1(b'blob '+str(len(card)).encode()+b'\0'+card).hexdigest()==entry['blobId'];(W/'model-README.md').write_bytes(card)

url='https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.txt'
lic=get(url).content;assert b'Attribution-NonCommercial-NoDerivatives 4.0 International' in lic and len(lic)>15000
(W/'CC-BY-NC-ND-4.0.txt').write_bytes(lic);write('license-provenance.json',{'url':url,'sha256':hashlib.sha256(lic).hexdigest(),'attribution':'RunDiffusion / KandooAI; Juggernaut XI v11','usage':'private noncommercial evaluation, no weight redistribution','gate':'public author API gated=false; no form submitted'})
for name,expected in [('OpenRAIL-M-license.txt','be351ebe7ac01bcdbb018639aadcfd38f136b7dc3f2a3d4d3a24db51d1b210ef'),('sdxl-base-LICENSE.md','19b6998b569b53ac1fc2158a8a3202c8699a9a4605b47075715d9c96be7fb6d0')]:
 p=R/'checkpoints-g333'/name;assert sha(p)==expected;shutil.copy2(p,W/name)
shutil.copy2(R/'checkpoints-g333/Juggernaut-XL-v9-README.md',W/'v9-README.md')
v9=json.loads((R/'checkpoints-g333/downloads.json').read_text())[1];v9.update(id='v9',absolute='/srv/eidolon/models/media-20261112/checkpoints-g333/'+v9['name']);assert sha(Path(v9['absolute']))==v9['sha256']
(W/'runtime-before.txt').write_text(subprocess.check_output([str(PY),'-m','pip','freeze'],text=True))
config=R/'preference-lab/sdxl-config';write('config-provenance.json',[{'path':str(p),'sha256':sha(p)} for p in sorted(config.rglob('*')) if p.is_file()])
shutil.copytree(config,W/'sdxl-config')
runtime=R/'preference-lab/venv/lib/python3.12/site-packages/diffusers';write('runtime-provenance.json',[{'path':str(runtime/n),'sha256':sha(runtime/n)} for n in ['pipelines/stable_diffusion_xl/pipeline_stable_diffusion_xl.py','schedulers/scheduling_dpmsolver_multistep.py','models/unets/unet_2d_condition.py','models/autoencoders/autoencoder_kl.py']])
entry=next(x for x in j['siblings'] if x['rfilename']=='Juggernaut-XI-byRunDiffusion.safetensors');dest=M/entry['rfilename'];start=time.monotonic()
if not dest.exists():
 part=dest.with_suffix('.partial');h=hashlib.sha256();total=0
 with requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{entry["rfilename"]}',stream=True,timeout=(20,120)) as response:
  response.raise_for_status()
  with part.open('wb') as f:
   for chunk in response.iter_content(8*1024*1024):
    f.write(chunk);h.update(chunk);total+=len(chunk);write('download-progress.json',{'bytes':total,'total':entry['size'],'seconds':time.monotonic()-start})
 assert total==entry['size'] and h.hexdigest()==entry['lfs']['sha256'];part.rename(dest)
assert dest.stat().st_size==entry['size'] and sha(dest)==entry['lfs']['sha256']
v10={'id':'v11','repo':REPO,'revision':REV,'name':entry['rfilename'],'absolute':str(dest),'bytes':entry['size'],'sha256':entry['lfs']['sha256']}
write('manifest.json',[v10]);write('prepare-complete.json',{'seconds':time.monotonic()-start,'sha256':v10['sha256'],'bytes':v10['bytes']})
print('Preparation verified',flush=True)
