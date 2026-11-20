# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : inspect_checkpoint_g356.py
# Description : Inspection CPU du checkpoint et des indices CLIP
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,struct,hashlib,collections,os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import torch
from safetensors import safe_open
w=Path('/srv/eidolon/workspaces/media-20261112/juggernaut-xi-lightning-g356');m=json.loads((w/'manifest.json').read_text())[0];p=Path(m['absolute'])
with p.open('rb') as f:
 n=struct.unpack('<Q',f.read(8))[0];assert n<5000000;b=f.read(n);header=json.loads(b)
counts=collections.Counter()
for k,v in header.items():
 if k=='__metadata__':continue
 group='vae' if k.startswith('first_stage_model.') else 'unet' if k.startswith('model.diffusion_model.') else 'text';counts[(group,v['dtype'])]+=v['data_offsets'][1]-v['data_offsets'][0]
rows=[]
with safe_open(str(p),framework='pt',device='cpu') as f:
 for k in f.keys():
  if k.endswith('embeddings.position_ids'):
   t=f.get_tensor(k);rows.append({'key':k,'shape':list(t.shape),'dtype':str(t.dtype),'values':t.tolist(),'standard_arange':torch.equal(t,torch.arange(t.shape[-1]).unsqueeze(0))})
src=Path('/srv/eidolon/workspaces/media-20261112/preference-lab/venv/lib/python3.12/site-packages/transformers/models/clip/modeling_clip.py')
d={'file':p.name,'checkpoint_sha256':m['sha256'],'header_sha256':hashlib.sha256(b).hexdigest(),'components':[{'group':k[0],'dtype':k[1],'bytes':v} for k,v in counts.items()],'position_ids':rows,'transformers_source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_excerpt':src.read_text().splitlines()[265:272]}
(w/'checkpoint-inspection.json').write_text(json.dumps(d,indent=2));print(json.dumps({k:v for k,v in d.items() if k!='position_ids'}));print('position_ids_standard',[x['standard_arange'] for x in rows])
