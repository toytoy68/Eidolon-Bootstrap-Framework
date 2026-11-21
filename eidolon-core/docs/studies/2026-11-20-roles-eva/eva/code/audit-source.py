# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : worker.py
# Description : Evaluation independante, sans DDP ni entrainement
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import os,time,json,math,hashlib,random
from pathlib import Path
from common import P,read,save,sha,item_path
RANK=int(os.environ['EVA_RANK']);OUT=Path(os.environ['EVA_OUTPUT']);MODE=os.environ['EVA_DIAGNOSTIC'];START=time.time()
def progress(stage,**kw):save(OUT/f'progress-rank{RANK}.json',dict(stage=stage,rank=RANK,epoch=time.time(),mode=MODE,**kw))
progress('importing')
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
from peft import PeftModel,prepare_model_for_kbit_training,set_peft_model_state_dict,get_peft_model_state_dict
from safetensors.torch import load_file
import eva_boundary_probes as probes
from curriculum import grade,CANARIES
torch.set_num_threads(4);torch.manual_seed(1234);random.seed(1234);torch.set_grad_enabled(False)
assert torch.cuda.device_count()==1 and torch.cuda.get_device_capability(0)==(7,0)
C=read(P/'config.json');SYSTEM=read(P/'system.json')['system'];CANDIDATES=read(P/'candidates.json')
assert os.environ['CUDA_VISIBLE_DEVICES']==C['uuids'][RANK]
proof=read(OUT/'integrity-proof.json');assert proof['passed'] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for n,h in read(P/'launch-manifest.json').items():assert sha(P/n)==h,n
tok=AutoTokenizer.from_pretrained(str(P/'source-model'),local_files_only=True,trust_remote_code=False)
if tok.pad_token_id is None:tok.pad_token_id=tok.eos_token_id
tok.padding_side='left'
progress('loading_model')
q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
base=AutoModelForCausalLM.from_pretrained(str(P/'source-model'),local_files_only=True,trust_remote_code=False,quantization_config=q,torch_dtype=torch.float16,device_map={'':0},attn_implementation='sdpa')
base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
model=None;STATE=None
def adapter(c):
 global model,STATE
 progress('adapter_loading',candidate=c['name']);f=Path(c['path'])/'adapter_model.safetensors'
 hs=[sha(f),sha(f)];assert hs==[c['sha256']]*2
 raw=load_file(str(f),device='cpu')
 if model is None:model=PeftModel.from_pretrained(base,c['path'],is_trainable=False)
 else:
  r=set_peft_model_state_dict(model,raw);assert not r.unexpected_keys
 model.requires_grad_(False);model.eval();model.config.use_cache=False
 assert not any(x.requires_grad for x in model.parameters())
 STATE=hashlib.sha256(b''.join(v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes() for k,v in sorted(get_peft_model_state_dict(model).items()))).hexdigest()
 expected_state=hashlib.sha256(b''.join(v.contiguous().view(torch.uint8).numpy().tobytes() for k,v in sorted(raw.items()))).hexdigest();assert STATE==expected_state,'Adapter tensor contents mismatch'
 if c['name']=='parent':assert STATE=='0883c80e45904bdcb85aa6a27d20e921eea7a6bf5574990375e51835d4163a52'
 save(OUT/f'identity-{c["name"]}-rank{RANK}.json',dict(candidate=c,adapter_state_sha256=STATE,adapter_hashes=hs,gpu_uuid=C['uuids'][RANK],precision='FP16/NF4 doublequant',base_model_loads_per_worker=1,training=False))
def identity(c,batch,ids,kind):
 return dict(adapter_sha256=c['sha256'],adapter_state_sha256=STATE,gpu_uuid=C['uuids'][RANK],precision='FP16/NF4 doublequant',batch_size=batch,batch_ids=ids,kind=kind,system_sha256=sha(P/'system.json'),source_revision=C['source_revision'],max_new_tokens=384,do_sample=False)
def prompt(ex):return tok.apply_chat_template([dict(role='system',content=ex.get('system',SYSTEM)),dict(role='user',content=ex['question'])],tokenize=False,add_generation_prompt=True,enable_thinking=False)
def gen(examples,stage,c,batchsize):
 rows=[];beg=time.time()
 for offset in range(0,len(examples),batchsize):
  chunk=examples[offset:offset+batchsize];ids=[x['id'] for x in chunk];ident=identity(c,batchsize,ids,stage)
  ident['systems_sha256']=hashlib.sha256(json.dumps([x.get('system',SYSTEM) for x in chunk],ensure_ascii=False).encode()).hexdigest()
  existing={}
  for ex in chunk:
   f=item_path(OUT,stage,c['name'],ex['id'])
   if f.exists():
    d=read(f);assert d['identity']==ident and d['question']==ex['question'] and d['expected']==ex['expected'],'Resume identity mismatch'
    existing[ex['id']]=d
  if len(existing)==len(chunk):rows.extend(existing[x['id']] for x in chunk);continue
  progress('generation',candidate=c['name'],stage_name=stage,done=offset,total=len(examples),batch=batchsize)
  tick=time.time();inputs=tok([prompt(x) for x in chunk],add_special_tokens=False,padding=True,return_tensors='pt').to('cuda')
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
   output=model.generate(**inputs,max_new_tokens=384,do_sample=False,use_cache=True,pad_token_id=tok.pad_token_id,eos_token_id=tok.eos_token_id)
  torch.cuda.synchronize();seconds=time.time()-tick
  for j,ex in enumerate(chunk):
   seq=output[j,inputs['input_ids'].shape[1]:].tolist();limited=tok.eos_token_id not in seq and len(seq)>=384
   if tok.eos_token_id in seq:seq=seq[:seq.index(tok.eos_token_id)+1]
   text=tok.decode(seq,skip_special_tokens=True)
   row=dict(id=ex['id'],question=ex['question'],expected=ex['expected'],response=text,candidate=c['name'],rank=RANK,identity=ident,generated_tokens=len(seq),truncated=limited,batch_seconds=seconds,input_tokens=int(inputs['attention_mask'][j].sum()),fresh_generation=True,epoch=time.time())
   for k in ['kind','stratum','group','family','pair','time_key']:
    if k in ex:row[k]=ex[k]
   if ex.get('kind')!='SG' and ex['expected'] is not None:
    evaluation=grade(text,ex['expected'])
    if ex['expected']['unite']=='heure':
     evaluation['content_correct']=bool(probes._correct(probes._last_object(text),ex['expected']));evaluation['exact']=evaluation['exact'] and evaluation['content_correct']
    row.update(evaluation=evaluation,format=probes.format_of(text),invalid_claims=probes.invalid_claims(text))
   if ex['id'] in existing:assert text==existing[ex['id']]['response'],'Resume batch result changed'
   else:save(item_path(OUT,stage,c['name'],ex['id']),row)
   rows.append(row)
  del output,inputs
 assert len(rows)==len(examples) and len({x['id'] for x in rows})==len(rows)
 save(OUT/f'{stage}-{c["name"]}-rank{RANK}.json',dict(rows=rows,seconds=time.time()-beg,batch_size=batchsize));return rows
try:
 adapter(CANDIDATES[0]);candidate=CANDIDATES[0]
 xs=[x for i,x in enumerate(read(P/'selection.json')) if i%2==RANK]
 baseline=gen(xs,'qualification',candidate,16)
 ref=read(P.parent/'eva-learning-cycle11-diversity-20261111-4c1f2095/baseline'/f'eval-selection-parent-rank{RANK}.json')['rows']
 assert [x['id'] for x in ref]==[x['id'] for x in baseline]
 changed=[x['id'] for x,y in zip(baseline,ref) if x['response']!=y['response']]
 save(OUT/f'baseline-equivalence-rank{RANK}.json',dict(passed=not changed,changed=changed,n=len(xs),same_gpu_batch16=True,independent_load=True))
 assert not changed,'Fresh baseline changed, no probes'
 allp=read(P/'boundary-probes.json');sg=[x for i,x in enumerate([q for q in allp if q['kind']=='SG']) if i%2==RANK]
 gen(sg,'sign',candidate,16);save(OUT/f'sign-ready-rank{RANK}.json',dict(passed=True,epoch=time.time()))
 deadline=time.time()+180
 while not (OUT/'sign-gate.json').exists():
  assert time.time()<deadline;progress('waiting_sign_gate');time.sleep(.5)
 gate=read(OUT/'sign-gate.json')
 pairs=list(dict.fromkeys(x['pair'] for x in allp if x['kind']!='SG'))
 for kind in ['ZS','FA','FB','FC']:
  if kind=='FB' and not gate['allow_B']:continue
  mine=[x for x in allp if x['kind']==kind and pairs.index(x['pair'])%2==RANK]
  gen(mine,'boundary-'+kind,candidate,16)
 progress('finished',training=False,seconds=time.time()-START)
except BaseException as e:
 save(OUT/f'failure-rank{RANK}.json',dict(reason=repr(e),epoch=time.time()));progress('failed',reason=repr(e));raise
