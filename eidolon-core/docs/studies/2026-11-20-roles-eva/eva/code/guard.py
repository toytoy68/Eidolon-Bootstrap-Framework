# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : guard.py
# Description : Garde independante thermique/ECC/noyau/secteur E4a
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from common import P,read,save
from pathlib import Path
import os,time,threading,subprocess,signal,re,json,urllib.request
import sampler_rtx,sampler_v100
OUT=Path(os.environ['EVA_OUTPUT']);C=read(P/'config.json');ending=threading.Event();meter_latest={};fault=[]
def meter():
 while not ending.is_set():
  try:
   with urllib.request.urlopen(C['meter_url'],timeout=3) as f:d=json.load(f)
   meter_latest.update(epoch=time.time(),wall_w=float(d['apower']),energy_wh=float(d['aenergy']['total']))
  except Exception:pass
  ending.wait(1)
threading.Thread(target=meter,daemon=True).start()
kernel=subprocess.Popen(['journalctl','-k','-b','-f','-n','0','--no-pager'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
def kr():
 for line in kernel.stdout:
  with (OUT/'kernel.log').open('a') as f:f.write(line)
  if re.search(r'NVRM: Xid|\bBUG:|Oops:|Hardware Error|Machine check|memory failure|hard LOCKUP|soft lockup',line,re.I):fault.append(line.strip())
threading.Thread(target=kr,daemon=True).start()
baseline=None;start=time.time()
try:
 while not (OUT/'guard-stop').exists():
  samples=[sampler_rtx.sample(),sampler_v100.sample()];now=time.time()
  if baseline is None:
   baseline=[{k:v for k,v in x.items() if k.startswith('ecc_')} for x in samples];save(OUT/'ecc-baseline.json',baseline)
  for rank,x in enumerate(samples):
   assert x['gpu_c']<83 and x['cpu_c']<70 and (x['hbm_c'] is None or x['hbm_c']<83),'Temperature threshold'
   assert abs(x['power_limit_w']-200)<.1,'Power cap changed'
   assert x['hw_thermal']!='Active' and x['sw_thermal']!='Active','Thermal throttling'
   assert all(v is None or x[k]==v for k,v in baseline[rank].items()),'ECC changed'
  assert not fault,fault
  assert kernel.poll() is None,'Kernel reader stopped'
  assert now-start<10 or now-meter_latest.get('epoch',0)<8,'Sector telemetry stale'
  status=read(OUT/'status.json');assert now-status['heartbeat']<30,'Stage heartbeat stale'
  row=dict(epoch=now,gpus=samples,meter=dict(meter_latest),phase=status.get('phase'))
  with (OUT/'telemetry.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  save(OUT/'guard-status.json',row);ending.wait(.5)
except BaseException as e:
 save(OUT/'guard-trip.json',dict(epoch=time.time(),reason=repr(e)))
 try:os.kill(int((OUT/'controller.pid').read_text()),signal.SIGTERM)
 except Exception:pass
finally:
 ending.set();kernel.terminate()
 try:kernel.wait(timeout=3)
 except subprocess.TimeoutExpired:kernel.kill();kernel.wait()
