# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : export_super_charcuterie_g359.py
# Description : Vérification et export de Super Charcuterie
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,hashlib,base64,io,subprocess
from PIL import Image
w=Path('/srv/eidolon/workspaces/media-20261112/super-charcuterie-g359');o=w/'run01';r=json.loads((o/'results.json').read_text());assert len(r)==1
p=o/'00-hero.png';b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==r[0]['png_sha256'];im=Image.open(p);assert im.size==(1024,1024)
assert r[0]['forward_counts']=={'calls':28,'sequences':56};assert json.loads((o/'completion.json').read_text())['generated']==1
telemetry=json.loads((o/'telemetry.json').read_text());assert telemetry['sample_errors']==0
clients=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True);assert not clients.strip()
services=subprocess.check_output(['systemctl','is-active','eidolon-core-api','eidolon-comm','eidolon-memory-tunnel','eidolon-darme','ollama'],text=True)
(w/'image.b64').write_bytes(base64.b64encode(b));im.thumbnail((768,768));preview=io.BytesIO();im.convert('RGB').save(preview,format='JPEG',quality=90);pb=preview.getvalue();(w/'preview.b64').write_bytes(base64.b64encode(pb));manifest=json.loads((o/'manifest.json').read_text())
info={'image_chars':len((w/'image.b64').read_bytes()),'image_sha256':hashlib.sha256(b).hexdigest(),'preview_chars':len((w/'preview.b64').read_bytes()),'preview_sha256':hashlib.sha256(pb).hexdigest(),'seconds':r[0]['seconds'],'encode_seconds':manifest['encode_seconds'],'load_seconds':manifest['load_seconds'],'telemetry':telemetry,'gpu_clients':clients,'services':services,'original_path':str(p)};(w/'delivery.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
