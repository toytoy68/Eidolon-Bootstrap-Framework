# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : inputs_g357.py
# Description : Sources et masques figés avant retouche G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw
R=Path('/srv/eidolon/workspaces/media-20261112');W=R/'sdxl-inpaint-g357';D=W/'inputs';D.mkdir(exist_ok=False)
ref=R/'source/eidolon-core/docs/studies/2026-11-12-eidolon-media/juggernaut-xi-lightning-validation-g356.json';j=json.loads(ref.read_text());records=[]
specs=[('hand',1,[(210,130),(740,130),(740,800),(600,900),(350,900),(240,750)],'Reconstruire une main ouverte avec cinq doigts.'),('objects',3,[(10,340),(1014,340),(1014,835),(10,835)],'Remplacer tous les récipients par exactement une tasse rouge à gauche et un bol bleu à droite.'),('katana',6,[(45,800),(780,65),(840,125),(105,860)],'Ajouter un fourreau noir à gauche et parallèle au sabre existant, sans modifier le sabre.'),('duo',7,[(571,381),(636,384),(680,420),(703,487),(679,511),(660,507),(653,580),(668,748),(577,748),(569,607),(559,531),(559,461)],'Changer la tenue noire de la femme en kimono rouge, en préservant les deux visages et le samouraï.')]
for case,index,points,target in specs:
 src=R/f'juggernaut-xi-lightning-g356/run02/xi_lightning/{index:02d}-{case}.png';meta=next(x for x in j['new_results'] if x['index']==index);assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256'];im=Image.open(src).convert('RGB');assert im.size==(1024,1024);im.save(D/(case+'-source.png'))
 mask=Image.new('L',im.size,0);ImageDraw.Draw(mask).polygon(points,fill=255);mask.save(D/(case+'-mask.png'));overlay=Image.blend(im,Image.new('RGB',im.size,(255,30,180)),.4);Image.composite(overlay,im,mask).save(D/(case+'-overlay.png'))
 records.append({'case':case,'index':index,'source':str(src),'source_sha256':meta['sha256'],'copied_sha256':hashlib.sha256((D/(case+'-source.png')).read_bytes()).hexdigest(),'mask_sha256':hashlib.sha256((D/(case+'-mask.png')).read_bytes()).hexdigest(),'polygon':points,'target':target,'prompt':meta['prompt'],'mask_pixels':mask.histogram()[255],'mask_fraction':mask.histogram()[255]/1024**2})
(W/'inputs.json').write_text(json.dumps({'reference':str(ref),'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),'reference_commit':'8e106400bac8754d8a17ae5c3703529e0251454e','masks_fixed_before_generation':True,'cases':records},ensure_ascii=False,indent=2));print('Four sources and masks fixed')
