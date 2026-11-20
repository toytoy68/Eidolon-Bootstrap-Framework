# Eidolon Core Technologies (ECT) - isolated local role benchmark
from pathlib import Path
import json,subprocess,os,time,urllib.request,hashlib,signal,re,statistics
P=Path(__file__).resolve().parent;B=P.parent/'backlog-20261120'
env=dict(os.environ,LD_LIBRARY_PATH=str(B/'cuda129/lib'))
cases=[x for x in json.loads((P/'cases.json').read_text()) if x['expected'] is not None]
models=[dict(name=Path(d['file']).stem,path=d['file']) for d in map(json.loads,(P/'downloads.jsonl').read_text().splitlines()) if d.get('verified')]
models += [dict(name=n,path=str(p)) for n,p in [('LFM3-1.7B',B/'candidates/LFM3-1.7B-Q4_K_M.gguf'),('Prism-Ternary-2B-Q2_0',B/'candidates/Ternary-Bonsai-2-2B-Q2_0.gguf'),('Qwen2.5-1.5B',P.parent/'campaign-20261120/qwen2.5-1.5b-instruct-q4_k_m.gguf')]]
root=Path('/srv/eidolon/models/ollama')
for f in (root/'manifests').rglob('*'):
 if f.is_file() and 'Qwen3-4B-Element8-Eva-Hermes-Heretic' in str(f):
  d=json.loads(f.read_text());layer=next(x for x in d['layers'] if x['mediaType']=='application/vnd.ollama.image.model')
  models.append(dict(name='Eva-source-Q4_K_M',path=str(root/'blobs'/layer['digest'].replace(':','-'))));break
assert len(models)==8
(P/'model-paths.json').write_text(json.dumps(models,indent=2))
def save(name,obj):
 f=P/name;tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(f)
def get(url,payload=None,timeout=15):
 data=None if payload is None else json.dumps(payload).encode()
 return urllib.request.urlopen(urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'}),timeout=timeout)
def meter():
 try:
  with get('http://LAN-REDACTED/rpc/PM1.GetStatus?id=0',timeout=3) as f:
   d=json.load(f);return dict(epoch=time.time(),watts=d['apower'],wh=d['aenergy']['total'])
 except Exception as e:return dict(error=repr(e))
def health():
 s=subprocess.check_output(['nvidia-smi','--query-gpu=temperature.gpu,power.draw,memory.used,ecc.errors.corrected.volatile.total,ecc.errors.uncorrected.volatile.total','--format=csv,noheader,nounits'],text=True)
 rows=[[float(t.strip()) for t in row.split(',')] for row in s.strip().splitlines()]
 assert all(x[0]<80 for x in rows),'GPU temperature'
 assert all(x[3:]==baseline[i][3:] for i,x in enumerate(rows)),'ECC changed'
 return rows
baseline=[[float(t.strip()) for t in row.split(',')] for row in subprocess.check_output(['nvidia-smi','--query-gpu=temperature.gpu,power.draw,memory.used,ecc.errors.corrected.volatile.total,ecc.errors.uncorrected.volatile.total','--format=csv,noheader,nounits'],text=True).strip().splitlines()]
assert all(x[2]<100 for x in baseline),'GPU already occupied'
save('pre-structured.json',dict(gpu=baseline,meter=meter(),case_sha256=hashlib.sha256((P/'cases.json').read_bytes()).hexdigest(),epoch=time.time()))
def equal(a,b):return json.dumps(a,sort_keys=True,ensure_ascii=False)==json.dumps(b,sort_keys=True,ensure_ascii=False)
def score(content,expected):
 if expected is None:return dict(strict=None,semantic=None)
 try:strict=equal(json.loads(content),expected)
 except Exception:strict=False
 extracted=content.split('</think>')[-1].strip()
 try:
  start=extracted.index('{');obj=json.JSONDecoder().raw_decode(extracted[start:])[0];semantic=equal(obj,expected)
 except Exception:semantic=False
 return dict(strict=strict,semantic=semantic)
def request(case):
 payload=dict(model='local',messages=[dict(role='system',content=case['system']),dict(role='user',content=case['question'])],temperature=0,seed=1234,max_tokens=512,stream=True,stream_options=dict(include_usage=True),chat_template_kwargs=dict(enable_thinking=False),reasoning_effort='none',reasoning_format='deepseek',cache_prompt=False)
 properties={}
 enums={'robot':{'action':['STOP','ATTENDRE','CLARIFIER','AVANCER']},'darme':{'triage':['BLOQUER','VERIFIER','OBSERVER']},'systeme':{'proposition':['MESURER','PROPOSER_REDEMARRAGE','ALERTER','INSPECTER','OBSERVER']}}
 for key,value in case['expected'].items():
  kind='null' if value is None else 'boolean' if isinstance(value,bool) else 'integer' if isinstance(value,int) else 'string'
  properties[key]={'type':['number','null'] if value is None else kind}
  if case['role'] in enums:properties[key]['enum']=enums[case['role']][key]
 payload['response_format']={'type':'json_schema','json_schema':{'name':'role_contract','strict':True,'schema':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}}}
 start=time.perf_counter();first=None;thought=None;content='';reason='';usage={};finish=None;timings={}
 with get('http://127.0.0.1:18091/v1/chat/completions',payload,90) as resp:
  for line in resp:
   if time.perf_counter()-start>90:raise TimeoutError('request total deadline')
   if not line.startswith(b'data: '):continue
   raw=line[6:].strip()
   if raw==b'[DONE]':break
   d=json.loads(raw)
   if d.get('usage'):usage=d['usage']
   if d.get('timings'):timings=d['timings']
   for choice in d.get('choices',[]):
    delta=choice.get('delta',{})
    if delta.get('content'):
     if first is None:first=time.perf_counter()-start
     content+=delta['content']
    if delta.get('reasoning_content'):
     if thought is None:thought=time.perf_counter()-start
     reason+=delta['reasoning_content']
    if choice.get('finish_reason'):finish=choice['finish_reason']
 return dict(content=content,reasoning=reason,ttft_content_s=first,ttft_reasoning_s=thought,seconds=time.perf_counter()-start,usage=usage,timings=timings,finish_reason=finish,**score(content,case['expected']))

summary=[]
try:
 for model in models:
  name=model['name'];out=P/'structured'/name;out.mkdir(parents=True,exist_ok=False)
  save('structured-status.json',dict(model=name,phase='loading',epoch=time.time()))
  args=[str(B/'build-cuda129-patched-v1/bin/llama-server'),'-m',model['path'],'-c','4096','-ngl','99','-dev','CUDA0','-t','8','-np','1','-fa','on','--host','127.0.0.1','--port','18091','--jinja','--reasoning-budget','0','--no-webui']
  start=time.time();proc=subprocess.Popen(args,env=env,stdout=(out/'server.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
  rows=[];before=meter()
  try:
   while True:
    assert proc.poll() is None,'server exited'
    assert time.time()-start<180,'load timeout'
    try:
     with get('http://127.0.0.1:18091/health',timeout=2) as f:
      if json.load(f).get('status')=='ok':break
    except Exception:time.sleep(.3)
   load_s=time.time()-start
   with get('http://127.0.0.1:18091/props') as f:save('structured/'+name+'/props.json',json.load(f))
   for i,case in enumerate(cases):
    save('structured-status.json',dict(model=name,case=case['id'],done=i,total=len(cases),phase='inference',epoch=time.time()))
    h=health()
    try:row=dict(id=case['id'],role=case['role'],critical=case['critical'],expected=case['expected'],**request(case),gpu=h)
    except Exception as e:row=dict(id=case['id'],role=case['role'],critical=case['critical'],expected=case['expected'],strict=False,semantic=False,error=repr(e))
    (out/(case['id']+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2));rows.append(row)
   result=dict(model=name,load_seconds=load_s,meter_before=before,meter_after=meter(),roles={})
   for role in ['robot','darme','systeme','raisonnement']:
    rr=[x for x in rows if x['role']==role]
    result['roles'][role]=dict(n=len(rr),strict=sum(bool(x['strict']) for x in rr),semantic=sum(bool(x['semantic']) for x in rr),critical_failures=[x['id'] for x in rr if x['critical'] and not x['strict']],truncated=sum(x.get('finish_reason')=='length' for x in rr))
   values=[x['ttft_content_s'] for x in rows if x.get('ttft_content_s') is not None]
   result.update(ttft_content_median_s=statistics.median(values) if values else None,request_median_s=statistics.median([x['seconds'] for x in rows if 'seconds'in x]),errors=[x for x in rows if 'error'in x])
  except Exception as e:result=dict(model=name,error=repr(e),rows_completed=len(rows))
  finally:
   if proc.poll() is None:proc.terminate()
   try:proc.wait(timeout=15)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  summary.append(result);save('structured-summary.json',summary)
 save('structured-status.json',dict(phase='finished',models=len(summary),epoch=time.time()))
except BaseException as e:
 save('structured-status.json',dict(phase='failed',error=repr(e),epoch=time.time()));raise
