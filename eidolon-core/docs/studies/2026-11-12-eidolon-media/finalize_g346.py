# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : finalize_g346.py
# Description : Archivage du lot SD3.5 G346 après revue
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,shutil,subprocess,datetime
w=Path('/srv/eidolon/workspaces/media-20261112/sd35-medium-g346');r=w.parent/'source';s=r/'eidolon-core/docs/studies/2026-11-12-eidolon-media';e=s/'evidence-g346';e.mkdir(exist_ok=True)
b=json.loads((w/'final-bundle.json').read_text());d=b['data'];d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(s/'sd35-medium-validation-g346.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(e/'visual-reviews.json').write_text(json.dumps(d['reviews'],ensure_ascii=False,indent=2)+'\n');(s/'SD35-MEDIUM-G346.md').write_text(b['report'])
for p in w.iterdir():
 if p.is_file() and (p.suffix in ['.json','.md','.txt'] or p.name in ['prepare-attempt01.py','runner-attempt01.py','runner-attempt02.py','launch-attempt01.py','launch-attempt02.py']):
  if p.name not in ['final-bundle.json','git-payload.json']:shutil.copy2(p,e/p.name)
for sub,prefix in [('run01','attempt01'),('run02','attempt02'),('run03','smoke'),('run04','quality')]:
 for p in (w/sub).iterdir():
  if p.suffix in ['.json','.jsonl']:shutil.copy2(p,e/(prefix+'-'+p.name))
for unit in ['prepare','prepare2','smoke','smoke2','smoke3','quality3']:
 p=subprocess.run(['journalctl','--no-pager','-u','eidolon-media-sd35-g346-'+unit,'-o','short-iso'],text=True,capture_output=True,check=True);(e/(unit+'-journal.txt')).write_text(p.stdout)
models=Path('/srv/eidolon/data/media-models-20261113/sd35-medium')
for name in ['LICENSE.md','model_index.json','scheduler/scheduler_config.json','transformer/config.json','vae/config.json','text_encoder/config.json','text_encoder_2/config.json','text_encoder_3/config.json']:
 shutil.copy2(models/name,e/('model-'+name.replace('/','-')))
summary=b['summary']
for name in ['README.md','ROADMAP.md']:
 p=s/name;p.write_text(p.read_text()+'\n\n## Avancement G346 — SD3.5 Medium, 14/11/2026\n\n'+summary+'\n')
p=s/'CANDIDATE-QUEUE-G332.md';t=p.read_text();old='| I24 — Stable Diffusion 3.5 Medium 2,5B | Générateur modeste mais encodeurs lourds | Encodeurs et/ou blocs séparés | Stability Community License, conditions/revenu à vérifier | Non testé, stabilité FP16 à vérifier |';assert old in t;t=t.replace(old,b['candidate_row']);p.write_text(t)
p=r/'eidolon-core/ECHANGES.md';p.write_text(p.read_text()+'\n\n## C-MSG-G346 — SD3.5 Medium terminé, 14/11/2026, Codex/GPT\n\n'+summary.replace('(SD35-MEDIUM-G346.md)','(docs/studies/2026-11-12-eidolon-media/SD35-MEDIUM-G346.md)')+' Rapport illustré enregistré ; preuves et incidents conservés dans evidence-g346. Aucun avis utilisateur attribué aux nouvelles images.\n')
print('Documents and evidence saved.')
