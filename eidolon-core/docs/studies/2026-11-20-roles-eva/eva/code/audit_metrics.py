# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : audit_metrics.py
# Description : Spans calcules/controle et chaine horaire A requise
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import re
from review_tools import time_steps
from eva_boundary_probes import invalid_claims,_last_object,_correct
def annotations(start,duration):
 text,expected=time_steps(start,duration);spans=[]
 def mark(role,pattern,groups=(1,)):
  matches=list(re.finditer(pattern,text));assert matches,(role,pattern,text)
  for m in matches:
   for group in groups:spans.append(dict(role=role,start=m.start(group),end=m.end(group),text=m[group]))
 mark('conversion',r'= ('+str(start)+r') minutes\.',(1,))
 total=start+duration
 mark('total',r'\b'+str(start)+r' \+ '+str(duration)+r' = ('+str(total)+r') minutes\.',(1,))
 for m in re.finditer(r'(\d+) − 1440 = (\d+), jour (\d+)',text):
  spans.append(dict(role='remainder',start=m.start(2),end=m.end(2),text=m[2]))
  spans.append(dict(role='days',start=m.start(3),end=m.end(3),text=m[3]))
 for m in re.finditer(r'\d+ [≥<] 1440|jour \d+',text):spans.append(dict(role='control',start=m.start(),end=m.end(),text=m[0]))
 mark('reconversion',r'(\d+) × 60 = (\d+) ; (\d+) − (\d+) = (\d+), et \d+ < 60\.',(2,5))
 mark('HHMM',r'Arrivée (\d{2}):(\d{2}),',(1,2))
 mark('days',r'décalage (\d+) jour\(s\)',(1,))
 assert all(text[x['start']:x['end']]==x['text'] for x in spans)
 return spans
def chain_metrics(response,start,duration):
 body=response[:response.rfind('{')] if '{' in response else response
 total=start+duration;day,rem=divmod(total,1440);hh,mm=divmod(rem,60);h,m=divmod(start,60)
 conversion=re.search(r'Départ\s+(\d{2}):(\d{2})\s*=\s*(\d+)\s*[×*]\s*60\s*\+\s*(\d+)\s*=\s*(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)\s*minutes',body)
 conv=bool(conversion) and tuple(map(int,conversion.groups()))==(h,m,h,m,h*60,m,start)
 additions=[tuple(map(int,x)) for x in re.findall(r'(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)\s*minutes',body)]
 addition=(start,duration,total) in additions
 normalize=[tuple(map(int,x)) for x in re.findall(r'(\d+)\s*≥\s*1440\s*:\s*(\d+)\s*[−-]\s*1440\s*=\s*(\d+)\s*,\s*jour\s*(\d+)',body)]
 required=[];r=total
 for k in range(1,day+1):required.append((r,r,r-1440,k));r-=1440
 normalization=normalize==required
 stop=re.search(r'(\d+)\s*<\s*1440\s*:\s*(\d+)\s*jour\(s\)',body)
 stop_ok=bool(stop) and tuple(map(int,stop.groups()))==(rem,day)
 reconv=re.search(r'(\d+)\s*[×*]\s*60\s*=\s*(\d+)\s*;\s*(\d+)\s*[−-]\s*(\d+)\s*=\s*(\d+),\s*et\s*(\d+)\s*<\s*60',body)
 reconv_ok=bool(reconv) and tuple(map(int,reconv.groups()))==(hh,hh*60,rem,hh*60,mm,mm)
 arrival=re.search(r'Arrivée\s+(\d{2}):(\d{2}),\s*décalage\s+(\d+)\s*jour',body)
 arr_ok=bool(arrival) and tuple(map(int,arrival.groups()))==(hh,mm,day)
 expected=dict(resultat=f'{hh:02}:{mm:02}',unite='heure',jours=day)
 final=_correct(_last_object(response),expected);claims=invalid_claims(response)
 complete=conv and addition and normalization and stop_ok and reconv_ok and arr_ok and final and not claims
 prefix=response.lstrip().startswith('Départ')
 return dict(starts_Depart=prefix,required_chain_A_verified=bool(complete),hybrid_prefix_without_required_chain=prefix and not complete,conversion_A_parsed=bool(conversion),conversion_A_correct=conv,total_operation_present=addition,normalization_steps=len(normalize),normalization_required=day,normalization_A_correct=normalization,stop_decision_A_correct=stop_ok,reconversion_A_parsed=bool(reconv),reconversion_A_correct=reconv_ok,arrival_A_correct=arr_ok,control_compare_count=len(re.findall(r'[≥<]\s*1440',body)),control_counter_count=len(re.findall(r',\s*jour\s+\d+',body)),content_correct=bool(final),detected_false_claims=claims,scope='Required canonical A components and detected claims only; unparsed does not mean mathematically false.')
