# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : metrics.py
# Description : Scores et criteres preenregistres E4b1
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from common import P,read,save
import re,math
import eva_boundary_probes as bp
from components import integer
def rows(folder,stage,candidate):
 xs=sum([read(P/folder/f'{stage}-{candidate}-rank{r}.json')['rows'] for r in range(2)],[])
 assert len({x['id'] for x in xs})==len(xs)
 return xs
def ok(x):
 if x.get('kind')=='SG':
  o=bp._last_object(x['response']) or {};e=x['expected']
  return integer(o.get('resultat'))==e['resultat'] and o.get('signe')==e['signe'] and o.get('unite')=='nombre'
 return bool(x['evaluation']['content_correct'])
def score(xs):
 return dict(n=len(xs),correct=sum(ok(x) for x in xs),truncated=sum(x['truncated'] for x in xs),starts_Depart=sum(bool(re.match(r'^\s*Départ\b',x['response'])) for x in xs),new_full_format=sum(x.get('format') in ['A','B','C'] for x in xs),hybrid_prefix=sum(x.get('chain_metrics',{}).get('hybrid_prefix_without_required_chain',False) for x in xs),false_claim_responses=sum(bool(x.get('invalid_claims')) for x in xs))
def compare(a,b):
 aa={x['id']:x for x in a};bb={x['id']:x for x in b};assert aa.keys()==bb.keys()
 assert all(aa[k]['rank']==bb[k]['rank'] and aa[k]['identity']['batch_ids']==bb[k]['identity']['batch_ids'] for k in aa)
 gains=sum(not ok(aa[k]) and ok(bb[k]) for k in aa);losses=sum(ok(aa[k]) and not ok(bb[k]) for k in aa);n=gains+losses
 return dict(before=score(a),after=score(b),gains=gains,losses=losses,p_exact_exploratory=min(1.,2*sum(math.comb(n,i) for i in range(min(gains,losses)+1))/2**n) if n else 1.)
def summarize(folder,candidate):
 full=rows(folder,'report',candidate);assert len(full)==352
 target=[x for x in full if x['group']=='target'];anchors=[x for x in full if x['group']=='anchor'];assert len(target)==320 and len(anchors)==32
 legacy=rows(folder,'legacy',candidate)
 return dict(candidate=candidate,components={k:score(rows(folder,'component-'+k,candidate)) for k in ['X1','X2','X3']},report=score(target),day0=score([x for x in target if x['stratum'].startswith('day0-')]),anchors=score(anchors),strata={s:score([x for x in target if x['stratum']==s]) for s in sorted({x['stratum'] for x in target})},legacy={k:score([x for x in legacy if x['kind']==k]) for k in ['S1','S4','SG']})
def assess(folder,candidate,final=False):
 parent=summarize('baseline','parent');after=summarize(folder,candidate);paired={k:compare(rows('baseline','component-'+k,'parent'),rows(folder,'component-'+k,candidate)) for k in ['X1','X2','X3']}
 guards=dict(full_report=after['report']['correct']>=parent['report']['correct']-2,day0=after['day0']['correct']>=parent['day0']['correct']-1,anchors=after['anchors']['correct']>=25,no_Depart=after['report']['starts_Depart']==parent['report']['starts_Depart']==0,no_full_format_switch=after['report']['new_full_format']<=parent['report']['new_full_format']+1,primitive_stability=all(after['components'][k]['correct']>=parent['components'][k]['correct']-1 for k in ['X1','X2','X3']),legacy_SG_stability=after['legacy']['SG']['correct']>=parent['legacy']['SG']['correct']-1)
 learning={}
 for k,z in paired.items():
  before=z['before']['correct'];n=z['before']['n'];available=n-before
  if available==0:passed=z['after']['correct']==n;rule='Maintain ceiling; gain impossible'
  elif available<=5:passed=z['after']['correct']==n;rule='Ceiling-limited: all remaining errors fixed, exploratory without significance claim'
  else:passed=z['gains']-z['losses']>=2 and z['p_exact_exploratory']<=.05;rule='Net>=2 and exact paired exploratory p<=.05'
  learning[k]=dict(passed=passed,rule=rule,available_errors=available,comparison=z)
 result=dict(parent=parent,after=after,guards=guards,all_guards=all(guards.values()),learning=learning,all_learning=all(x['passed'] for x in learning.values()),final=final,qualified=all(guards.values()) and all(x['passed'] for x in learning.values()),continue_to_phase2=all(guards.values()) and not final,automatic_promotion=False)
 save(P/folder/'assessment.json',result);return result
