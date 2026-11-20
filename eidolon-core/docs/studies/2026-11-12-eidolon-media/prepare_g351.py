# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : prepare_g351.py
# Description : Préparation isolée de FLUX Schnell GGUF Q8
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import requests,json,hashlib,subprocess,shutil,time
ROOT=Path('/srv/eidolon/workspaces/media-20261112');W=ROOT/'flux-q8-g351'
M=Path('/srv/eidolon/data/media-models-20261113/flux-schnell-q8');M.mkdir(exist_ok=True)
PY=ROOT/'preference-lab/venv/bin/python'
REPO='city96/FLUX.1-schnell-gguf';REV='f495746ed9c5efcf4661f53ef05401dceadc17d2'
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def get(url):
 r=requests.get(url,timeout=25);r.raise_for_status();return r
def write(n,d):(W/n).write_text(json.dumps(d,indent=2))
j=get(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true').json();assert j['sha']==REV and not j['gated'];write('author-metadata.json',j)
readme=get(f'https://huggingface.co/{REPO}/resolve/{REV}/README.md').content
entry=next(x for x in j['siblings'] if x['rfilename']=='README.md')
assert hashlib.sha1(b'blob '+str(len(readme)).encode()+b'\0'+readme).hexdigest()==entry['blobId']
(W/'model-README.md').write_bytes(readme)
shutil.copy2(ROOT/'flux-schnell-g339/BFL-LICENSE-SCHNELL.txt',W/'BFL-LICENSE-SCHNELL.txt')
source=json.loads((ROOT/'flux-schnell-g339/manifest.json').read_text());shared=[]
for row in source[1:]:
 p=Path('/srv/eidolon/models/media-20261112/flux-g332')/row['name']
 assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256']
 shared.append({**row,'absolute':str(p)})
write('shared-files.json',shared)
(W/'runtime-before.txt').write_text(subprocess.check_output([str(PY),'-m','pip','freeze'],text=True))
pkg=get('https://pypi.org/pypi/gguf/0.17.1/json').json();wheel=next(x for x in pkg['urls'] if x['filename'].endswith('py3-none-any.whl'))
data=get(wheel['url']).content;assert hashlib.sha256(data).hexdigest()==wheel['digests']['sha256']
path=W/wheel['filename'];path.write_bytes(data);write('gguf-wheel.json',{'name':wheel['filename'],'sha256':wheel['digests']['sha256'],'bytes':len(data),'requires_dist':pkg['info']['requires_dist']})
subprocess.run([str(PY),'-m','pip','install','--no-deps','--no-index','--target',str(W/'vendor'),str(path)],check=True)
row=next(x for x in j['siblings'] if x['rfilename']=='flux1-schnell-Q8_0.gguf');dest=M/row['rfilename'];started=time.monotonic()
if not dest.exists():
 part=dest.with_suffix('.partial');h=hashlib.sha256();total=0
 with requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{row["rfilename"]}',stream=True,timeout=(20,120)) as r:
  r.raise_for_status()
  with part.open('wb') as f:
   for chunk in r.iter_content(8*1024*1024):
    f.write(chunk);h.update(chunk);total+=len(chunk)
    write('download-progress.json',{'bytes':total,'total':row['size'],'seconds':time.monotonic()-started})
 assert total==row['size'] and h.hexdigest()==row['lfs']['sha256'];part.rename(dest)
assert dest.stat().st_size==row['size'] and digest(dest)==row['lfs']['sha256']
record={'repo':REPO,'revision':REV,'name':row['rfilename'],'path':row['rfilename'],'absolute':str(dest),'bytes':row['size'],'sha256':row['lfs']['sha256']}
write('downloads.json',[record]);write('manifest.json',[record]+shared)
write('prepare-complete.json',{'revision':REV,'sha256':record['sha256'],'bytes':record['bytes'],'seconds':time.monotonic()-started})
print('Preparation verified',flush=True)
