#!/usr/bin/python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : wake_cycle.py
# Description : Controlled suspend with RTC fallback and restoration
# Standard    : Eidolon Presentation Standard v1
# Devise      : Local AI • Modular • Reliable • Reproducible
# ==========================================================
# Controlled suspend experiment; RTC fallback and configuration restoration.
from pathlib import Path
import sys,json,subprocess,time,os,re
P=Path('/var/lib/eidolon-qualification-20261122')
B=Path('/home/toytoy/wall-e/qualification-20261122/compact-cool')
mode=sys.argv[1];tag=sys.argv[2]
assert mode in ('deep','s2idle') and re.fullmatch('[a-z0-9-]+',tag)
assert json.loads((B/'status.json').read_text())['phase']=='finished'
assert (P/'cpufreq-restored.json').exists()
alarm=Path('/sys/class/rtc/rtc0/wakealarm')
assert alarm.read_text().strip() in ('','0'),'existing alarm; preserve it'
path=Path('/sys/power/mem_sleep');before=path.read_text().strip()
original=re.search(r'\[([^]]+)\]',before).group(1)
out=P/(tag+'.json')
assert not out.exists()
def cmd(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
d=dict(mode=mode,tag=tag,before=before,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_epoch=time.time())
def save():out.write_text(json.dumps(d,ensure_ascii=False,indent=2))
try:
 path.write_text(mode)
 r=cmd(['/usr/sbin/rtcwake','-m','no','-s','120'])
 assert r.returncode==0,r.stderr
 d['rtc_epoch']=int(alarm.read_text().strip());d['selected']=path.read_text().strip();save()
 d['suspend_request_epoch']=time.time();save()
 r=subprocess.run(['/usr/bin/systemctl','start','systemd-suspend.service'],capture_output=True,text=True,timeout=180)
 d.update(resume_epoch=time.time(),returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
 d['seconds_before_rtc']=d['rtc_epoch']-d['resume_epoch']
except Exception as e:d['error']=repr(e)
finally:
 try:
  if alarm.read_text().strip() in ('','0',str(d.get('rtc_epoch'))):alarm.write_text('0')
 except Exception as e:d['alarm_clear_error']=repr(e)
 path.write_text(original);d['restored_mode']=path.read_text().strip();d['end_epoch']=time.time()
 d['boot_id_after']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 for name in ['pm_wakeup_irq','pm_debug_messages']:
  f=Path('/sys/power')/name
  if f.exists():
   try:d[name]=f.read_text().strip()
   except OSError:pass
 r=cmd(['/usr/bin/journalctl','-b','--since','@'+str(int(d['start_epoch'])),'-u','systemd-suspend.service','--no-pager'])
 d['service_journal']=r.stdout
 r=cmd(['/usr/bin/journalctl','-b','-k','--since','@'+str(int(d['start_epoch'])),'--no-pager'])
 (P/(tag+'-kernel.log')).write_text(r.stdout)
 save()

# Evidence and RTC cleanup are already saved before any network recovery.
net=[]
for attempt in range(3):
 r=cmd(['/usr/bin/ping','-n','-c','1','-W','2','192.168.1.20']);net.append(r.returncode)
 if r.returncode==0:break
 time.sleep(3)
d['network_probe_returncodes']=net
if net[-1]!=0:
 try:
  r=subprocess.run(['/usr/bin/nmcli','--wait','20','connection','up','uuid','bf0849bf-dbe3-4882-82ac-878034510cb3'],capture_output=True,text=True,timeout=30)
  d['network_recovery']=dict(attempted=True,returncode=r.returncode)
 except Exception as e:d['network_recovery']=dict(attempted=True,error=type(e).__name__)
else:d['network_recovery']=dict(attempted=False)
save()
