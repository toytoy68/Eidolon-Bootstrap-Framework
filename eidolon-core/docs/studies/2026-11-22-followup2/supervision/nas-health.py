#!/usr/bin/python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : nas-health.py
# Description : Independent NAS observations; local journal only
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,subprocess,urllib.request,time,datetime,fcntl,os,socket
os.umask(0o077)
p=Path.home()/'archive/independent-health';p.mkdir(mode=0o700,exist_ok=True)
lock=(p/'monitor.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
now=time.time();out=dict(schema='eidolon-nas-health/1',epoch=now,source=socket.gethostname(),external_notification=False)
for name,ip in [('switch','192.168.1.239'),('x399','192.168.1.51')]:
 r=subprocess.run(['/usr/bin/ping','-n','-c','1','-W','2',ip],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=4)
 out[name+'_icmp']=r.returncode==0
try:
 req=urllib.request.Request('http://192.168.1.197/rpc/PM1.GetStatus?id=0',headers={'Cache-Control':'no-cache'})
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(req,timeout=3) as f:d=json.load(f)
 w=d['apower'];assert type(w) in (int,float) and 0<=w<10000;out['x399_power_w']=w
except Exception as e:out['power_error']=type(e).__name__
archive=Path.home()/'archive/network/latest-summary.json';out['archive_age_s']=now-archive.stat().st_mtime if archive.exists() else None
previous={}
try:previous=json.loads((p/'latest.json').read_text())
except (OSError,ValueError):pass
out['switch_failures']=0 if out['switch_icmp'] else int(previous.get('switch_failures',0))+1
out['switch_state']='REACHABLE' if out['switch_icmp'] else 'UNREACHABLE_CONFIRMED' if out['switch_failures']>=3 else 'UNREACHABLE_PENDING'
if 'x399_power_w' not in out:out['x399_state']='POWER_UNKNOWN'
elif out['x399_power_w']<5:out['x399_state']='OFF_BY_SHELLY'
elif not out['x399_icmp']:out['x399_state']='POWERED_BUT_UNREACHABLE'
else:out['x399_state']='POWERED_AND_REACHABLE'
out['archive_state']='PAUSED_HOST_OFF' if out['x399_state']=='OFF_BY_SHELLY' else 'FRESH' if out['archive_age_s'] is not None and out['archive_age_s']<1200 else 'STALE_OR_ABSENT'
r=subprocess.run(['/usr/sbin/zfs','list','-H','-p','-t','snapshot','-o','name,creation','-r','tank/eidolon-darme-archive'],capture_output=True,text=True,timeout=8)
out['snapshots']=[dict(name=x.split()[0],epoch=int(x.split()[1])) for x in r.stdout.splitlines()] if r.returncode==0 else None
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d');raw=json.dumps(out,sort_keys=True)
with (p/(stamp+'.jsonl')).open('a') as f:f.write(raw+'\n')
tmp=p/'latest.tmp';tmp.write_text(raw+'\n');tmp.replace(p/'latest.json');print(raw)
