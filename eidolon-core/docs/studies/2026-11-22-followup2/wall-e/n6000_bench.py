# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : n6000_bench.py
# Description : Offline intent qualification, no actuator access
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,subprocess,time,urllib.request,hashlib,statistics,os,threading
P=Path(__file__).resolve().parent
cases=[json.loads(x) for x in (P/'cases.jsonl').read_text().splitlines()]
def save(n,x):
 t=P/(n+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2));t.replace(P/n)
def get(path,data=None,timeout=180):
 req=urllib.request.Request('http://127.0.0.1:18093'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 return urllib.request.urlopen(req,timeout=timeout)
def temp():
 vals=[]
 for x in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
  if (x.parent/'type').read_text().strip() not in ['TCPU','x86_pkg_temp']:continue
  try:vals.append(int(x.read_text())/1000)
  except Exception:pass
 return max(vals) if vals else None
def request(case):
 props={}
 enums={'robot':{'action':['STOP','ATTENDRE','CLARIFIER','AVANCER']},'darme':{'triage':['BLOQUER','VERIFIER','OBSERVER']},'systeme':{'proposition':['MESURER','PROPOSER_REDEMARRAGE','ALERTER','INSPECTER','OBSERVER']}}
 for k,v in (case['expected'] or {}).items():props[k]={'type':'string','enum':enums[case['role']][k]}
 payload=dict(model='local',messages=[dict(role='system',content=case['system']),dict(role='user',content=case['question'])],temperature=0,seed=1234,max_tokens=128,stream=True,stream_options={'include_usage':True},chat_template_kwargs={'enable_thinking':False},reasoning_effort='none',cache_prompt=False)
 if case['expected'] is not None:payload['response_format']={'type':'json_schema','json_schema':{'name':'role_contract','strict':True,'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}}
 start=time.time();first=None;content='';usage={};timings={};finish=None
 with get('/v1/chat/completions',payload) as resp:
  for line in resp:
   if time.time()-start>180:raise TimeoutError('total request deadline')
   if not line.startswith(b'data: '):continue
   raw=line[6:].strip()
   if raw==b'[DONE]':break
   d=json.loads(raw)
   if d.get('usage'):usage=d['usage']
   if d.get('timings'):timings=d['timings']
   for c in d.get('choices',[]):
    token=c.get('delta',{}).get('content','')
    if token:
     if first is None:first=time.time()-start
     content+=token
    if c.get('finish_reason'):finish=c['finish_reason']
 try:strict=None if case['expected'] is None else json.loads(content)==case['expected']
 except Exception:strict=False
 if finish is None or not content:raise RuntimeError('incomplete server response')
 return dict(content=content,strict=strict,ttft_s=first,seconds=time.time()-start,usage=usage,timings=timings,finish=finish,start_epoch=start,end_epoch=time.time())
def cooldown(limit=70,deadline=1200):
 start=time.time()
 if (temp() or 100)>limit:save('status.json',dict(phase='cooldown',model=model['name'],limit_c=limit,timeout_s=deadline))
 while (temp() or 100)>limit:
  if time.time()-start>deadline:raise RuntimeError('cooldown deadline')
  time.sleep(2)
 return time.time()-start

models=json.loads((P/'models.json').read_text());binary=P/'cpu-bin/llama-server'
save('protocol.json',dict(cases=len(cases),seed=1234,max_tokens=128,ctx=4096,threads=3,cpu_only=True,temperature=0,robot_execution=False,stop_cpu_c=85,deadline_s=180,background_services='dashboard and local model remain running; voice inactive at baseline; deployed idle system',energy='RAPL package only, not wall power',corpus='full36 compact role cases and3 chat probes; neutral boilerplate reduced16to1; long-context latency separate; cap2GHz; cooldown70C before model and above75C between requests; limit85C unchanged; initial33 responses retained',binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),case_sha256=hashlib.sha256((P/'cases.jsonl').read_bytes()).hexdigest()))
summary=[]
for model in models:
 cooldown()
 out=P/model['name'];out.mkdir(exist_ok=True)
 path=Path(model['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if model.get('sha256'):assert digest==model['sha256']
 log=(out/'server.log').open('w')
 args=[str(binary),'-m',str(path),'-c','4096','-ngl','0','-t','3','-tb','3','-np','1','--host','127.0.0.1','--port','18093','--jinja','--reasoning-budget','0','--no-webui']
 start=time.time();proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT);rows=[json.loads((out/(c['id']+'.json')).read_text()) for c in cases if (out/(c['id']+'.json')).exists()];resumed=len(rows);existing={r['id'] for r in rows};samples=json.loads((out/'telemetry.json').read_text()) if (out/'telemetry.json').exists() else [];stop=threading.Event()
 def monitor():
  while not stop.wait(1):
   t=temp()
   try:status=Path('/proc',str(proc.pid),'status').read_text();rss=next(x for x in status.splitlines() if x.startswith('VmRSS:'))
   except Exception:rss=None
   samples.append(dict(epoch=time.time(),cpu_c=t,rss=rss,load=os.getloadavg()))
   if t is not None and t>=85:proc.terminate();return
 watcher=threading.Thread(target=monitor);watcher.start()
 try:
  while True:
   assert proc.poll() is None,'server exited'
   assert time.time()-start<180,'load deadline'
   try:
    with get('/health',timeout=2) as f:
     if json.load(f).get('status')=='ok':break
   except Exception:time.sleep(.5)
  load=time.time()-start
  for i,case in enumerate(cases):
   if case['id'] in existing:continue
   if (temp() or 100)>75:cooldown()
   assert proc.poll() is None
   save('status.json',dict(model=model['name'],case=case['id'],done=i,total=len(cases),phase='inference'))
   try:r=dict(id=case['id'],role=case['role'],expected=case['expected'],critical=case['critical'],**request(case))
   except Exception as e:r=dict(id=case['id'],role=case['role'],expected=case['expected'],critical=case['critical'],strict=False,error=repr(e))
   (out/(case['id']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2));rows.append(r)
   if len(rows)>=3 and all('error' in x for x in rows[-3:]):raise RuntimeError('three consecutive request failures')
  result=dict(name=model['name'],sha256=digest,load_seconds=load,resumed_rows=resumed,rows=rows)
 except Exception as e:result=dict(name=model['name'],sha256=digest,error=repr(e),rows=rows)
 finally:
  if proc.poll() is None:proc.terminate()
  try:proc.wait(timeout=15)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  stop.set();watcher.join();log.close()
  (out/'telemetry.json').write_text(json.dumps(samples))
 if any(x['cpu_c'] is not None and x['cpu_c']>=85 for x in samples):
  save('status.json',dict(phase='thermal_abort',model=model['name']));raise RuntimeError('thermal limit reached; entire campaign stopped')
 result.update(start_epoch=min([start]+[r['start_epoch'] for r in rows if 'start_epoch' in r]),end_epoch=time.time(),resume_protocol='70C cooldown / 75C pause / 85C abort; first33 at65C cooldown')
 summary.append(result);save('summary-raw.json',summary)
save('status.json',dict(phase='finished',models=len(summary)))
