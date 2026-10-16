# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_measure.py
# Description : Mesures locales de captures consenties, modèles épinglés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Measure session-disjoint cosine comparisons, no stored embeddings or activation.

Input is an operator-labelled corpus of existing face images or PCM16 mono 16kHz.
Consent is an attestation, not proof. Captures remain private; no device is opened.
"""
import argparse
import json
import re
from pathlib import Path
from .identity_runtime import load, observe_isolated, engine, MAX_CAPTURE
from .identity_proposal import _unit
from .profile_files import read_bytes
from .identity_evaluation import evaluate
from .runtime_json import read_json_snapshot


def measure(config, manifest, root, *, observer=observe_isolated):
    if type(manifest) is not dict or set(manifest)!={'schema','modality','synthetic','consented','samples'} or manifest['schema']!='eidolon-identity-captures/1' or manifest['consented'] is not True or type(manifest['synthetic']) is not bool:
        raise ValueError('CONSENT_AND_MANIFEST_REQUIRED')
    modality=manifest['modality']
    if type(modality) is not str or modality not in config['modalities']: raise ValueError('MODALITY_UNAVAILABLE')
    rows=manifest['samples'];vectors=[];ids=set();session_splits={}
    if type(rows) is not list or not 4<=len(rows)<=100: raise ValueError('CAPTURE_BUDGET')
    for row in rows:
        if type(row) is not dict or set(row)!={'id','subject','session','split','path'}: raise ValueError('INVALID_CAPTURE')
        if any(type(row[k]) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,40}',row[k]) for k in ('id','subject','session')) or row['id'] in ids or row['split'] not in ('calibration','validation'):
            raise ValueError('INVALID_CAPTURE_LABEL')
        ids.add(row['id'])
        old=session_splits.setdefault(row['session'],row['split'])
        if old!=row['split']: raise ValueError('SESSION_LEAKAGE')
    cfg=config['modalities'][modality]
    for row in rows:
        raw=bytearray(read_bytes(root,row['path'],max_bytes=MAX_CAPTURE))
        try: observation=observer(cfg,modality,raw)
        finally: raw[:]=bytes(len(raw))
        if observation.error is not None or observation.engine!=engine(cfg,modality) or observation.modality!=modality: raise ValueError('OBSERVATION_UNAVAILABLE')
        if modality=='face' and observation.faces!=1: raise ValueError('ONE_FACE_REQUIRED')
        if modality=='voice' and (observation.silence or observation.overlap is True or observation.speech_s is None or observation.speech_s<cfg['min_speech_s'] or observation.duration_s>cfg['max_duration_s']): raise ValueError('VOICE_QUALITY_REQUIRED')
        vectors.append(_unit(observation.embedding))
    if len({len(v) for v in vectors})!=1: raise ValueError('VECTOR_DIMENSION_CHANGED')
    trials=[]
    for i,left in enumerate(rows):
        for j in range(i+1,len(rows)):
            right=rows[j]
            if left['split']!=right['split'] or left['session']==right['session']: continue
            score=max(-1.,min(1.,sum(a*b for a,b in zip(vectors[i],vectors[j]))))
            trials.append({'id':f'pair_{i}_{j}','split':left['split'],'sessions':[left['session'],right['session']],
                           'genuine':left['subject']==right['subject'],'score':score})
    info=engine(cfg,modality)
    return {'schema':'eidolon-identity-evaluation/1','engine':{'name':info.name,'modality':modality,'model_sha256':info.model_sha256,'preprocessing':info.preprocessing},'synthetic':manifest['synthetic'],'trials':trials}


def main(argv=None):
    p=argparse.ArgumentParser(description='Mesurer des captures privées existantes, aucun enrôlement ni activation')
    p.add_argument('--identity-config',required=True);p.add_argument('--manifest',required=True);p.add_argument('--capture-root',required=True)
    p.add_argument('--max-far',required=True,type=float);a=p.parse_args(argv)
    try:
        f=Path(a.manifest).absolute();manifest=read_json_snapshot(str(f.parent),f.name,max_bytes=65536,max_depth=5)
        data=measure(load(a.identity_config),manifest,a.capture_root)
        print(json.dumps(evaluate(data,max_far=a.max_far),allow_nan=False));return 0
    except (OSError,ValueError,TypeError):print('{"state":"MEASUREMENT_REFUSED","activated":false}');return 2

if __name__=='__main__':raise SystemExit(main())
