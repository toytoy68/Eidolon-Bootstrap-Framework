"""Isolated QLoRA hardware pilot; never changes the production model."""
import os,time,json,pathlib,hashlib,signal,random,copy,math
P=pathlib.Path(__file__).resolve().parent
def save(n,d):
 p=P/(n+'.tmp');p.write_text(json.dumps(d,ensure_ascii=False));p.replace(P/n)
def append(n,d):
 with (P/n).open('a') as f:f.write(json.dumps(d,ensure_ascii=False)+'\n')
def progress(stage,**kw):save('train-progress.json',dict(stage=stage,epoch=time.time(),**kw))
progress('importing')
import torch
from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training,get_peft_model_state_dict,set_peft_model_state_dict
assert torch.cuda.device_count()==1,'Unexpected visible GPUs'
assert torch.cuda.get_device_capability(0)==(8,6),'Unexpected GPU architecture'
C=json.loads((P/'config.json').read_text());torch.set_num_threads(6);torch.manual_seed(1234);random.seed(1234)
dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
progress('tokenizer')
tokenizer=AutoTokenizer.from_pretrained(str(P/'source-model'),local_files_only=True,trust_remote_code=False)
if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
SYSTEM='Tu es un assistant francophone. Résous le calcul avec de courtes opérations intermédiaires exactes, puis un objet JSON contenant resultat (chaîne ou null), unite, et jours si demandé. Si une donnée manque, utilise null. N’invente aucune donnée.'
from curriculum import examples,grade,CANARIES
train=examples(44771,10000);valid=examples(97532,512,exclude_questions={x['question'] for x in train});heldout=examples(88013,160,True,exclude_questions={x['question'] for x in train+valid})
assert not ({x['question'] for x in train}&{x['question'] for x in valid})
assert not ({x['question'] for x in train}&{x['question'] for x in heldout})
save('dataset.json',dict(train=train,validation=valid,heldout=heldout,warning='Heldout has different templates and larger number ranges. Never used for optimizer/checkpoint selection.'))
def encode(examples):
 packed=[];ids=[];labels=[];L=C['sequence_length'];lengths=[]
 for ex in examples:
  messages=[dict(role='system',content=SYSTEM),dict(role='user',content=ex['question'])]
  prefix=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
  full=tokenizer.apply_chat_template(messages+[dict(role='assistant',content=ex['answer'])],tokenize=False,add_generation_prompt=False,enable_thinking=False)
  assert full.startswith(prefix),'Assistant masking prefix mismatch'
  enc=tokenizer(full,add_special_tokens=False,return_offsets_mapping=True)
  seq=enc['input_ids'];lab=[t if off[0]>=len(prefix) else -100 for t,off in zip(seq,enc['offset_mapping'])]
  assert any(t!=-100 for t in lab),'No supervised target tokens'
  if len(seq)>L:raise RuntimeError('Example exceeds sequence length: '+str(len(seq)))
  lengths.append(len(seq))
  if len(ids)+len(seq)>L:
   packed.append((ids,labels));ids=[];labels=[]
  ids+=seq;labels+=lab
 if ids:packed.append((ids,labels))
 batches=[]
 for seq,lab in packed:
  actual=len(seq);batches.append(dict(input_ids=torch.tensor([seq+[tokenizer.pad_token_id]*(L-actual)]),attention_mask=torch.tensor([[1]*actual+[0]*(L-actual)]),labels=torch.tensor([lab+[-100]*(L-actual)])))
 return batches,dict(examples=len(examples),packs=len(batches),tokens=sum(lengths),mean_tokens_per_example=sum(lengths)/len(lengths),max_tokens_per_example=max(lengths),packing='Whole examples concatenated; causal attention crosses sample boundaries; padding masked; assistant-only loss.')
train_batches,train_info=encode(train);valid_batches,valid_info=encode(valid)
save('dataset-statistics.json',dict(train=train_info,validation=valid_info,template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()))
progress('loading_model')
quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
model=AutoModelForCausalLM.from_pretrained(str(P/'source-model'),local_files_only=True,trust_remote_code=False,quantization_config=quant,torch_dtype=dtype,device_map={'':0},attn_implementation='sdpa')
model.config.use_cache=False
model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
from peft import PeftModel
model=PeftModel.from_pretrained(model,C['parent_adapter'],is_trainable=True)
params=[p for p in model.parameters() if p.requires_grad];assert params
initial={k:v.detach().cpu().clone() for k,v in get_peft_model_state_dict(model).items()}
init_hash=hashlib.sha256(b''.join(v.contiguous().view(torch.uint8).numpy().tobytes() for k,v in sorted(initial.items()))).hexdigest()
save('training-qualification.json',dict(torch=torch.__version__,cuda_runtime=torch.version.cuda,gpu=torch.cuda.get_device_name(),dtype=str(dtype),trainable_parameters=sum(p.numel() for p in params),initial_adapter_sha256=init_hash,device_map={k:str(v) for k,v in model.hf_device_map.items()},attention='sdpa',quantization='NF4, double quant; distinct from inference Q4_K_M',assistant_only_loss=True,sequence_length=C['sequence_length'],micro_batch=C['micro_batch'],gradient_accumulation=C['gradient_accumulation'],parent_adapter=C['parent_adapter']))
def batch(b):return {k:v.to('cuda',non_blocking=True) for k,v in b.items()}
def evaluate():
 model.eval();losses=[]
 with torch.no_grad():
  for b in valid_batches[:8]:
   with torch.autocast('cuda',dtype=dtype):loss=model(**batch(b)).loss
   losses.append(float(loss))
 model.train();return sum(losses)/len(losses)
def evaluate_generation(stage):
 model.eval();rows=[];start=time.time();progress('evaluation_'+stage,done=0,total=len(heldout)+len(CANARIES))
 for i,ex in enumerate(heldout):
  messages=[dict(role='system',content=SYSTEM),dict(role='user',content=ex['question'])]
  ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False,return_tensors='pt').to('cuda')
  with torch.inference_mode(),torch.autocast('cuda',dtype=dtype):out=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),max_new_tokens=192,do_sample=False,use_cache=True,pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id)
  text=tokenizer.decode(out[0,ids.shape[1]:],skip_special_tokens=True);r=dict(stage=stage,id=ex['id'],family=ex['family'],question=ex['question'],expected=ex['expected'],response=text,evaluation=grade(text,ex['expected']),generated_tokens=int(out.shape[1]-ids.shape[1]),token_limit_reached=out.shape[1]-ids.shape[1]>=192);append('evaluation.jsonl',r);rows.append(r);progress('evaluation_'+stage,done=i+1,total=len(heldout)+len(CANARIES))
 for j,(name,q) in enumerate(CANARIES):
  ids=tokenizer.apply_chat_template([dict(role='system',content='Tu es un assistant francophone. Réponds à la demande sans inventer les informations manquantes.'),dict(role='user',content=q)],tokenize=True,add_generation_prompt=True,enable_thinking=False,return_tensors='pt').to('cuda')
  with torch.inference_mode(),torch.autocast('cuda',dtype=dtype):out=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),max_new_tokens=256,do_sample=False,use_cache=True,pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id)
  text=tokenizer.decode(out[0,ids.shape[1]:],skip_special_tokens=True);append('canaries.jsonl',dict(stage=stage,name=name,question=q,response=text,token_limit_reached=out.shape[1]-ids.shape[1]>=256));progress('evaluation_'+stage,done=len(heldout)+j+1,total=len(heldout)+len(CANARIES))
 summary={'stage':stage,'n':len(rows),'content_correct':sum(r['evaluation']['content_correct'] for r in rows),'exact_json':sum(r['evaluation']['exact'] for r in rows),'seconds':time.time()-start,'families':{str(f):{'n':sum(r['family']==f for r in rows),'correct':sum(r['family']==f and r['evaluation']['content_correct'] for r in rows)} for f in range(8)}}
 save('evaluation-'+stage+'.json',summary);model.train();return summary

def update(optimizer,scaler,index):
 optimizer.zero_grad(set_to_none=True);nonpad=supervised=padded=0;losses=[];t0=time.perf_counter();micro=C['micro_batch'];acc=C['gradient_accumulation'];begin=index*micro*acc
 chunks=[train_batches[k:min(k+micro,len(train_batches))] for k in range(begin,min(begin+micro*acc,len(train_batches)),micro)]
 assert chunks
 for group in chunks:
  b={k:torch.cat([v[k] for v in group],dim=0) for k in group[0]};nonpad+=int(b['attention_mask'].sum());supervised+=int((b['labels'][:,1:]!=-100).sum());padded+=b['input_ids'].numel()
  with torch.autocast('cuda',dtype=dtype):loss=model(**batch(b)).loss
  if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
  losses.append(float(loss.detach()));scaler.scale(loss/len(chunks)).backward()
 scaler.unscale_(optimizer);norm=torch.nn.utils.clip_grad_norm_(params,1.0)
 if not torch.isfinite(norm):raise RuntimeError('Nonfinite gradient norm')
 old=scaler.get_scale();scaler.step(optimizer);scaler.update();torch.cuda.synchronize()
 if scaler.get_scale()<old:raise RuntimeError('Optimizer overflow')
 return dict(seconds=time.perf_counter()-t0,nonpadding_tokens=nonpad,supervised_tokens=supervised,padded_tokens=padded,loss=sum(losses)/len(losses),gradient_norm=float(norm),lr=optimizer.param_groups[0]['lr'],allocated_mib=torch.cuda.memory_allocated()/1048576,reserved_mib=torch.cuda.memory_reserved()/1048576,max_allocated_mib=torch.cuda.max_memory_allocated()/1048576,max_reserved_mib=torch.cuda.max_memory_reserved()/1048576)

progress('loaded')
while not (P/'command.json').exists():time.sleep(.2)
assert json.loads((P/'command.json').read_text())['power_w']==200
baseline=evaluate();before=evaluate_generation('before')
optimizer=torch.optim.AdamW(params,lr=5e-5,weight_decay=0.0,foreach=False);scaler=torch.amp.GradScaler('cuda',enabled=dtype==torch.float16)
steps=math.ceil(len(train_batches)/(C['micro_batch']*C['gradient_accumulation']));warm=max(1,int(steps*.05));scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda i:min((i+1)/warm,1.0)*max(.1,1-i/max(steps,1)))
torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.time();rows=[];progress('measuring',power_w=200,start=start,total_steps=steps)
for i in range(steps):
 r=update(optimizer,scaler,i);r.update(power_w=200,optimizer_step=i,epoch=time.time());rows.append(r);append('steps.jsonl',r);scheduler.step();progress('measuring',power_w=200,start=start,optimizer_step=i+1,total_steps=steps)
 if (i+1)%100==0:
  progress('checkpoint',optimizer_step=i+1,total_steps=steps);model.save_pretrained(P/'checkpoints'/('step-'+str(i+1)))
end=time.time();progress('validation');after_loss=evaluate();progress('saving');model.save_pretrained(P/'adapter-final');tokenizer.save_pretrained(P/'adapter-final')
assert sum(r['nonpadding_tokens'] for r in rows)==train_info['tokens'],'Training token coverage mismatch'
save('cell-200.json',dict(power_w=200,start=start,end=end,seconds=end-start,optimizer_steps=len(rows),nonpadding_tokens=sum(r['nonpadding_tokens'] for r in rows),supervised_tokens=sum(r['supervised_tokens'] for r in rows),padded_tokens=sum(r['padded_tokens'] for r in rows),initial_adapter_sha256=init_hash,parent_adapter=C['parent_adapter'],examples=len(train),epochs=1,micro_batch=C['micro_batch'],validation_loss_before=baseline,validation_loss_after=after_loss))
after=evaluate_generation('after');save('quality-comparison.json',dict(before=before,after=after,warning='No checkpoint selection on heldout; canary conversations require qualitative review. No production deployment.'))
progress('finished')
