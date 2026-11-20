# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : make_g349.py
# Description : Rapport illustré comparatif SD3.5 Large
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
ROOT=Path(__file__).parent
D=json.loads((ROOT/'g348-data.json').read_text());S=json.loads((ROOT/'g340-data.json').read_text());K=json.loads((ROOT/'g349-data.json').read_text());R=json.loads((ROOT/'g349-reviews.json').read_text());DR=json.loads((ROOT/'g348-reviews.json').read_text());SR=json.loads((ROOT/'g340-reviews.json').read_text())
pdfmetrics.registerFont(TTFont('DV','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'));pdfmetrics.registerFont(TTFont('DV-Bold','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'));pdfmetrics.registerFontFamily('DV',normal='DV',bold='DV-Bold',italic='DV',boldItalic='DV-Bold')
W,H=A4;c=canvas.Canvas(str(ROOT/'Eidolon-comparatif-SD35Large-G349.pdf'),pagesize=A4);c.setTitle('Eidolon - SD3.5 Large - G349')
style=ParagraphStyle('p',fontName='DV',fontSize=10,leading=15,textColor=HexColor('#24364e'));small=ParagraphStyle('s',parent=style,fontSize=8.5,leading=12)
def page(title,sub,n):
 c.setFillColor(HexColor('#0b2037'));c.rect(0,H-120,W,120,fill=1,stroke=0);c.setFillColor(HexColor('#9bd2ff'));c.setFont('DV',8);c.drawString(34,H-29,'EIDOLON CORE TECHNOLOGIES / G349 / 14 NOVEMBRE 2026');c.setFillColor(HexColor('#ffffff'));c.setFont('DV-Bold',20);c.drawString(34,H-64,title);c.setFont('DV',9);c.drawString(34,H-94,sub);c.setFillColor(HexColor('#64778d'));c.setFont('DV',7);c.drawString(34,23,'Revue GPT provisoire / génération locale / aucune promotion automatique.');c.drawRightString(W-34,23,str(n))
def p(text,y,x=34,width=W-68,st=style):
 obj=Paragraph(text,st);_,h=obj.wrap(width,700);obj.drawOn(c,x,y-h);return y-h-12
def pic(path,x,y,width,maxh):
 im=ImageReader(str(path));iw,ih=im.getSize();sc=min(width/iw,maxh/ih);c.drawImage(im,x+(width-iw*sc)/2,y-ih*sc,width=iw*sc,height=ih*sc);return y-ih*sc
quality=lambda d:[r for r in d['results'] if r['condition']=='quality']
page('SD3.5 Large : G349','Même grille de scènes - qualité visuelle, conformité et coût de calcul',1)
y=p(K['conclusion'],H-148)
rows=[['Mesure','Large Turbo G348','Klein G340','Large G349'],['Étapes / guidage','4 / 0','4 / 1','28 / 3,5'],['GPU + décodage 1024²']+[f"{statistics.median(x['seconds'] for x in quality(d)):.2f} s" for d in [D,S,K]],['Encodage CPU¹']+[f"{d['manifest']['encode_seconds']:.2f} s" for d in [D,S,K]],['Propositions / 8']+[str(sum(r[str(i)]['verdict']=='Proposée' for i in range(1,9)))+'/8' for r in [DR,SR,R]]]
t=Table(rows,colWidths=[209,106,106,106]);t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DV'),('FONTSIZE',(0,0),(-1,-1),8),('BACKGROUND',(0,0),(-1,0),HexColor('#dceeff')),('FONTNAME',(0,0),(-1,0),'DV-Bold'),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.3,HexColor('#cbd5e1'))]));_,th=t.wrap(W-68,700);t.drawOn(c,34,y-th);y-=th+22
y=p('¹ SD3.5 : mêmes cinq encodages réutilisés pour Large ; Klein : quatre scènes. Temps hors encodage et chargement ; contrôles intermédiaires inclus. Recettes différentes : ces mesures comparent les configurations testées, sans isoler le seul effet du modèle.',y)
for line in K['summary_paragraphs']:y=p(line,y)
c.showPage()
names={'hand':'Main ouverte','objects':'Tasse rouge et bol bleu','katana':'Katana et fourreau','duo':'Duo devant le château'}
for row in K['results']:
 i=row['index'];case=row['case'];v=R[str(i)];page(names[case],f"G349-{i:02d} | {row['width']} x {row['height']} | seed {row['seed']} | {row['condition']}",i+2)
 # Larger new candidate, compact historical references directly below.
 bottom=pic(ROOT/'g349-images'/f'{i:02d}-{case}.jpg',34,H-140,W-68,310)
 y=p('<b>Large : '+v['verdict']+'</b> - '+v['comment'],bottom-12)
 col=(W-84)/2
 for x,label,folder,rev in [(34,'Large Turbo G348','g348-images',DR[str(i)]),(50+col,'Klein G340','g340-images',SR[str(i)])]:
  c.setFillColor(HexColor('#24364e'));c.setFont('DV-Bold',9);c.drawString(x,y-4,label+' : '+rev['verdict']);pic(ROOT/folder/f'{i:02d}-{case}.jpg',x,y-13,col,115)
 y-=145;y=p(v['comparison'],y,st=small)
 p(f"Calcul GPU + décodage Large : {row['seconds']:.2f} s. "+v['rendering'],y,st=small);c.showPage()
page('Méthode et limites','Recherche locale sur V100 ; recettes historiques conservées',len(K['results'])+2);y=H-149
for line in K['method_paragraphs']:y=p(line,y)
c.save();print(ROOT/'Eidolon-comparatif-SD35Large-G349.pdf')
