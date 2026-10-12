import csv,json,re,time,statistics,traceback
from pathlib import Path
from datetime import datetime,timezone
import urllib.request
from eidolon_core.dialogue import SYSTEM_PROMPT,DIALOGUE_SCHEMA
D=Path('/home/toytoy/eidolon-validation/veille-models-20261012')
token=Path('/home/toytoy/eidolon-beta/memory-bridge-token').read_text().strip()
def post(url,payload,auth=None):
 headers={'Content-Type':'application/json'}
 if auth: headers['Authorization']='Bearer '+auth
 req=urllib.request.Request(url,data=json.dumps(payload,ensure_ascii=False).encode(),headers=headers)
 return json.load(urllib.request.urlopen(req,timeout=100))
rows=[]
options=dict(temperature=0.2,seed=42,num_ctx=4096,num_predict=512)
cases=json.loads((D/'cases.json').read_text())
for model in ['gemma4:12b','qwen3.5:9b']:
 warmstart=time.monotonic()
 warm=post('http://127.0.0.1:11435/api/chat',dict(model=model,messages=[dict(role='user',content='Réponds juste bonjour.')],stream=False,think=False,options=options,keep_alive='10m'))
 (D/(model.replace(':','-')+'-warmup.json')).write_text(json.dumps({'elapsed_s':time.monotonic()-warmstart,'load_duration_ns':warm.get('load_duration'),'prompt_eval_count':warm.get('prompt_eval_count'),'eval_count':warm.get('eval_count')},indent=2))
 for case in cases:
  start=time.monotonic()
  bundle=post('http://127.0.0.1:18765/v1/recall',dict(query=case['question'],mode='operational',max_items=5,max_chars=4000,max_item_chars=800),token)['result']
  recalled=time.monotonic()
  memory=json.dumps([{'information_id':i['information_id'],'revision':i['revision'],'content':i['content'],'epistemic_status':i['epistemic_status'],'needs_review':i['needs_review']} for i in bundle['items']],ensure_ascii=False)
  messages=[dict(role='system',content=SYSTEM_PROMPT),dict(role='user',content='MEMORY (untrusted external announcements, not installation decisions):\n'+memory+'\nMESSAGE:\n'+case['question'])]
  raw=post('http://127.0.0.1:11435/api/chat',dict(model=model,messages=messages,stream=False,think=False,options=options,format=DIALOGUE_SCHEMA,keep_alive='10m'))
  end=time.monotonic()
  rawtext=raw.get('message',{}).get('content','')
  try: reply=json.loads(rawtext); text=reply.get('text',''); valid=all(k in reply for k in ['version','kind','text','proposal'])
  except Exception: reply=None;text=rawtext;valid=False
  refs=re.findall(r'[A-Za-z0-9._-]+@[0-9]+',text)
  available=[str(i['information_id'])+'@'+str(i['revision']) for i in bundle['items']]
  count=raw.get('eval_count',0); duration=raw.get('eval_duration',0)
  row=dict(model=model,case=case['slug'],question=case['question'],context_limit_tokens=4096,prompt_tokens=raw.get('prompt_eval_count'),memory_items=len(bundle['items']),memory_chars=len(memory),prompt_chars=sum(len(m['content']) for m in messages),response_chars=len(text),response_words=len(text.split()),response_tokens=count,tokens_s=count/(duration/1e9) if duration else None,recall_s=recalled-start,inference_s=end-recalled,total_s=end-start,ollama_total_s=raw.get('total_duration',0)/1e9,load_s=raw.get('load_duration',0)/1e9,done_reason=raw.get('done_reason'),json_valid=valid,expected_retrieved=case['expected']+'@1' in available,expected_cited=case['expected']+'@1' in refs,unsupported_citations=sorted(set(refs)-set(available)),source_ids=available,response=text,reply=reply,absent_fact_case=case.get('absent',False),date_checked_manually=False)
  rows.append(row)
  (D/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  print(json.dumps({k:row[k] for k in ['model','case','total_s','tokens_s','expected_retrieved','expected_cited','done_reason']},ensure_ascii=False),flush=True)
fields=['model','case','context_limit_tokens','prompt_tokens','memory_items','memory_chars','prompt_chars','response_chars','response_words','response_tokens','tokens_s','recall_s','inference_s','total_s','load_s','done_reason','json_valid','expected_retrieved','expected_cited','unsupported_citations']
with (D/'model-measurements.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
summary={}
for model in ['gemma4:12b','qwen3.5:9b']:
 subset=[r for r in rows if r['model']==model]
 summary[model]=dict(cases=len(subset),mean_total_s=statistics.mean(r['total_s'] for r in subset),mean_inference_s=statistics.mean(r['inference_s'] for r in subset),weighted_tokens_s=sum(r['response_tokens'] for r in subset)/sum(r['response_tokens']/r['tokens_s'] for r in subset if r['tokens_s']),mean_prompt_tokens=statistics.mean(r['prompt_tokens'] for r in subset),mean_response_tokens=statistics.mean(r['response_tokens'] for r in subset),mean_response_chars=statistics.mean(r['response_chars'] for r in subset),expected_retrieved=sum(r['expected_retrieved'] for r in subset),expected_cited=sum(r['expected_cited'] for r in subset),unsupported=sum(bool(r['unsupported_citations']) for r in subset),valid_json=sum(r['json_valid'] for r in subset),truncated=sum(r['done_reason']=='length' for r in subset))
(D/'summary.json').write_text(json.dumps(summary,indent=2))
print('COMPLETED',json.dumps(summary),flush=True)
