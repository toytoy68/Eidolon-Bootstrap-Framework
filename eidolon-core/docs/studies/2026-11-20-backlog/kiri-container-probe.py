# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : kiri-container-probe.py
# Description : Mesures de conteneurs dans une VM jetable
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,time,json,statistics,random,os
b=Path('/home/toytoy/backlog-20261120')
engines={'docker':['sudo','-n','docker'],'podman':['sudo','-n','podman'],'kiri':['sudo','-n','docker','-H','unix:///run/kiri/docker.sock']}
image='alpine:3.22.2';rows=[];checks=[]
def run(name,args,timeout=30):
 start=time.perf_counter();r=subprocess.run(engines[name]+args,capture_output=True,text=True,timeout=timeout)
 return {'runtime':name,'seconds':time.perf_counter()-start,'exit':r.returncode,'stdout':r.stdout[-1000:],'stderr':r.stderr[-1000:]}
fixture=b/'fixtures';fixture.mkdir(exist_ok=True);(fixture/'input').write_text('eidolon-fixture')
for name in engines:
 checks.append(dict(test='version',**run(name,['version'])))
 checks.append(dict(test='exit37',**run(name,['run','--rm','--network','none',image,'sh','-c','exit 37'])))
 checks.append(dict(test='readonly-bind',**run(name,['run','--rm','--network','none','-v',str(fixture)+':/fixture:ro',image,'sh','-c','test "$(cat /fixture/input)" = eidolon-fixture && ! touch /fixture/forbidden'])))
 checks.append(dict(test='network-none',**run(name,['run','--rm','--network','none',image,'sh','-c','! wget -T 2 -q -O /dev/null http://1.1.1.1 && ! ip route | grep -q default'])))
 checks.append(dict(test='rootfs-readonly',**run(name,['run','--rm','--network','none','--read-only',image,'sh','-c','! touch /forbidden'])))
 checks.append(dict(test='warmup',**run(name,['run','--rm','--network','none',image,'true'])))
(b/'functional.json').write_text(json.dumps(checks,indent=2))
rng=random.Random(20261120)
for i in range(100):
 order=list(engines);rng.shuffle(order)
 for name in order:
  try:r=run(name,['run','--rm','--network','none',image,'true'])
  except subprocess.TimeoutExpired:r={'runtime':name,'exit':'timeout','seconds':30}
  rows.append(dict(iteration=i,**r))
 (b/'startup-raw.json').write_text(json.dumps(rows,indent=2))
summary={}
for name in engines:
 a=sorted(x['seconds']*1000 for x in rows if x['runtime']==name and x['exit']==0)
 summary[name]={'n':len(a),'failures':sum(x['exit']!=0 for x in rows if x['runtime']==name),'median_ms':statistics.median(a),'p95_ms':a[int(.95*(len(a)-1))],'p99_ms':a[int(.99*(len(a)-1))]}
(b/'startup-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({'summary':summary,'functional':checks},indent=2))
