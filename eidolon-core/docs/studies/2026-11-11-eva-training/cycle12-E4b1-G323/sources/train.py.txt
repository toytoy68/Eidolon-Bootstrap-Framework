# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : train.py
# Description : E4b1, apprentissage des pieces et evaluation hors DDP
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Only training in DDP. All generation is performed in independent processes."""
import os,time,json,pathlib,hashlib,random,math,contextlib,datetime,ast,shutil
ROOT=pathlib.Path(__file__).resolve().parent
MODE=os.environ.get('EVA_MODE','train');PHASE=int(os.environ.get('EVA_PHASE','1'));assert PHASE in [1,2]
RANK=int(os.environ['LOCAL_RANK']);WORLD=int(os.environ['WORLD_SIZE'])
assert WORLD in [1,2]
SINGLE=WORLD==1
P=pathlib.Path(os.environ['EVA_OUTPUT'])
P.mkdir(exist_ok=True)
def save(n,d):
 q=P/(n+'.'+str(RANK)+'.tmp')
 with q.open('w') as f:json.dump(d,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 q.replace(P/n)
def append(n,d):
 with (P/n).open('a') as f:f.write(json.dumps(d,ensure_ascii=False)+'\n')
def progress(stage,**kw):save('progress-rank'+str(RANK)+'.json',dict(stage=stage,epoch=time.time(),rank=RANK,**kw))
progress('importing')
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
from peft import prepare_model_for_kbit_training,PeftModel,get_peft_model_state_dict,set_peft_model_state_dict
from safetensors.torch import load_file
from curriculum import grade,CANARIES
C=json.loads((ROOT/'config.json').read_text())
assert torch.cuda.device_count()==WORLD==2
torch.cuda.set_device(RANK);torch.set_num_threads(4);torch.manual_seed(1234);random.seed(1234)
assert torch.cuda.get_device_capability(RANK)==(7,0)
dtype=torch.float16
dist.init_process_group('nccl',timeout=datetime.timedelta(minutes=30),device_id=torch.device('cuda',RANK))
proof=json.loads((P/'integrity-proof.json').read_text());assert proof['passed'] and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for n,h in json.loads((ROOT/'launch-manifest.json').read_text()).items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
dist.barrier(device_ids=[RANK])
test=torch.tensor([RANK+1.],device='cuda');dist.all_reduce(test);assert float(test)==3.
save('nccl-rank'+str(RANK)+'.json',dict(passed=True,result=float(test),backend=dist.get_backend(),world_size=WORLD,nccl_version=torch.cuda.nccl.version()))
progress('tokenizer')
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'source-model'),local_files_only=True,trust_remote_code=False)
if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
# Reuse the validated prompt and masking/packing function verbatim.
old=ROOT/'encoding-source.py'
tree=ast.parse(old.read_text())
nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='encode') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in n.targets))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(old),'exec'))
data=json.loads((ROOT/'dataset.json').read_text())
assert hashlib.sha256((ROOT/'dataset.json').read_bytes()).hexdigest()==json.loads((ROOT/'lineage.json').read_text())['dataset_sha256']
train=data['train'];valid=data['validation'];heldout=data['heldout']
from packing import assemble
plans=json.loads((ROOT/'pack-plan.json').read_text())
train_batches,train_info=assemble(train,plans[0],encode,torch,tokenizer.pad_token_id)
second_batches,second_info=assemble(data['train_second'],plans[1],encode,torch,tokenizer.pad_token_id)
valid_info=dict(used_for_training=False)
assert train_info['supervised_tokens']==second_info['supervised_tokens']==60109
assert len(train_batches)%2==len(second_batches)%2==0
train_batches_by_epoch=[train_batches,second_batches]
save('dataset-statistics-rank'+str(RANK)+'.json',dict(train=train_info,second=second_info,validation=valid_info))
progress('loading_model')
quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
model=AutoModelForCausalLM.from_pretrained(str(ROOT/'source-model'),local_files_only=True,trust_remote_code=False,quantization_config=quant,torch_dtype=dtype,device_map={'':RANK},attn_implementation='sdpa')
model.config.use_cache=False
model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
STATE=pathlib.Path(os.environ.get('EVA_RESUME_DIR',str(P/'resume' if MODE=='smoke' else ROOT/'checkpoints')))
STATE.mkdir(exist_ok=True)
resume_path=ROOT/'checkpoints/step-102' if MODE=='train' and PHASE==2 else None
resume_info=dict(step=102) if resume_path else None
if resume_path:
 assert json.loads((STATE/'latest.json').read_text())['step']==102,'Only explicit phase2 continuation from complete102'
 complete=json.loads((resume_path/'complete.json').read_text());assert complete['step']==102
 for name,h in complete['files'].items():
  assert [hashlib.sha256((resume_path/name).read_bytes()).hexdigest() for _ in range(2)]==[h,h],name
else:assert not (STATE/'latest.json').exists(),'No automatic partial-run continuation'
model=PeftModel.from_pretrained(model,C['parent_adapter'],is_trainable=True)
assert model.peft_config['default'].r==8 and model.peft_config['default'].lora_alpha==16
params=[p for p in model.parameters() if p.requires_grad]
assert sum(p.numel() for p in params)==16515072
assert all(p.dtype==torch.float32 for p in params)
def statehash():
 return hashlib.sha256(b''.join(v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes() for k,v in sorted(get_peft_model_state_dict(model).items()))).hexdigest()
initial_hash=statehash();assert initial_hash=='0883c80e45904bdcb85aa6a27d20e921eea7a6bf5574990375e51835d4163a52';hashes=[None]*WORLD;dist.all_gather_object(hashes,initial_hash)
assert len(set(hashes))==1,'Different initial adapters'
resume_hash=None
if resume_path:
 raw=load_file(str(resume_path/'adapter/adapter_model.safetensors'),device='cpu')
 result=set_peft_model_state_dict(model,raw);assert not result.unexpected_keys
 resume_hash=statehash();expected=hashlib.sha256(b''.join(v.contiguous().view(torch.uint8).numpy().tobytes() for k,v in sorted(raw.items()))).hexdigest()
 assert resume_hash==expected
 save('prefix-loaded-rank'+str(RANK)+'.json',dict(passed=True,step=102,state_sha256=resume_hash,adapter_sha256=hashlib.sha256((resume_path/'adapter/adapter_model.safetensors').read_bytes()).hexdigest()))
save('qualification-rank'+str(RANK)+'.json',dict(rank=RANK,gpu=torch.cuda.get_device_name(RANK),uuid=C['uuids'][1 if SINGLE else RANK],precision=str(dtype),trainable_parameters=sum(p.numel() for p in params),initial_adapter_state_sha256=initial_hash,device_map={k:str(v) for k,v in model.hf_device_map.items()},torch=torch.__version__,attention='sdpa',quantization='NF4 double quant',mode=MODE))
model.train()
progress('ddp_setup')
ddp=DDP(model,device_ids=[RANK],output_device=RANK,broadcast_buffers=False,find_unused_parameters=False)
def batch(b):return {k:v.to('cuda',non_blocking=True) for k,v in b.items()}
def barrier():
 progress('waiting_peer')
 dist.barrier(device_ids=[RANK])
def agreement():
 flat=torch.cat([p.detach().flatten() for p in params]);ref=flat.clone();dist.broadcast(ref,src=0)
 delta=(flat-ref).abs().max();dist.all_reduce(delta,op=dist.ReduceOp.MAX)
 value=float(delta);assert value<=1e-6,'Adapter replicas diverged: '+str(value)
 return value
def update(optimizer,scaler,index):
 optimizer.zero_grad(set_to_none=True);start=time.time()
 index=index%C['updates_per_epoch']
 pairs=len(train_batches)//WORLD
 if MODE=='smoke' and index>=2:
  six=[i for i in range(102) if ((i+1)*pairs//102-i*pairs//102)*WORLD==6];assert len(six)>=2
  index=six[index-2]

 indices=list(range((index*pairs//102)*WORLD,((index+1)*pairs//102)*WORLD));microsteps=len(indices)//WORLD
 assert len(indices) in [4,6] and microsteps in [2,3]
 total_supervised=sum(int((train_batches[k]['labels'][:,1:]!=-100).sum()) for k in indices)
 assert total_supervised>0
 nonpad=supervised=padded=0;losses=[];local_indices=[]
 for j in range(microsteps):
  k=indices[j*WORLD+RANK];real=True
  cpu=train_batches[k if real else indices[-1]]
  n=int((cpu['labels'][:,1:]!=-100).sum()) if real else 0
  if real:
   nonpad+=int(cpu['attention_mask'].sum());supervised+=n;padded+=cpu['input_ids'].numel();local_indices.append(k)
  with ddp.no_sync() if j<microsteps-1 else contextlib.nullcontext():
   with torch.autocast('cuda',dtype=dtype):loss=ddp(**batch(cpu)).loss
   if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
   if real:losses.append(float(loss.detach()))
   scaler.scale(loss*(WORLD*n/total_supervised)).backward()
 scaler.unscale_(optimizer);norm=torch.nn.utils.clip_grad_norm_(params,1.0)
 if not torch.isfinite(norm):raise RuntimeError('Nonfinite gradient norm')
 old=scaler.get_scale();scaler.step(optimizer);scaler.update();torch.cuda.synchronize()
 if scaler.get_scale()<old:raise RuntimeError('Optimizer overflow')
 return dict(rank=RANK,seconds=time.time()-start,pack_indices=local_indices,nonpadding_tokens=nonpad,supervised_tokens=supervised,padded_tokens=padded,loss=sum(losses)/len(losses) if losses else None,gradient_norm=float(norm),lr=optimizer.param_groups[0]['lr'],scale=scaler.get_scale(),peak_vram_mib=torch.cuda.max_memory_allocated()/1048576)
progress('loaded')
barrier()
optimizer=torch.optim.AdamW(params,lr=C['learning_rate'],weight_decay=0.0,foreach=False)
scaler=torch.amp.GradScaler('cuda',init_scale=128.0,growth_interval=2000,enabled=True)
assert all(len(b)%2==0 and 408<=len(b)<=612 for b in train_batches_by_epoch)
full_steps=C['updates_per_epoch']*C['epochs']
assert full_steps==C['max_updates']
steps=4 if MODE=='smoke' else PHASE*C['updates_per_epoch']
warm=max(1,int(C['updates_per_epoch']*.05))
scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda i:min((i%C['updates_per_epoch']+1)/warm,1.0)*max(.1,1-(i%C['updates_per_epoch'])/C['updates_per_epoch']))
torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();start=time.time()
start_step=0;resume_totals=[0,0,0]
if resume_path:
 state=torch.load(resume_path/'training-state.pt',map_location='cpu',weights_only=False)
 assert state['dataset_sha256']==json.loads((ROOT/'lineage.json').read_text())['dataset_sha256']
 prep=json.loads((ROOT/'dataset-preparation.json').read_text())['passes'][0]
 assert state['step']==102 and state['world_size']==2 and state['totals']==[prep['nonpadding_tokens'],60109,prep['packs']*512]
 assert hashlib.sha256((resume_path/'training-state.pt').read_bytes()).hexdigest()==complete['files']['training-state.pt']
 optimizer.load_state_dict(state['optimizer']);scheduler.load_state_dict(state['scheduler']);scaler.load_state_dict(state['scaler'])
 start_step=state['step'];resume_totals=state['totals']
 rng=state['rngs'][1 if SINGLE and len(state['rngs'])==2 else RANK]
 torch.set_rng_state(rng['cpu']);torch.cuda.set_rng_state(rng['cuda'],device=RANK)
 save('resumed-rank'+str(RANK)+'.json',dict(step=start_step,directory=str(resume_path),previous_world_size=state['world_size'],world_size=WORLD,optimizer_restored=True))
rows=[]
def checkpoint(step):
 progress('checkpoint',optimizer_step=step,total_steps=steps)
 totals=torch.tensor([sum(r[k] for r in rows) for k in ['nonpadding_tokens','supervised_tokens','padded_tokens']],device='cuda',dtype=torch.int64)
 dist.all_reduce(totals);totals=[a+b for a,b in zip(totals.cpu().tolist(),resume_totals)]
 rngs=[None]*WORLD;dist.all_gather_object(rngs,dict(cpu=torch.get_rng_state(),cuda=torch.cuda.get_rng_state()))
 if RANK==0:
  name='step-'+str(step);tmp=STATE/(name+'.pending')
  assert not tmp.exists() and not (STATE/name).exists(),'Never overwrite complete or pending checkpoints'
  tmp.mkdir(exist_ok=False)
  model.save_pretrained(tmp/'adapter')
  torch.save(dict(step=step,optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),scaler=scaler.state_dict(),rngs=rngs,totals=totals,world_size=WORLD,dataset_sha256=json.loads((ROOT/'lineage.json').read_text())['dataset_sha256']),tmp/'training-state.pt')
  for file in tmp.rglob('*'):
   if file.is_file():
    with file.open('rb') as handle:os.fsync(handle.fileno())
  files={str(f.relative_to(tmp)):hashlib.sha256(f.read_bytes()).hexdigest() for f in tmp.rglob('*') if f.is_file()}
  (tmp/'complete.json').write_text(json.dumps(dict(step=step,totals=totals,files=files)))
  with (tmp/'complete.json').open('rb') as handle:os.fsync(handle.fileno())
  tmp.rename(STATE/name)
  q=STATE/'latest.tmp';q.write_text(json.dumps(dict(step=step,directory=name,epoch=time.time())));q.replace(STATE/'latest.json')
 dist.barrier(device_ids=[RANK])
progress('training',optimizer_step=start_step,total_steps=steps)
for i in range(start_step,steps):
 train_batches=train_batches_by_epoch[i//C['updates_per_epoch']]
 r=update(optimizer,scaler,i);r.update(optimizer_step=i+1,epoch=time.time());rows.append(r)
 append('steps-rank'+str(RANK)+'.jsonl',r);scheduler.step()
 progress('training',optimizer_step=i+1,total_steps=steps)
 if (i+1)%(2 if MODE=='smoke' else 20)==0 or (i+1)%C['updates_per_epoch']==0 or i+1==steps:checkpoint(i+1)

delta=agreement();final_hash=statehash();assert start_step==steps or final_hash!=initial_hash,'No adapter learning'
save('training-rank'+str(RANK)+'.json',dict(mode=MODE,seconds=time.time()-start,optimizer_steps=steps,executed_updates=len(rows),resumed_from=start_step,nonpadding_tokens=sum(r['nonpadding_tokens'] for r in rows),supervised_tokens=sum(r['supervised_tokens'] for r in rows),initial_adapter_state_sha256=initial_hash,final_adapter_state_sha256=final_hash,replica_max_difference=delta,peak_vram_mib=torch.cuda.max_memory_allocated()/1048576))
barrier()
if MODE=='smoke':
 final_copy={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}
 parent=load_file(str(pathlib.Path(C['parent_adapter'])/'adapter_model.safetensors'),device='cpu')
 r=set_peft_model_state_dict(model,parent);assert not r.unexpected_keys and statehash()==initial_hash
 r=set_peft_model_state_dict(model,final_copy);assert not r.unexpected_keys and statehash()==final_hash
 restored=torch.load(STATE/'step-4/training-state.pt',map_location='cpu',weights_only=False)
 optimizer.load_state_dict(restored['optimizer']);scheduler.load_state_dict(restored['scheduler']);scaler.load_state_dict(restored['scaler'])
 assert restored['step']==4 and restored['world_size']==2 and agreement()<=1e-6
 if RANK==0:save('passed.json',dict(passed=True,tested_global_packs=sorted({len(x['pack_indices'])*WORLD for x in rows}),steps=4,checkpoint_optimizer_scheduler_scaler_roundtrip=True,parent_adapter_roundtrip=True,replica_max_difference=delta,epoch=time.time()))
else:
 assert start_step==(PHASE-1)*102 and len(rows)==102 and (PHASE==1 or resume_hash!=final_hash)
 if RANK==0:
  counts=[json.loads((P/('training-rank'+str(r)+'.json')).read_text()) for r in range(WORLD)]
  prep=json.loads((ROOT/'dataset-preparation.json').read_text())['passes']
  assert resume_totals[0]+sum(r['nonpadding_tokens'] for r in counts)==sum(x['nonpadding_tokens'] for x in prep[:PHASE])
  assert resume_totals[1]+sum(r['supervised_tokens'] for r in counts)==60109*PHASE
  assert sum(r['padded_tokens'] for r in rows)==len(train_batches)*512//WORLD
  save('training-summary.json',dict(ranks=counts,phase=PHASE,total_epochs=PHASE,global_packs_per_update='4 or6, token-weighted, equal microsteps per rank',precision='FP16/NF4 doublequant',power_limit_per_gpu_w=200,parent_adapter=C['parent_adapter'],coverage_verified=True,resumed_from=start_step,new_updates=102,total_updates=steps,inherited_tokens=resume_totals,world_size=WORLD))
  progress('saving_trained_candidate');model.save_pretrained(P/'adapter-final');tokenizer.save_pretrained(P/'adapter-final')
  save('candidate-info.json',dict(trained_candidate=str(P/'adapter-final'),adapter_state_sha256=final_hash,automatic_promotion=False,selection='outside training; no automatic model adoption or next experiment'))
 barrier()
progress('finished');dist.destroy_process_group()
