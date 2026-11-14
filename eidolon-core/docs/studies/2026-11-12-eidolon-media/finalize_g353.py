# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : finalize_g353.py
# Description : Archivage des résultats Juggernaut G353
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,shutil,subprocess,datetime
w=Path('/srv/eidolon/workspaces/media-20261112/juggernaut-x-g353');r=w.parent/'source';s=r/'eidolon-core/docs/studies/2026-11-12-eidolon-media';e=s/'evidence-g353';e.mkdir(exist_ok=True)
b=json.loads((w/'final-bundle.json').read_text());d=b['data'];d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(s/'juggernaut-x-validation-g353.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(s/'JUGGERNAUT-X-G353.md').write_text(b['report']);(e/'visual-reviews.json').write_text(json.dumps(d['reviews'],ensure_ascii=False,indent=2)+'\n')
for p in w.iterdir():
 if p.is_file() and p.suffix in ['.json','.md','.txt'] and p.name not in ['final-bundle.json','git-payload.json']:shutil.copy2(p,e/p.name)
shutil.copy2(w/'runner-before-config-json-fix.py',e/'runner-before-config-json-fix.py')
for sub,prefix in [('run00-config-json-failed','config-failed'),('run01','smoke'),('run02','quality')]:
 for p in (w/sub).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.jsonl']:shutil.copy2(p,e/(prefix+'-'+str(p.relative_to(w/sub)).replace('/','-')))
for p in (w/'sdxl-config').rglob('*.json'):
 if p.name!='vocab.json':
  dst=e/'sdxl-config'/p.relative_to(w/'sdxl-config');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
for unit in ['prepare','smoke','quality']:
 out=subprocess.check_output(['journalctl','--no-pager','-u','eidolon-media-juggernaut-x-g353-'+unit,'-o','short-iso'],text=True);(e/(unit+'-journal.txt')).write_text(out)
summary=b['summary']
for name in ['README.md','ROADMAP.md']:
 p=s/name;p.write_text(p.read_text()+'\n\n## Avancement G353 — Juggernaut v10/v9, 14/11/2026\n\n'+summary+'\n')
p=s/'CANDIDATE-QUEUE-G332.md';lines=p.read_text().splitlines();found=False
for i,line in enumerate(lines):
 if line.startswith('| I06 — '):lines[i]=b['candidate_row'];found=True
assert found;p.write_text('\n'.join(lines)+'\n')
p=r/'eidolon-core/ECHANGES.md';p.write_text(p.read_text()+'\n\n## C-MSG-G353 — Juggernaut v10/v9 terminé, 14/11/2026, Codex/GPT\n\n'+summary.replace('(JUGGERNAUT-X-G353.md)','(docs/studies/2026-11-12-eidolon-media/JUGGERNAUT-X-G353.md)')+' Rapport illustré enregistré, preuves conservées. Aucun avis utilisateur attribué.\n')
print('G353 documents and evidence saved.')
