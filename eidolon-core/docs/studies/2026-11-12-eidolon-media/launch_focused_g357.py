# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : launch_focused_g357.py
# Description : Lancement borné de la recette G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,subprocess,sys
root=Path('/srv/eidolon/workspaces/media-20261112');w=root/'sdxl-inpaint-g357';s=root/'source/eidolon-core/docs/studies/2026-11-12-eidolon-media'
assert (w/'prepare-complete.json').is_file()
kind='focused';out='run03'
assert not (w/out).exists()
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
subprocess.run(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama'],check=True)
a=['sudo','-n','systemd-run','--unit=eidolon-media-sdxl-inpaint-g357-'+kind,'--collect','--property=User=toytoy','--property=WorkingDirectory='+str(root),'--property=ProtectSystem=strict','--property=ReadWritePaths='+str(root),'--property=ReadOnlyPaths=/srv/eidolon/models /srv/eidolon/data/media-models-20261113','--property=PrivateTmp=yes','--property=NoNewPrivileges=yes','--property=IPAddressDeny=any','--property=IPAddressAllow=localhost','--property=MemoryMax=72G','--property=CPUQuota=800%','--property=RuntimeMaxSec=5400','--setenv=HF_HUB_OFFLINE=1','--setenv=TRANSFORMERS_OFFLINE=1','--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONPATH='+str(root/'source/eidolon-core/src'),'--setenv=CUDA_VISIBLE_DEVICES=GPU-a7716f02-4fbb-b36c-8b0c-2ec78c75be75','/usr/bin/flock','-n',str(root/'quality-campaign.lock'),str(root/'preference-lab/venv/bin/python'),str(s/'sdxl_inpaint_focused_probe_g357.py'),'--root',str(root),'--manifest',str(w/'manifest.json'),'--mode','quality','--output',str(w/out)]
(w/('launch-'+kind+'.json')).write_text(json.dumps(a,indent=2));subprocess.run(a,check=True)
