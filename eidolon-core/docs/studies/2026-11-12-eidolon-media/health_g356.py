# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : health_g356.py
# Description : Contrôles de clôture du lot Juggernaut Lightning
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import subprocess,json,hashlib,datetime,statistics,zlib,base64
w=Path('/srv/eidolon/workspaces/media-20261112/juggernaut-xi-lightning-g356')
def run(a):
 p=subprocess.run(a,text=True,capture_output=True,timeout=15);return {'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu':run(['nvidia-smi','--query-gpu=index,name,temperature.gpu,temperature.memory,memory.used,power.limit','--format=csv']),'clients':run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv']),'services':run(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama']),'vms':run(['sudo','-n','virsh','-c','qemu:///system','list','--all'])}
f=run(['/srv/eidolon/workspaces/media-20261112/preference-lab/venv/bin/python','-m','pip','freeze']);(w/'runtime-after.txt').write_text(f['stdout']);r['runtime_unchanged']=f['exit']==0 and f['stdout']==(w/'runtime-before.txt').read_text()
r['source_checks']=[]
for name in ['runtime-provenance.json','config-provenance.json']:
 for row in json.loads((w/name).read_text()):r['source_checks'].append({'path':row['path'],'match':hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']})
r['png_checks']=[];rows=[]
for sub in ['run01','run02']:
 for row in json.loads((w/sub/'results.json').read_text()):
  p=w/sub/row['model']/f"{row['index']:02d}-{row['case']}.png";r['png_checks'].append({'model':row['model'],'index':row['index'],'match':hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']});rows.append(row)
assert len(rows)==12 and all(x['match'] for x in r['png_checks']) and all(x['match'] for x in r['source_checks'])
assert r['runtime_unchanged'] and r['services']['exit']==0 and r['clients']['stdout'].strip()=='pid, process_name'
(w/'health-final.json').write_text(json.dumps(r,indent=2))
d={'results':rows,'manifest':json.loads((w/'run02/manifest.json').read_text()),'completion':json.loads((w/'run02/completion.json').read_text()),'telemetry':json.loads((w/'run02/telemetry.json').read_text()),'telemetry_by_model':json.loads((w/'run02/telemetry-by-model.json').read_text()),'loads':json.loads((w/'run02/loads.json').read_text()),'health_final':r,'pipelines':{name:json.loads((w/'run02'/name/'pipeline.json').read_text()) for name in ['xi_lightning']}}
d['completion']['generated_total']=12
b=json.dumps(d,ensure_ascii=False).encode();(w/'raw-report.b64').write_bytes(base64.b64encode(zlib.compress(b)))
print(json.dumps({'raw_chars':len((w/'raw-report.b64').read_bytes()),'raw_sha256':hashlib.sha256(b).hexdigest(),'medians':{name:statistics.median(x['seconds'] for x in rows if x['model']==name and x['condition']=='quality') for name in ['xi_lightning']},'health':r}))
