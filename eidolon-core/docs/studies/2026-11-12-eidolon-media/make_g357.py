# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : make_g357.py
# Description : Rapport illustré des retouches SDXL G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
R=Path(__file__).parent;D=json.loads((R/'g357-data.json').read_text());Q=D['summary'];W,H=A4
pdfmetrics.registerFont(TTFont('DV','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'));pdfmetrics.registerFont(TTFont('DV-Bold','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'));pdfmetrics.registerFontFamily('DV',normal='DV',bold='DV-Bold',italic='DV',boldItalic='DV-Bold')
c=canvas.Canvas(str(R/'Eidolon-retouches-SDXL-Inpainting-G357.pdf'),pagesize=A4);c.setTitle('Eidolon - SDXL Inpainting - G357')
st=ParagraphStyle('p',fontName='DV',fontSize=10,leading=15,textColor=HexColor('#24364e'));small=ParagraphStyle('s',parent=st,fontSize=8.5,leading=12)
def page(title,sub,n):
 c.setFillColor(HexColor('#0b2037'));c.rect(0,H-120,W,120,fill=1,stroke=0);c.setFillColor(HexColor('#9bd2ff'));c.setFont('DV',8);c.drawString(34,H-29,'EIDOLON CORE TECHNOLOGIES / G357 / 14 NOVEMBRE 2026');c.setFillColor(HexColor('#ffffff'));c.setFont('DV-Bold',20);c.drawString(34,H-64,title);c.setFont('DV',9);c.drawString(34,H-94,sub);c.setFillColor(HexColor('#64778d'));c.setFont('DV',7);c.drawString(34,23,'SDXL Inpainting : Diffusers / Stability AI. Images sources : RunDiffusion / KandooAI.');c.drawRightString(W-34,23,str(n))
def para(t,y,x=34,width=W-68,style=st):
 p=Paragraph(t,style);_,h=p.wrap(width,700);p.drawOn(c,x,y-h);return y-h-10
def pic(p,x,y,width,maxh):
 im=ImageReader(str(p));iw,ih=im.getSize();sc=min(width/iw,maxh/ih);c.drawImage(im,x+(width-iw*sc)/2,y-ih*sc,width=iw*sc,height=ih*sc)
page('SDXL Inpainting : peut-il réparer ?','Quatre défauts G356, deux graines par retouche, masques figés',1)
y=para(f'<b>{Q["proposed"]}/8 retouches natives proposées</b>, {Q["review"]} à revoir, {Q["rejected"]} rejetées. Revue GPT provisoire, aucune validation utilisateur attribuée.',H-148)
rows=[['Mesure','Résultat'],['Modèle','SDXL Inpainting 0.1 dédié, UNet 9 canaux'],['Recette','Euler auteur, 20 étapes, force 0,99, CFG 8'],['Appels UNet réellement exécutés','19 par retouche'],['Temps médian 1024²',f'{Q["median_seconds"]:.2f} s'],['GPU / pic VRAM',f'Une V100 / {Q["peak_mib"]:.0f} Mio'],['Températures max GPU / mémoire',f'{Q["gpu_c"]:.0f} / {Q["hbm_c"]:.0f} °C'],['Répétition','Brute et composite pixel-identiques'],['Préservation hors masque','Exacte après recomposition explicite']]
t=Table(rows,colWidths=[231,296]);t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DV'),('FONTSIZE',(0,0),(-1,-1),9),('BACKGROUND',(0,0),(-1,0),HexColor('#dceeff')),('FONTNAME',(0,0),(-1,0),'DV-Bold'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,HexColor('#cbd5e1'))]));_,h=t.wrap(W-68,700);t.drawOn(c,34,y-h);y-=h+18
for text in D['summary_paragraphs']:y=para(text,y)
c.showPage()
names={'hand':'Réparer une main','objects':'Corriger les objets','katana':'Ajouter le fourreau','duo':'Changer le vêtement'}
col=(W-84)/2
for i in range(1,9):
 row=next(x for x in D['results'] if x['phase']=='focused' and x['index']==i);case=row['case'];page(names[case],f'G357-{i:02d} | 1024 x 1024 | seed {row["seed"]} | même source et même masque',i+1);y=H-147
 for x,phase,label in [(34,'baseline','Prompt de scène initial'),(50+col,'focused','Prompt ciblé sur la zone')]:
  c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',10);c.drawString(x,y,label);folder=R/'g357-images'/('focused' if phase=='focused' else '');pic(folder/f'{i:02d}-{case}.jpg',x,y-16,col,246)
 y-=282
 for x,label,suffix in [(34,'Source G356','source'),(50+col,'Masque figé : zone rose','overlay')]:
  c.setFont('DV-Bold',9);c.drawString(x,y,label);pic(R/'g357-images/inputs'/f'{case}-{suffix}.jpg',x,y-14,col,100)
 y-=130
 for phase,label in [('baseline','Initial'),('focused','Ciblé')]:
  n=D['reviews'][phase][str(i)];y=para(f'<b>{label} : {n["verdict"]}</b> - '+n['comment'],y)
 a=next(x for x in D['results'] if x['phase']=='baseline' and x['index']==i)
 para(f"Temps initial / ciblé : {a['seconds']:.2f} / {row['seconds']:.2f} s. Écart brut hors masque : {a['preservation']['raw_outside_mae']:.2f} / {row['preservation']['raw_outside_mae']:.2f} sur 255. Après collage : 0 exactement dans les deux cas.",y,style=small);c.showPage()
page('Contrôle à 512 pixels','G357-00 | hors score natif | première qualification technique',10);y=H-147
for x,label,path in [(34,'Source G356',R/'g357-images/inputs/hand-source.jpg'),(50+col,'Retouche recomposée',R/'g357-images/00-hand.jpg')]:
 c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',10);c.drawString(x,y,label);pic(path,x,y-18,col,246)
y-=290;y=para('<b>Rejetée.</b> '+D['reviews']['baseline']['0']['comment'],y)
y=para('La sortie brute était déjà déformée ; le collage rend en plus la différence de teinte visible à la frontière du masque. Cette image a motivé une vérification à la résolution native, sans modification des masques.',y)
pic(R/'g357-images/00-raw.jpg',34,y-10,180,180);c.showPage()
page('Deux répétitions exactes','G357-09 | contrôle de reproductibilité, distinct de la qualité',11);y=H-147
for x,phase,label in [(34,'baseline','Prompt initial'),(50+col,'focused','Prompt ciblé')]:
 c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',10);c.drawString(x,y,label);folder=R/'g357-images'/('focused' if phase=='focused' else '');pic(folder/'09-hand.jpg',x,y-18,col,246)
y-=290
for phase,label in [('baseline','Initial'),('focused','Ciblé')]:y=para('<b>'+label+' :</b> '+D['reviews'][phase]['9']['comment'],y)
para('Les pixels et les SHA des PNG répétés correspondent à ceux de 01 dans chaque passe. Cela prouve une répétabilité dans cette pile et cette recette ; cela ne constitue pas une validation anatomique.',y);c.showPage()
page('Masques vide et plein','G357-10 et G357-11 | contrôles hors score principal',12);y=H-147
for x,i,label in [(34,10,'Masque vide : composite'),(50+col,11,'Masque plein : sortie brute')]:
 c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',10);c.drawString(x,y,label);pic(R/'g357-images'/f'{i:02d}-objects.jpg',x,y-18,col,246)
y-=290
for i in [10,11]:y=para('<b>'+D['reviews']['baseline'][str(i)]['verdict']+' :</b> '+D['reviews']['baseline'][str(i)]['comment'],y)
para('Le masque vide confirme que la conservation exacte est assurée par le collage de la source. Le masque plein n’offre aucune zone préservée. Aucune de ces images ne compte parmi les huit retouches locales.',y);c.showPage()
page('Sorties brutes des deux passes','A = prompt initial ; B = prompt ciblé. Aucun collage sur cette planche.',13)
for idx,(phase,i) in enumerate([(phase,i) for i in range(1,9) for phase in ['baseline','focused']]):
 row=next(x for x in D['results'] if x['phase']==phase and x['index']==i);x=34+(idx%4)*133;y=H-145-(idx//4)*148;c.setFillColor(HexColor('#24364e'));c.setFont('DV',8);c.drawString(x,y,f'{i:02d} '+('A' if phase=='baseline' else 'B'));folder=R/'g357-images'/('focused' if phase=='focused' else '');pic(folder/f'{i:02d}-raw.jpg',x,y-10,126,126)
para('Les différences hors masque sont mesurées sur les originaux PNG, pas sur ces aperçus. Les 42 sorties brutes et recomposées sont conservées sur Eidolon-OS.',95,style=small);c.showPage()
page('Méthode et limites','Retouche locale contrôlée, distincte du classement texte-vers-image',14);y=H-149
for text in D['method_paragraphs']:y=para(text,y)
c.save();print(R/'Eidolon-retouches-SDXL-Inpainting-G357.pdf')
