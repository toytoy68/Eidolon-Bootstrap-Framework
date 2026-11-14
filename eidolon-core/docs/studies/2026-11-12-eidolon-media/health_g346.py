# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : health_g346.py
# Description : Contrôles de clôture du lot G346
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import subprocess,json,hashlib,datetime,statistics,zlib,base64
w=Path('/srv/eidolon/workspaces/media-20261112/sd35-medium-g346')
def run(a):
 p=subprocess.run(a,text=True,capture_output=True,timeout=15);return {'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu':run(['nvidia-smi','--query-gpu=index,name,temperature.gpu,temperature.memory,memory.used,power.limit','--format=csv']),'clients':run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv']),'services':run(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama']),'vms':run(['sudo','-n','virsh','-c','qemu:///system','list','--all'])}
f=run(['/srv/eidolon/workspaces/media-20261112/klein-g340/venv/bin/python','-m','pip','freeze']);(w/'runtime-after.txt').write_text(f['stdout']);r['runtime_unchanged']=f['exit']==0 and f['stdout']==(w/'runtime-before.txt').read_text()
r['png_checks']=[];rows=[]
for sub in ['run03','run04']:
 for row in json.loads((w/sub/'results.json').read_text()):
  p=w/sub/f"{row['index']:02d}-{row['case']}.png";r['png_checks'].append({'index':row['index'],'match':hashlib.sha256(p.read_bytes()).hexdigest()==row['png_sha256']});rows.append(row)
assert all(x['match'] for x in r['png_checks']) and len(r['png_checks'])==12
assert r['runtime_unchanged'] and r['services']['exit']==0
(w/'health-final.json').write_text(json.dumps(r,indent=2))
d={'results':rows,'manifest':json.loads((w/'run04/manifest.json').read_text()),'completion':json.loads((w/'run04/completion.json').read_text()),'telemetry':json.loads((w/'run04/telemetry.json').read_text()),'health_final':r};d['completion']['generated_total']=12
b=json.dumps(d,ensure_ascii=False).encode();(w/'raw-report.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(json.dumps({'raw_report_chars':len((w/'raw-report.b64').read_bytes()),'raw_sha256':hashlib.sha256(b).hexdigest(),'native_median':statistics.median(x['seconds'] for x in rows if x['condition']=='quality'),'health':r}))
