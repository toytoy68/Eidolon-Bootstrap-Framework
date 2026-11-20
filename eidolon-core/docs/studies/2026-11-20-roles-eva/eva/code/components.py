# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : components.py
# Description : Oracles et notation des pieces horaires isolees
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json,re
def make(kind,n,variant=0,ident=''):
 if kind=='X1':
  h,m=divmod(n,60);q=[f'Convertis {h:02}:{m:02} en minutes depuis minuit.',f'Combien de minutes depuis minuit correspondent a {h:02}:{m:02} ?'][variant]
  expected=dict(resultat=str(n),unite='minute');a=f'{h} × 60 + {m} = {h*60} + {m} = {n}.'
 elif kind=='X2':
  q=[f'{n} minutes : combien de jours entiers de 1440 et quel reste en minutes ?',f'Decompose {n} minutes en jours de 1440 minutes et reste.'][variant]
  parts=[];r=n;k=0
  while r>=1440:
   parts.append(f'{r} ≥ 1440 : {r} − 1440 = {r-1440}, jour {k+1}.');r-=1440;k+=1
  parts.append(f'{r} < 1440 : {k} jour(s), reste {r}.');a=' '.join(parts);expected=dict(resultat=str(r),unite='minute',jours=k)
 elif kind=='X3':
  h,m=divmod(n,60);q=[f'Convertis {n} minutes depuis minuit en heure HH:MM.',f'Quelle heure HH:MM correspond a {n} minutes depuis minuit ?'][variant]
  a=f'{h} × 60 = {h*60} ; {n} − {h*60} = {m}, et {m} < 60. {h:02}:{m:02}.';expected=dict(resultat=f'{h:02}:{m:02}',unite='heure')
 else:raise ValueError(kind)
 q+=' Termine par un objet JSON avec resultat, unite exactement « '+expected['unite']+' »'+(' et jours, un entier.' if kind=='X2' else '.')
 return dict(id=ident,kind=kind,skill='component-'+kind,group='component',family=-1,stratum=kind+'-template'+str(variant),value=n,variant=variant,question=q,answer=a+'\n'+json.dumps(expected,ensure_ascii=False),expected=expected)
def integer(v):
 if isinstance(v,bool):return None
 if isinstance(v,int):return v
 if isinstance(v,str) and re.fullmatch(r'[−-]?\d+',v.strip()):return int(v.strip().replace('−','-'))
 return None
def correct(obj,ex):
 if not isinstance(obj,dict) or obj.get('unite')!=ex['expected']['unite']:return False
 k=ex['kind'];exp=ex['expected'];v=obj.get('resultat')
 if k in ['X1','X2']:
  if integer(v)!=int(exp['resultat']):return False
  return k!='X2' or isinstance(obj.get('jours'),int) and not isinstance(obj.get('jours'),bool) and obj['jours']==exp['jours']
 if not isinstance(v,str):return False
 m=re.fullmatch(r'(\d{1,2}):(\d{2})',v.strip())
 return bool(m) and 0<=int(m[1])<24 and 0<=int(m[2])<60 and int(m[1])*60+int(m[2])==ex['value']
