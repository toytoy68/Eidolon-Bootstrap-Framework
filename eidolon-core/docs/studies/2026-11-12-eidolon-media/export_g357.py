# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : export_g357.py
# Description : Aperçus sources, masques et sorties G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,io,zipfile,base64,hashlib,sys
from PIL import Image
w=Path('/srv/eidolon/workspaces/media-20261112/sdxl-inpaint-g357');name=sys.argv[1];files=[]
if name=='inputs':files=[(p,'inputs/'+p.stem+'.jpg') for p in (w/'inputs').glob('*.png')]
else:
 for i in map(int,sys.argv[2].split(',')):
  d=w/('run01' if i==0 else 'run02')/'sdxl_inpaint'
  for p in d.glob(f'{i:02d}-*.png'):
   if 'source' not in p.name and 'mask' not in p.name:files.append((p,p.stem+'.jpg'))
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p,n in files:
  im=Image.open(p).convert('RGB');im.thumbnail((768,768));s=io.BytesIO();im.save(s,format='JPEG',quality=85);z.writestr(n,s.getvalue())
data=b.getvalue();enc=base64.b64encode(data);(w/(name+'.b64')).write_bytes(enc);print(json.dumps({'name':name,'chars':len(enc),'sha256':hashlib.sha256(data).hexdigest(),'files':len(files)}))
