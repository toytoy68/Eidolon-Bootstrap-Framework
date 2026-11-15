# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : make_g353.py
# Description : Rapport illustré Juggernaut v9 et v10
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
ROOT=Path(__file__).parent;D=json.loads((ROOT/'g353-data.json').read_text());R=D['reviews']
pdfmetrics.registerFont(TTFont('DV','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'));pdfmetrics.registerFont(TTFont('DV-Bold','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'));pdfmetrics.registerFontFamily('DV',normal='DV',bold='DV-Bold',italic='DV',boldItalic='DV-Bold')
W,H=A4;c=canvas.Canvas(str(ROOT/'Eidolon-comparatif-JuggernautX-G353.pdf'),pagesize=A4);c.setTitle('Eidolon - Juggernaut v9 contre v10 - G353')
style=ParagraphStyle('p',fontName='DV',fontSize=10,leading=15,textColor=HexColor('#24364e'));small=ParagraphStyle('s',parent=style,fontSize=9,leading=13)
def page(title,sub,n):
 c.setFillColor(HexColor('#0b2037'));c.rect(0,H-120,W,120,fill=1,stroke=0);c.setFillColor(HexColor('#9bd2ff'));c.setFont('DV',8);c.drawString(34,H-29,'EIDOLON CORE TECHNOLOGIES / G353 / 14 NOVEMBRE 2026');c.setFillColor(HexColor('#ffffff'));c.setFont('DV-Bold',20);c.drawString(34,H-64,title);c.setFont('DV',9);c.drawString(34,H-94,sub);c.setFillColor(HexColor('#64778d'));c.setFont('DV',7);c.drawString(34,23,'Revue GPT provisoire / génération locale / aucune promotion automatique.');c.drawRightString(W-34,23,str(n))
def p(text,y,x=34,width=W-68,st=style):
 obj=Paragraph(text,st);_,h=obj.wrap(width,700);obj.drawOn(c,x,y-h);return y-h-12
def pic(path,x,y,width,maxh):
 im=ImageReader(str(path));iw,ih=im.getSize();sc=min(width/iw,maxh/ih);c.drawImage(im,x+(width-iw*sc)/2,y-ih*sc,width=iw*sc,height=ih*sc);return y-ih*sc
page('Juggernaut : v9 contre v10','Même matériel, mêmes prompts, mêmes seeds et mêmes paramètres',1)
y=p(D['conclusion'],H-148)
rows=[['Mesure','Juggernaut v9','Juggernaut X v10'],['Étapes / CFG','30 / 5','30 / 5'],['V100 utilisées','1','1']]
for label,key,fmt in [('Temps médian 1024²','median_seconds','{:.2f} s'),('Pic VRAM','peak_mib','{:.0f} Mio'),('Images proposées','proposed','{}/8'),('À revoir','review','{}'),('Rejetées','rejected','{}')]:rows.append([label]+[fmt.format(D['summary'][n][key]) for n in ['v9','v10']])
t=Table(rows,colWidths=[243,142,142]);t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DV'),('FONTSIZE',(0,0),(-1,-1),9),('BACKGROUND',(0,0),(-1,0),HexColor('#dceeff')),('FONTNAME',(0,0),(-1,0),'DV-Bold'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,HexColor('#cbd5e1'))]));_,th=t.wrap(W-68,700);t.drawOn(c,34,y-th);y-=th+18
for line in D['summary_paragraphs']:y=p(line,y)
c.showPage()
names={'hand':'Main ouverte','objects':'Tasse rouge et bol bleu','katana':'Katana et fourreau','duo':'Duo devant le château'}
for i in range(12):
 row=next(x for x in D['results'] if x['model']=='v10' and x['index']==i);case=row['case'];page(names[case],f"G353-{i:02d} | {row['width']} x {row['height']} | seed {row['seed']} | {row['condition']}",i+2)
 col=(W-84)/2;y=H-147
 for x,model,label in [(34,'v9','Juggernaut v9 - témoin'),(50+col,'v10','Juggernaut X v10')]:
  c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',11);c.drawString(x,y,label);pic(ROOT/'g353-images'/model/f'{i:02d}-{case}.jpg',x,y-18,col,255)
 y-=290
 for model in ['v9','v10']:
  note=R[model][str(i)];row=next(x for x in D['results'] if x['model']==model and x['index']==i)
  y=p(f'<b>{model} : {note["verdict"]}</b> - '+note['comment'],y)
  y=p(f'Temps génération, encodage compris : {row["seconds"]:.2f} s.',y,st=small)
 y=p('<b>Comparaison :</b> '+D['comparisons'][str(i)],y)
 p('Avis GPT provisoires. Les contrôles 00 et 09-11 sont exclus du score sur huit images natives.',y,st=small);c.showPage()
page('Méthode et limites','Protocole local reproductible ; images originales et preuves conservées',14);y=H-149
for line in D['method_paragraphs']:y=p(line,y)
c.save();print(ROOT/'Eidolon-comparatif-JuggernautX-G353.pdf')
