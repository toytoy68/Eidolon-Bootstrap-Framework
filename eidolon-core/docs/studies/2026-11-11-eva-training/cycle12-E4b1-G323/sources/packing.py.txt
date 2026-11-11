# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : packing.py
# Description : Assemblage dense de masques assistant valides, even packs
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
def pack_plan(lengths,count=408,limit=512):
 assert all(0<x<=limit for x in lengths)
 groups=[];sizes=[]
 for i in sorted(range(len(lengths)),key=lambda i:(-lengths[i],i)):
  fits=[j for j,s in enumerate(sizes) if s+lengths[i]<=limit]
  if fits:j=max(fits,key=lambda j:sizes[j]);groups[j].append(i);sizes[j]+=lengths[i]
  else:groups.append([i]);sizes.append(lengths[i])
 count=max(count,len(groups)+(len(groups)%2))
 while len(groups)<count:
  choices=[j for j,g in enumerate(groups) if len(g)>1];assert choices
  j=max(choices,key=lambda j:(len(groups[j]),sizes[j]));cut=len(groups[j])//2
  new=groups[j][cut:];groups[j]=groups[j][:cut];groups.append(new);sizes[j]=sum(lengths[i] for i in groups[j]);sizes.append(sum(lengths[i] for i in new))
 groups=[sorted(g) for g in groups];groups.sort(key=lambda g:min(g))
 assert len(groups)==count and sorted(i for g in groups for i in g)==list(range(len(lengths)))
 return groups
def assemble(examples,groups,encode,torch,pad,limit=512):
 one=[encode([ex])[0][0] for ex in examples];batches=[];nonpad=sup=0
 for g in groups:
  ids=[];labels=[]
  for i in g:
   x=one[i];n=int(x['attention_mask'].sum());ids+=x['input_ids'][0,:n].tolist();labels+=x['labels'][0,:n].tolist()
  n=len(ids);assert 0<n<=limit and labels[0]==-100;nonpad+=n;sup+=sum(x!=-100 for x in labels)
  batches.append(dict(input_ids=torch.tensor([ids+[pad]*(limit-n)]),attention_mask=torch.tensor([[1]*n+[0]*(limit-n)]),labels=torch.tensor([labels+[-100]*(limit-n)])))
 assert sum(int((x['labels'][:,1:]!=-100).sum()) for x in batches)==sup
 return batches,dict(examples=len(examples),packs=len(batches),tokens=nonpad,supervised_tokens=sup,packing='Best-fit whole examples then split to even count, at least408; causal attention crosses examples; original assistant mask unchanged. Training order differs E3.')
