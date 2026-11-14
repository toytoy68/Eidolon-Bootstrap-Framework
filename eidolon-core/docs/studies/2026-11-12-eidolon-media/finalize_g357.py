# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : finalize_g357.py
# Description : Archivage de la qualification SDXL Inpainting G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,shutil,subprocess,datetime
w=Path('/srv/eidolon/workspaces/media-20261112/sdxl-inpaint-g357');r=w.parent/'source';s=r/'eidolon-core/docs/studies/2026-11-12-eidolon-media';e=s/'evidence-g357';assert not e.exists();e.mkdir()
b=json.loads((w/'final-bundle.json').read_text());d=b['data'];d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(s/'sdxl-inpaint-validation-g357.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(s/'SDXL-INPAINT-G357.md').write_text(b['report']);(e/'visual-reviews.json').write_text(json.dumps(d['reviews'],ensure_ascii=False,indent=2)+'\n')
for p in w.iterdir():
 if p.is_file() and p.suffix in ['.json','.md','.txt'] and p.name not in ['final-bundle.json','git-payload.json']:shutil.copy2(p,e/p.name)
for sub,prefix in [('run01','smoke'),('run02','baseline'),('run03','focused')]:
 for p in (w/sub).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.jsonl']:shutil.copy2(p,e/(prefix+'-'+str(p.relative_to(w/sub)).replace('/','-')))
for p in (w/'model-config').rglob('*'):
 if p.is_file() and p.name not in ['vocab.json','merges.txt']:
  dst=e/'model-config'/p.relative_to(w/'model-config');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
for unit in ['prepare','smoke','quality','focused']:
 out=subprocess.check_output(['sudo','-n','journalctl','--all','--no-pager','-u','eidolon-media-sdxl-inpaint-g357-'+unit,'-o','short-iso'],text=True);assert len(out)>100;(e/(unit+'-journal.txt')).write_text(out)
for name in ['README.md','ROADMAP.md']:
 p=s/name;p.write_text(p.read_text()+'\n\n## Avancement G357 - SDXL Inpainting, 14/11/2026\n\n'+b['summary']+'\n')
p=s/'CANDIDATE-QUEUE-G332.md';lines=p.read_text().splitlines();matches=[i for i,line in enumerate(lines) if line.startswith('| I03 — ')];assert len(matches)==1;lines[matches[0]]=b['candidate_row'];p.write_text('\n'.join(lines)+'\n')
p=r/'eidolon-core/ECHANGES.md';p.write_text(p.read_text()+'\n\n## C-MSG-G357 — SDXL Inpainting terminé, 14/11/2026, Codex/GPT\n\n'+b['summary'].replace('(SDXL-INPAINT-G357.md)','(docs/studies/2026-11-12-eidolon-media/SDXL-INPAINT-G357.md)')+' Rapport illustré de 14 pages enregistré ; aucun avis utilisateur attribué.\n')
print('G357 documents and evidence saved')
