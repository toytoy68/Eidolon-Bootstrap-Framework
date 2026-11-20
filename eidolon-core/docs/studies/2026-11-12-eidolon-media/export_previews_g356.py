# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : export_previews_g356.py
# Description : Aperçus de revue, originaux conservés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,io,zipfile,base64,hashlib,sys
from PIL import Image
w=Path('/srv/eidolon/workspaces/media-20261112/juggernaut-xi-lightning-g356')
model=sys.argv[1];indices=[int(x) for x in sys.argv[2].split(',')];name=sys.argv[3];assert model in ['xi_lightning']
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for i in indices:
  sub='run01' if model=='xi_lightning' and i==0 else 'run02';p=next((w/sub/model).glob(f'{i:02d}-*.png'))
  im=Image.open(p);im.thumbnail((768,768));out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=85)
  z.writestr(model+'/'+p.stem+'.jpg',out.getvalue())
data=b.getvalue();enc=base64.b64encode(data);(w/(name+'.b64')).write_bytes(enc)
print(json.dumps({'chars':len(enc),'sha256':hashlib.sha256(data).hexdigest(),'indices':indices,'model':model,'name':name}))
