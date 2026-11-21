# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : finalize_g351.py
# Description : Archivage comparatif FLUX Schnell Q8 G351
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,shutil,subprocess,datetime
w=Path('/srv/eidolon/workspaces/media-20261112/flux-q8-g351');r=w.parent/'source';s=r/'eidolon-core/docs/studies/2026-11-12-eidolon-media';e=s/'evidence-g351';e.mkdir(exist_ok=True)
b=json.loads((w/'final-bundle.json').read_text());d=b['data'];d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(s/'flux-q8-validation-g351.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(e/'visual-reviews.json').write_text(json.dumps(d['reviews'],ensure_ascii=False,indent=2)+'\n');(s/'FLUX-Q8-G351.md').write_text(b['report'])
for p in w.iterdir():
 if p.is_file() and p.suffix in ['.json','.md','.txt','.html'] and p.name not in ['final-bundle.json','git-payload.json']:shutil.copy2(p,e/p.name)
shutil.copy2(w/'transformer-config/config.json',e/'transformer-config.json')
shutil.copy2(w/'runner-before-placement-fix.py',e/'runner-before-placement-fix.py')
for sub,prefix in [('run00-placement-failed','placement-failed'),('run01','smoke'),('run02','quality')]:
 for p in (w/sub).iterdir():
  if p.suffix in ['.json','.jsonl']:shutil.copy2(p,e/(prefix+'-'+p.name))
for unit in ['prepare','smoke','quality']:
 p=subprocess.run(['journalctl','--no-pager','-u','eidolon-media-flux-q8-g351-'+unit,'-o','short-iso'],text=True,capture_output=True,check=True);(e/(unit+'-journal.txt')).write_text(p.stdout)
summary=b['summary']
for name in ['README.md','ROADMAP.md']:
 p=s/name;p.write_text(p.read_text()+'\n\n## Avancement G351 — FLUX Schnell Q8, 14/11/2026\n\n'+summary+'\n')
p=s/'CANDIDATE-QUEUE-G332.md';lines=p.read_text().splitlines();found=False
for i,line in enumerate(lines):
 if line.startswith('| I08 — '):lines[i]=b['candidate_row'];found=True
assert found;p.write_text('\n'.join(lines)+'\n')
p=r/'eidolon-core/ECHANGES.md';p.write_text(p.read_text()+'\n\n## C-MSG-G351 — FLUX Schnell Q8 terminé, 14/11/2026, Codex/GPT\n\n'+summary.replace('(FLUX-Q8-G351.md)','(docs/studies/2026-11-12-eidolon-media/FLUX-Q8-G351.md)')+' Rapport illustré enregistré, preuves conservées. Aucun avis utilisateur attribué aux nouvelles images.\n')
print('Documents and evidence saved.')
