# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : feedback_build.py
# Description : Matérialisation privée de jugements explicitement rédigés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Import an actual review, not inferred labels or an automated evaluator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from eidolon_core.media_feedback import FeedbackLedger, checksum, verify_pair_files

def asset_prefix(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}', value):
        raise argparse.ArgumentTypeError('Invalid campaign asset prefix')
    return value

def main():
    p=argparse.ArgumentParser();p.add_argument('--campaign',type=Path,required=True)
    p.add_argument('--decisions',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--asset-prefix', type=asset_prefix, default='g329')
    a=p.parse_args();os.umask(0o077);a.output.mkdir(mode=0o700)
    assets=a.output/'assets';assets.mkdir(mode=0o700)
    book=FeedbackLedger(a.output/'ledger')
    summary=json.loads((a.campaign/'summary.json').read_text())
    manifest=json.loads((a.campaign/'manifest.json').read_text())
    decisions=json.loads(a.decisions.read_text())
    if len(decisions)!=len(summary) or len({d['id'] for d in decisions})!=len(summary):
        raise RuntimeError('INCOMPLETE_REVIEW')
    for i,d in enumerate(decisions):
        if d['id']!=f'{i:02}':raise RuntimeError('REVIEW_ORDER_MISMATCH')
        folder=a.campaign/d['id'];metadata=json.loads((folder/'metadata.json').read_text())
        if metadata['state']!='SUCCEEDED':raise RuntimeError('FAILED_GENERATION')
        body=(folder/'result.png').read_bytes();sha=hashlib.sha256(body).hexdigest()
        if sha!=summary[i]['sha256']:raise RuntimeError('RESULT_HASH_MISMATCH')
        r=metadata['request'];graph=json.loads(json.dumps(metadata['graph']))
        graph['5']['inputs'].pop('seed');graph['7']['inputs']['filename_prefix']='feedback'
        asset=f'{a.asset_prefix}-{i:02}';(assets/(asset+'.png')).write_bytes(body)
        record=dict(asset_id=asset,image_sha256=sha,prompt=r['prompt'],config_sha256=checksum(graph),
            model_sha256=manifest['model_sha256'],width=r['width'],height=r['height'],split='train',
            decision=d['decision'],reason=d['reason'],reviewer='gpt',confidence=d['confidence'],
            scores=dict(zip(('fidelity','structure','composition','finish'),d['scores'])))
        book.append(record,expected_revision=i)
    snapshot=book.snapshot()
    for pair in snapshot['pairs']:verify_pair_files(pair,assets)
    snapshot['decisions_sha256']=hashlib.sha256(a.decisions.read_bytes()).hexdigest()
    snapshot['source_campaign']=str(a.campaign)
    (a.output/'dataset.json').write_text(json.dumps(snapshot,indent=2))
    print(json.dumps({'records':len(snapshot['records']),'pairs':len(snapshot['pairs']),
                      'revision':snapshot['revision'],'ledger_hash':snapshot['ledger_hash']}),flush=True)

if __name__=='__main__':main()
