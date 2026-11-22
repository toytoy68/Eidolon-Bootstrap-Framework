# Eidolon Core Technologies (ECT) — complete synthetic documents, derived passages only
from pathlib import Path
from dataclasses import asdict
import json,hashlib,time,os
from core.backend.filesystem import FilesystemBackend
from core.backend.models import Memory
from core.indexing.passages import split_passages,verify_passage
from core.indexing.runtime import load_runtime,open_index
os.umask(0o077)
p=Path('/home/toytoy/followup2-20261122/run1');p.mkdir(mode=0o700,exist_ok=True);p.chmod(0o700)
root=p/'corpus/memory/persistent';backend=FilesystemBackend(root,p/'corpus/memory/history')
sources=sorted(Path('/home/toytoy/eidolon-test-corpora/eidolon-corpus-fr-100-v1/documents').glob('*.txt'))[:3]
manifest=[];queries=[]
for i,source in enumerate(sources):
 text=source.read_text();identity=f'long-{i:03d}';chunks=split_passages(identity,1,text,size=1200,overlap=160)
 assert chunks and chunks[0].start==0 and chunks[-1].end==len(text)
 rebuilt=chunks[0].text
 for j,c in enumerate(chunks):
  assert verify_passage(c,text,document_id=identity,revision=1)
  if j:assert c.start<=chunks[j-1].end;rebuilt+=c.text[chunks[j-1].end-c.start:]
  backend.store(Memory(c.passage_id,content=c.text))
 assert rebuilt==text
 manifest.append(dict(source=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),characters=len(text),chunks=[asdict(c) for c in chunks]))
 for j in sorted(set([0,len(chunks)//2,len(chunks)-1])):queries.append(dict(document=identity,expected=chunks[j].passage_id,text=chunks[j].text[:300]))
(p/'passage-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
config=json.loads(Path('/home/toytoy/eidolon-beta-memory/index.json').read_text());config.update(alias='eidolon_followup2_longdocs',num_ctx=2048,max_input_chars=16000)
(p/'index.json').write_text(json.dumps(config));cfg=load_runtime(p/'index.json');index=open_index(cfg,create=True)
start=time.time();before=asdict(index.status());published=index.sync(root);status=asdict(index.status());assert status['points']==sum(len(x['chunks']) for x in manifest)
unchanged=index.sync(root);assert unchanged['state']=='UNCHANGED'
answers=[]
for q in queries:
 t=time.time();hits=index.query_snapshot(q['text'],limit=5).hits;ids=[x.information_id for x in hits];answers.append(dict(document=q['document'],expected=q['expected'],top5=ids,found=q['expected'] in ids,seconds=time.time()-t))
assert all(hashlib.sha256(s.read_bytes()).hexdigest()==m['sha256'] for s,m in zip(sources,manifest))
result=dict(passed=True,source_documents=len(sources),source_characters=sum(x['characters'] for x in manifest),coverage='complete with exact reconstruction',projection='explicit derived staging; native ordinary-document path unchanged',initial=before,final=status,published=published,unchanged=unchanged,queries=answers,query_scope='literal 300-character excerpts, not an independent semantic benchmark',seconds=time.time()-start,canonical_unchanged=True,production_modified=False)
(p/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));index.client.close()
