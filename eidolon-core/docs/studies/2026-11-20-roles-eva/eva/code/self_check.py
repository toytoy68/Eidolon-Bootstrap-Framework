# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : self_check.py
# Description : Qualification CPU du curriculum, masque et DDP pondere
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from common import P,read,save,sha
from components import make,correct
from packing import assemble
import ast,torch,json,collections,re
from transformers import AutoTokenizer
import eva_boundary_probes as bp
for n in ['train.py','audit_worker.py','campaign.py','finish.py','metrics.py','prepare.py','components.py','packing.py','guard.py','live_check.py']:ast.parse((P/n).read_text())
t=ast.parse((P/'train.py').read_text());a=ast.parse((P/'audit_worker.py').read_text())
assert not any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='generate' for x in ast.walk(t))
assert not any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr in ['backward','step','train','init_process_group'] for x in ast.walk(a))
C=read(P/'config.json');tokenizer=AutoTokenizer.from_pretrained(str(P/'source-model'),local_files_only=True,trust_remote_code=False)
if tokenizer.pad_token_id is None:tokenizer.pad_token_id=tokenizer.eos_token_id
tree=ast.parse((P/'encoding-source.py').read_text());ns=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='encode' or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='SYSTEM' for x in n.targets)];exec(compile(ast.Module(body=ns,type_ignores=[]),'encoding-source.py','exec'))
d=read(P/'dataset.json');plans=read(P/'pack-plan.json');stats=read(P/'dataset-preparation.json');coverage=[]
replay=read(P/'replay-original.json')
for ep,key in enumerate(['train','train_second']):
 xs=d[key];assert [x for x in xs if x['group']=='replay']==replay
 assert not any(x['answer'].startswith('Départ') for x in xs)
 for x in xs:
  if x['group']=='component':
   assert x==make(x['kind'],x['value'],x['variant'],x['id'])
   assert correct(bp._last_object(x['answer']),x)
   assert not bp.invalid_claims(x['answer'])
 batches,info=assemble(xs,plans[ep],encode,torch,tokenizer.pad_token_id);assert info['supervised_tokens']==60109
 assert info['tokens']==stats['passes'][ep]['nonpadding_tokens'] and len(batches)==stats['passes'][ep]['packs']
 pairs=len(batches)//2;seen=[];sizes=[]
 for i in range(102):
  inds=list(range((i*pairs//102)*2,((i+1)*pairs//102)*2));assert len(inds) in [4,6];sizes.append(len(inds));seen+=inds
  assert all((x['labels'][x['attention_mask']==0]==-100).all() for x in [batches[k] for k in inds])
 assert sorted(seen)==list(range(len(batches))) and len(seen)==len(set(seen))
 coverage.append(dict(epoch=ep+1,groups=dict(collections.Counter(sizes)),statistics=info))
# DDP averages ranks: per-micro WORLD*n/global_tokens reproduces the global token gradient.
for ns in [[3,17,5,11],[3,17,5,11,7,13]]:
 x=torch.tensor(2.,requires_grad=True);loss=sum((x-(i+1))**2*n for i,n in enumerate(ns))/sum(ns);loss.backward();want=x.grad.item();got=[]
 for rank in range(2):
  y=torch.tensor(2.,requires_grad=True);v=sum((y-(i+1))**2*2*ns[i]/sum(ns) for i in range(rank,len(ns),2));v.backward();got.append(y.grad.item())
 assert abs(sum(got)/2-want)<1e-6
# Finite-domain oracles and strict types, including midnight and final minute.
oracle_count=0
for kind,domain in [('X1',range(1440)),('X2',range(4320)),('X3',range(1440))]:
 for n in domain:
  ex=make(kind,n,n%2);obj=bp._last_object(ex['answer']);assert correct(obj,ex);assert not bp.invalid_claims(ex['answer']);oracle_count+=1
  bad=dict(obj,resultat=True);assert not correct(bad,ex)
for n in [0,59,60,1380,1439]:
 assert make('X3',n)['expected']['resultat']==f'{n//60:02}:{n%60:02}'
save(P/'self-check.json',dict(passed=True,coverage=coverage,gradient_checks_global_packs=[4,6],oracle_cases=oracle_count,full_questions_new_format_in_training=0,masking='Original encode function called per example; assistant labels reused verbatim',world_size=2,training=False))
print(json.dumps(read(P/'self-check.json')))
