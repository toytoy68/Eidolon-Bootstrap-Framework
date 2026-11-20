# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : kiri-extended-probe.py
# Description : Contrats conteneurs dans une VM jetable
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,time,json,uuid
b=Path('/home/toytoy/backlog-20261120')
engines={'docker':['sudo','-n','docker'],'podman':['sudo','-n','podman'],'kiri':['sudo','-n','docker','-H','unix:///run/kiri/docker.sock']}
out=[]
def run(name,args):
 r=subprocess.run(engines[name]+args,capture_output=True,text=True,timeout=30)
 return {'runtime':name,'args':args,'exit':r.returncode,'out':r.stdout[-1500:],'err':r.stderr[-1500:]}
for name in engines:
 vol='eidolon-proof-'+name+'-'+uuid.uuid4().hex[:6];container=vol+'-run'
 try:
  out.append(run(name,['volume','create',vol]))
  out.append(run(name,['run','--rm','--network','none','-v',vol+':/data','alpine:3.22.2','sh','-c','echo persistent-fixture > /data/proof']))
  out.append(run(name,['run','--rm','--network','none','-v',vol+':/data:ro','alpine:3.22.2','sh','-c','test "$(cat /data/proof)" = persistent-fixture']))
  out.append(run(name,['run','--rm','--network','none','--memory','32m','--pids-limit','32','--cpus','0.5','alpine:3.22.2','sh','-c','cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/pids.max /sys/fs/cgroup/cpu.max']))
  out.append(run(name,['run','-d','--name',container,'--network','none','alpine:3.22.2','sleep','30']))
  out.append(run(name,['rm','-f',container]))
  out.append(run(name,['inspect',container]))
 finally:out.append(run(name,['volume','rm',vol]))
(b/'extended-functional.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
