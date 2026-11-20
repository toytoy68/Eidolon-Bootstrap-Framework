# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : health_g357.py
# Description : Validation des sorties et de la préservation G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import subprocess,json,hashlib,datetime,zlib,base64,statistics
W=Path('/srv/eidolon/workspaces/media-20261112/sdxl-inpaint-g357');R=W.parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(a):
 p=subprocess.run(a,text=True,capture_output=True,timeout=15);return {'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
h={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu':run(['nvidia-smi','--query-gpu=index,name,temperature.gpu,temperature.memory,memory.used,power.limit','--format=csv']),'clients':run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv']),'services':run(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama']),'vms':run(['sudo','-n','virsh','-c','qemu:///system','list','--all'])}
f=run([str(R/'preference-lab/venv/bin/python'),'-m','pip','freeze']);(W/'runtime-after.txt').write_text(f['stdout']);h['runtime_unchanged']=f['exit']==0 and f['stdout']==(W/'runtime-before.txt').read_text();assert h['runtime_unchanged'] and h['services']['exit']==0 and h['clients']['stdout'].strip()=='pid, process_name'
h['source_checks']=[{'path':x['path'],'match':sha(Path(x['path']))==x['sha256']} for x in json.loads((W/'runtime-provenance.json').read_text())];assert all(x['match'] for x in h['source_checks'])
inputs=json.loads((W/'inputs.json').read_text());assert sha(Path(inputs['reference']))==inputs['reference_sha256']
for x in inputs['cases']:
 assert sha(Path(x['source']))==x['source_sha256'];assert sha(W/'inputs'/f"{x['case']}-source.png")==x['copied_sha256'];assert sha(W/'inputs'/f"{x['case']}-mask.png")==x['mask_sha256']
rows=[];checks=[]
for sub in ['run01','run02']:
 for row in json.loads((W/sub/'results.json').read_text()):
  for suffix,key in [(row['case'],'sha256'),('raw','raw_sha256'),('source','source_sha256'),('mask','mask_sha256')]:
   p=W/sub/'sdxl_inpaint'/f"{row['index']:02d}-{suffix}.png";checks.append({'path':str(p),'match':sha(p)==row[key]})
  rows.append(row)
assert len(rows)==12 and all(x['match'] for x in checks) and all(x['unet_calls']==19 for x in rows);h['png_checks']=checks
c=json.loads((W/'run02/completion.json').read_text());assert c['repeat_same_pixels']=={'sdxl_inpaint':True} and c['raw_repeat_same_pixels']
for x in rows:
 if x['preservation']['outside_pixels']:assert x['preservation']['composite_outside_max']==0
assert next(x for x in rows if x['index']==10)['sha256']==next(x for x in rows if x['index']==10)['source_sha256']
model=json.loads((W/'manifest.json').read_text());h['config_checks']=[{'path':x['path'],'match':sha(Path(x['path']))==x['sha256']} for x in model['files'] if not x['name'].endswith('.safetensors')];assert all(x['match'] for x in h['config_checks'])
(W/'health-final.json').write_text(json.dumps(h,indent=2))
d={'results':rows,'inputs':inputs,'model':model,'health_final':h,'completion':c,'manifest':json.loads((W/'run02/manifest.json').read_text()),'loads':json.loads((W/'run02/loads.json').read_text()),'telemetry':json.loads((W/'run02/telemetry.json').read_text()),'pipeline':json.loads((W/'run02/sdxl_inpaint/pipeline.json').read_text())}
b=json.dumps(d,ensure_ascii=False).encode();(W/'raw-report.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(json.dumps({'chars':len((W/'raw-report.b64').read_bytes()),'sha256':hashlib.sha256(b).hexdigest(),'median_seconds':statistics.median(x['seconds'] for x in rows if x['condition']=='quality'),'telemetry':d['telemetry'],'health':h['gpu']}))
