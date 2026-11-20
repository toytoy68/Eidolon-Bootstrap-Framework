# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : launch_g350.py
# Description : Lancement borné de la recette G350
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,subprocess,sys
root=Path('/srv/eidolon/workspaces/media-20261112');w=root/'sana-sprint-600m-g350';s=root/'source/eidolon-core/docs/studies/2026-11-12-eidolon-media'
assert (w/'prepare-complete.json').is_file()
kind=sys.argv[1];assert kind in ['smoke','quality'];out='run01' if kind=='smoke' else 'run02';indices='0' if kind=='smoke' else '1,2,3,4,5,6,7,8,9,10,11'
assert not (w/out).exists()
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
subprocess.run(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama'],check=True)
a=['sudo','-n','systemd-run','--unit=eidolon-media-sana-sprint-g350-'+kind,'--collect','--property=User=toytoy','--property=WorkingDirectory='+str(root),'--property=ProtectSystem=strict','--property=ReadWritePaths='+str(root),'--property=ReadOnlyPaths=/srv/eidolon/models /srv/eidolon/data/media-models-20261113','--property=PrivateTmp=yes','--property=NoNewPrivileges=yes','--property=IPAddressDeny=any','--property=IPAddressAllow=localhost','--property=MemoryMax=72G','--property=CPUQuota=800%','--property=RuntimeMaxSec=5400','--setenv=HF_HUB_OFFLINE=1','--setenv=TRANSFORMERS_OFFLINE=1','--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONPATH='+str(root/'source/eidolon-core/src'),'--setenv=CUDA_VISIBLE_DEVICES=GPU-a7716f02-4fbb-b36c-8b0c-2ec78c75be75','/usr/bin/flock','-n',str(root/'quality-campaign.lock'),str(root/'klein-g340/venv/bin/python'),str(s/'sana_sprint_probe_g350.py'),'--work',str(w),'--models','/srv/eidolon/data/media-models-20261113/sana-sprint-600m','--output',str(w/out),'--indices',indices]
(w/('launch-'+kind+'.json')).write_text(json.dumps(a,indent=2));subprocess.run(a,check=True)
