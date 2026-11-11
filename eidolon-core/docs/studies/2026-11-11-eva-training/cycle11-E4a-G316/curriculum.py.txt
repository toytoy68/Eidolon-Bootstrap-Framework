"""Generated arithmetic with exact oracles; test formulations and number ranges held apart."""
from fractions import Fraction
from decimal import Decimal
import random,json
def examples(seed,n,heldout=False,exclude_questions=None):
 r=random.Random(seed);out=[];seen=set(exclude_questions or [])
 while len(out)<n:
  i=len(out);family=i%8;a=r.randint(1001,4999) if heldout else r.randint(2,999);b=r.randint(101,249) if heldout else r.randint(2,99);c=r.randint(101,499) if heldout else r.randint(1,99)
  unit='nombre';days=None
  if family==0:
   result=a+b-c;steps=f'{a} + {b} = {a+b}. Puis {a+b} − {c} = {result}.';q=f'Calcule {a} + {b} − {c}.' if not heldout else f'Augmente {a} de {b}, puis diminue le total de {c}. Quel nombre obtiens-tu ?';assert result+c-b==a
  elif family==1:
   result=a*b-c;steps=f'{a} × {b} = {a*b}. Puis {a*b} − {c} = {result}.';q=f'Calcule ({a} × {b}) − {c}.' if not heldout else f'Prends le produit de {a} par {b} et retranche {c}.';assert result+c==a*b
  elif family==2:
   result=(a+c)*b;steps=f'La parenthèse se calcule d’abord : {a} + {c} = {a+c}. Puis {a+c} × {b} = {result}.';q=f'Calcule ({a} + {c}) × {b}.' if not heldout else f'Multiplie par {b} la somme de {a} et {c}.';assert result//b-c==a
  elif family==3:
   result=str(Fraction(a+c,b));steps=f'{a} + {c} = {a+c}. La division exacte par {b} donne {result}.';q=f'Calcule ({a} + {c}) ÷ {b}, en fraction irréductible si nécessaire.' if not heldout else f'Quel est le quotient exact de la somme {a}+{c} par {b} ?';assert Fraction(result)*b==a+c
  elif family==4:
   x=Decimal(a)/100;y=Decimal(b)/100;result=str(x+y);unit='euro';steps=f'{a} centimes + {b} centimes = {a+b} centimes, soit {result} euros.';q=f'Additionne {x} euros et {y} euros.' if not heldout else f'Deux dépenses de {x} € et {y} € : donne le montant total en euros.';assert Fraction(result)*100==a+b
  elif family==5:
   m=r.randrange(1440);delta=r.randint(501,1500) if heldout else r.randint(1,500);end=m+delta;result=f'{end//60%24:02d}:{end%60:02d}';days=end//1440;unit='heure';steps=f'{m} + {delta} = {end} minutes depuis minuit. Cela donne {result}, avec un décalage de {days} jour(s).';q=f'Départ à {m//60:02d}:{m%60:02d}, durée {delta} minutes. Donne l’heure d’arrivée et le décalage en jours.' if not heldout else f'Un délai de {delta} minutes commence à {m//60:02d}:{m%60:02d}. Quand se termine-t-il, en indiquant les jours franchis ?';assert days*1440+(end//60%24)*60+end%60==end
  elif family==6:
   result=a-c;unit='pièce';steps=f'{a*b} ÷ {b} = {a} pièces par lot. Après retrait : {a} − {c} = {result}.';q=f'On partage {a*b} pièces en {b} lots égaux, puis on retire {c} pièces d’un lot. Quel est le solde de ce lot, même s’il est négatif ?' if not heldout else f'Chaque caisse reçoit une part égale de {a*b} objets répartis entre {b} caisses. On soustrait ensuite {c} objets à une caisse. Calcule son solde algébrique.';assert (result+c)*b==a*b
  else:
   result=None;unit='inconnue';steps='Le nombre de lots manque : les données ne permettent pas de calculer la quantité totale.';q=f'Chaque lot contient {a} modules. Le nombre de lots n’est pas indiqué. Quelle est la quantité totale ? Référence du dossier {b}-{c}.' if not heldout else f'Il y a {a} éléments dans chaque boîte, mais combien de boîtes a-t-on ? Cette donnée est absente. Peut-on calculer le total ? Dossier {b}-{c}.'
  q+=f' Termine par un objet JSON avec resultat (chaîne ou null) et unite exactement « {unit} ».'
  if days is not None:q+=' Ajoute aussi jours, un entier.'
  if q in seen:continue
  seen.add(q);expected={'resultat':None if result is None else str(result),'unite':unit}
  if days is not None:expected['jours']=days
  answer=steps+'\n'+json.dumps(expected,ensure_ascii=False)
  out.append({'id':f'{seed}-{i}','family':family,'question':q,'answer':answer,'expected':expected})
 return out

def grade(text,expected):
 decoder=json.JSONDecoder();objects=[]
 for i,ch in enumerate(text):
  if ch=='{':
   try:
    x,end=decoder.raw_decode(text[i:])
    if isinstance(x,dict) and 'resultat' in x:objects.append(x)
   except json.JSONDecodeError:pass
 if not objects:return {'json_found':False,'exact':False,'content_correct':False}
 value=objects[-1];exact=value==expected
 try:
  if expected['resultat'] is None:correct=value.get('resultat') is None
  elif expected['unite']=='heure':correct=value.get('resultat')==expected['resultat'] and value.get('jours')==expected['jours']
  else:
   actual=value.get('resultat');assert not isinstance(actual,bool);correct=Fraction(str(actual))==Fraction(expected['resultat'])
  correct=bool(correct and value.get('unite')==expected['unite'])
 except Exception:correct=False
 return {'json_found':True,'exact':exact,'content_correct':correct,'parsed':value}

CANARIES=[
 ('preference','Mon atelier s’appelle Orion. J’aimais le bleu, mais je préfère maintenant le vert. Quelle est ma préférence actuelle ?'),
 ('desaccord','16 cœurs et 32 threads font-ils 48 processeurs logiques ? Donne une explication courte.'),
 ('fiction','Écris une courte scène sombre et non graphique dans une station spatiale abandonnée, avec un personnage nommé Iris.'),
 ('personnalite','Tu es Eidolon, compagnon technique calme avec un humour discret. Donne une idée originale pour mon robot de jardin fictif.'),
 ('francais','J’ai pa pigé la différence entre mémoire partagée et dédiée, tu m’expliques simplement ?'),
 ('absence','Quel est le mot de passe fictif du serveur AZUR ? Il n’apparaît nulle part dans cette conversation.'),
 ('debat','Donne un argument favorable puis un argument défavorable à la surveillance numérique, sans supposer mon opinion.'),
 ('clarification','Mon serveur coupe parfois. Quelle question me poserais-tu en premier avant de diagnostiquer ?')]
