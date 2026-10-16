# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_evaluation.py
# Description : Services hors VM G273, configuration opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Offline calibration candidate from labelled, session-disjoint comparisons.

Scores are cosine similarities measured by the selected engine, never invented
probabilities. Synthetic input may test the tool but cannot qualify real people.
No registry/configuration is modified and no threshold is activated.
"""
import argparse
import json
import math
from .contracts import digest


def wilson(errors,total):
    if not total: return None
    z=1.95996398454;p=errors/total;d=1+z*z/total
    middle=(p+z*z/(2*total))/d
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0,middle-radius),min(1,middle+radius)]


def evaluate(data, *, max_far):
    if type(max_far) not in (int,float) or not math.isfinite(max_far) or not 0<=max_far<1:
        raise ValueError('EXPLICIT_FAR_REQUIRED')
    if type(data) is not dict or set(data)!={'schema','engine','synthetic','trials'} or data['schema']!='eidolon-identity-evaluation/1': raise ValueError('INVALID_DATASET')
    engine=data['engine']
    if type(engine) is not dict or set(engine)!={'name','modality','model_sha256','preprocessing'}: raise ValueError('INVALID_ENGINE')
    import re
    if engine['modality'] not in ('voice','face') or not all(type(engine[k]) is str and 0<len(engine[k])<=200 for k in engine) or not re.fullmatch('[0-9a-f]{64}',engine['model_sha256']): raise ValueError('INVALID_ENGINE')
    if type(data['synthetic']) is not bool or type(data['trials']) is not list or not 4<=len(data['trials'])<=10000: raise ValueError('INVALID_DATASET')
    groups={'calibration':[], 'validation':[]}; sessions={k:set() for k in groups};ids=set()
    for row in data['trials']:
        if type(row) is not dict or set(row)!={'id','split','sessions','genuine','score'}: raise ValueError('INVALID_TRIAL')
        if type(row['id']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,80}',row['id']) or row['id'] in ids: raise ValueError('DUPLICATE_TRIAL')
        ids.add(row['id']);split=row['split'];score=row['score']
        if type(split) is not str or split not in groups or type(row['genuine']) is not bool or type(score) not in (int,float) or not math.isfinite(score) or not -1<=score<=1: raise ValueError('INVALID_SCORE')
        if type(row['sessions']) is not list or len(row['sessions'])!=2 or any(type(s) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,80}',s) for s in row['sessions']): raise ValueError('INVALID_SESSION')
        sessions[split].update(row['sessions']);groups[split].append(row)
    if sessions['calibration'] & sessions['validation']: raise ValueError('SESSION_LEAKAGE')
    for rows in groups.values():
        if not any(r['genuine'] for r in rows) or not any(not r['genuine'] for r in rows): raise ValueError('BOTH_CLASSES_REQUIRED')
    def metrics(rows,threshold):
        pos=sum(r['genuine'] for r in rows);neg=len(rows)-pos
        fp=sum(not r['genuine'] and r['score']>=threshold for r in rows)
        fn=sum(r['genuine'] and r['score']<threshold for r in rows)
        return {'genuine':pos,'impostor':neg,'false_accepts':fp,'false_rejects':fn,'far':fp/neg,'frr':fn/pos,'far_wilson95':wilson(fp,neg),'frr_wilson95':wilson(fn,pos)}
    # Select on calibration only; validation never participates in threshold choice.
    calibration=groups['calibration'];pos=sum(r['genuine'] for r in calibration);neg=len(calibration)-pos
    bins={}
    for row in calibration:
        counts=bins.setdefault(row['score'],[0,0]);counts[0 if row['genuine'] else 1]+=1
    tp=fp=0;candidates=[]
    for score in sorted(bins,reverse=True):
        if score<1 and fp/neg<=max_far: candidates.append(((pos-tp)/pos,math.nextafter(score,math.inf)))
        tp+=bins[score][0];fp+=bins[score][1]
        if fp/neg<=max_far: candidates.append(((pos-tp)/pos,score))
    if not candidates: return {'state':'NO_THRESHOLD','activated':False,'engine':engine}
    _,threshold=min(candidates)
    validation=metrics(groups['validation'],threshold)
    return {'schema':'eidolon-identity-evaluation-report/1','state':'SYNTHETIC_ONLY' if data['synthetic'] else 'MEASURED_CANDIDATE_REVIEW_REQUIRED','engine':engine,
            'dataset_sha256':digest(data),'target_far':max_far,'candidate_threshold':threshold,'calibration':metrics(groups['calibration'],threshold),'validation':validation,
            'validation_meets_empirical_target':validation['far']<=max_far,'activated':False,'authorizes_execution':False,
            'limits':['Correlated trials: Wilson intervals are indicative, not independent-population guarantees.','No liveness, spoof resistance or multimodal calibration established.','Review labels, sample coverage and separate acquisition sessions before use.']}


def main(argv=None):
    p=argparse.ArgumentParser(description='Évaluation voix/visage hors ligne, seuil jamais activé')
    p.add_argument('--input',required=True);p.add_argument('--max-far',required=True,type=float);a=p.parse_args(argv)
    try:
        from .runtime_json import read_json_snapshot
        from pathlib import Path
        f=Path(a.input).absolute();data=read_json_snapshot(str(f.parent),f.name,max_bytes=4*1024*1024,max_depth=6)
        print(json.dumps(evaluate(data,max_far=a.max_far),ensure_ascii=False,allow_nan=False));return 0
    except (OSError,ValueError,TypeError): print('{"state":"EVALUATION_REFUSED","activated":false}');return 2

if __name__=='__main__': raise SystemExit(main())
