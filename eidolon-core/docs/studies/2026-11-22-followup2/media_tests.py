from pathlib import Path
import subprocess,json,urllib.request,hashlib,os,time
p=Path('/srv/eidolon/ssd/work/followup2-20261122');v=p/'media-venv';base=Path('/srv/eidolon/workspaces/media-20261112/preference-lab/venv')
subprocess.run([str(base/'bin/python'),'-m','venv',str(v)],check=True)
site=next((v/'lib').glob('python*/site-packages'));site.joinpath('shared-media.pth').write_text(str(next((base/'lib').glob('python*/site-packages')))+'\n'+str(Path('/srv/eidolon/workspaces/media-20261112/venv/lib/python3.12/site-packages'))+'\n')
with (p/'media-install.log').open('w') as log:
 r=subprocess.run([str(v/'bin/python'),'-m','pip','install','pytest==9.0.2','opencv-python-headless==4.12.0.88','numpy==2.2.6','onnx==1.19.1','onnxruntime==1.23.2','kaldi-native-fbank==1.21.3'],stdout=log,stderr=subprocess.STDOUT)
assert r.returncode==0
core=Path('/srv/eidolon/ssd/work/followup-20261122/core/eidolon-core');models=p/'identity-models';models.mkdir(exist_ok=True)
manifest=json.loads((core/'docs/identity-models.json').read_text())
for entry in manifest['models'][:2]:
 url=entry['source'].replace('https://github.com/opencv/opencv_zoo/blob/','https://media.githubusercontent.com/media/opencv/opencv_zoo/')
 data=urllib.request.urlopen(url,timeout=60).read();assert hashlib.sha256(data).hexdigest()==entry['sha256_computed'];(models/entry['file']).write_bytes(data)
env=dict(os.environ,PYTHONPATH=str(core/'src'),EIDOLON_IDENTITY_MODELS=str(models),EIDOLON_TEST_V100='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
files=['test_identity_runners.py','test_media_animatediff_probe.py','test_media_codec.py','test_media_flux_dev.py','test_media_sana_probe.py']
t=time.time()
with (p/'media-tests.log').open('w') as log:r=subprocess.run([str(v/'bin/python'),'-m','pytest','-q','-rs','--junitxml='+str(p/'media-tests.xml')]+['tests/'+x for x in files],cwd=core,env=env,stdout=log,stderr=subprocess.STDOUT)
(p/'media-result.json').write_text(json.dumps(dict(exit_code=r.returncode,seconds=time.time()-t)))
with (p/'media-versions.txt').open('w') as out:subprocess.run([str(v/'bin/python'),'-m','pip','freeze'],stdout=out)
