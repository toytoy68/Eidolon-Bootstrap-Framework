# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : finalize_g352.py
# Description : Archivage comparatif FLUX Schnell Q4 G352
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,shutil,subprocess,datetime
w=Path('/srv/eidolon/workspaces/media-20261112/flux-q4-g352');r=w.parent/'source';s=r/'eidolon-core/docs/studies/2026-11-12-eidolon-media';e=s/'evidence-g352';e.mkdir(exist_ok=True)
b=json.loads((w/'final-bundle.json').read_text());d=b['data'];d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(s/'flux-q4-validation-g352.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(e/'visual-reviews.json').write_text(json.dumps(d['reviews'],ensure_ascii=False,indent=2)+'\n');(s/'FLUX-Q4-G352.md').write_text(b['report'])
for p in w.iterdir():
 if p.is_file() and p.suffix in ['.json','.md','.txt','.html'] and p.name not in ['final-bundle.json','git-payload.json']:shutil.copy2(p,e/p.name)
shutil.copy2(w/'transformer-config/config.json',e/'transformer-config.json')
shutil.copy2(w/'prepare-before-license-path-fix.py',e/'prepare-before-license-path-fix.py')
for sub,prefix in [('run01','smoke'),('run02','quality')]:
 for p in (w/sub).iterdir():
  if p.suffix in ['.json','.jsonl']:shutil.copy2(p,e/(prefix+'-'+p.name))
for unit in ['prepare','smoke','quality']:
 p=subprocess.run(['journalctl','--no-pager','-u','eidolon-media-flux-q4-g352-'+unit,'-o','short-iso'],text=True,capture_output=True,check=True);(e/(unit+'-journal.txt')).write_text(p.stdout)
summary=b['summary']
for name in ['README.md','ROADMAP.md']:
 p=s/name;p.write_text(p.read_text()+'\n\n## Avancement G352 — FLUX Schnell Q4, 14/11/2026\n\n'+summary+'\n')
p=s/'CANDIDATE-QUEUE-G332.md';lines=p.read_text().splitlines();found=False
for i,line in enumerate(lines):
 if line.startswith('| I09 — '):lines[i]=b['candidate_row'];found=True
assert found;p.write_text('\n'.join(lines)+'\n')
p=r/'eidolon-core/ECHANGES.md';p.write_text(p.read_text()+'\n\n## C-MSG-G352 — FLUX Schnell Q4 terminé, 14/11/2026, Codex/GPT\n\n'+summary.replace('(FLUX-Q4-G352.md)','(docs/studies/2026-11-12-eidolon-media/FLUX-Q4-G352.md)')+' Rapport illustré enregistré, preuves conservées. Aucun avis utilisateur attribué aux nouvelles images.\n')
print('Documents and evidence saved.')
