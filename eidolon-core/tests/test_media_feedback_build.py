# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_feedback_build.py
# Description : Identification de lots distincts et refus des chemins malformes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media/feedback_build.py'

class FeedbackBuildTests(unittest.TestCase):
    def fixture(self, root):
        campaign=root/'campaign';campaign.mkdir()
        summary=[];reviews=[]
        for i in range(2):
            folder=campaign/f'{i:02}';folder.mkdir();body=f'hash-test-fixture-{i}'.encode()
            (folder/'result.png').write_bytes(body)
            summary.append({'sha256':hashlib.sha256(body).hexdigest()})
            (folder/'metadata.json').write_text(json.dumps({'state':'SUCCEEDED',
                'request':{'prompt':'one object','width':1024,'height':1024},
                'graph':{'5':{'inputs':{'seed':i}},'7':{'inputs':{'filename_prefix':str(i)}}}}))
            reviews.append({'id':f'{i:02}','decision':'ACCEPT' if i==0 else 'REJECT',
                'reason':'Synthetic ledger test, no visual validation','confidence':'high',
                'scores':[3,3,3,3] if i==0 else [1,1,3,3]})
        (campaign/'summary.json').write_text(json.dumps(summary))
        (campaign/'manifest.json').write_text(json.dumps({'model_sha256':'1'*64}))
        decisions=root/'reviews.json';decisions.write_text(json.dumps(reviews))
        return [sys.executable,str(SCRIPT),'--campaign',str(campaign),'--decisions',str(decisions)]

    def test_two_lots_keep_distinct_asset_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cmd=self.fixture(root)
            for prefix in ('g329','g331'):
                out=root/prefix
                result=subprocess.run(cmd+['--output',str(out),'--asset-prefix',prefix],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                data=json.loads((out/'dataset.json').read_text())
                self.assertEqual(data['pairs'][0]['chosen'],prefix+'-00')
                self.assertEqual(data['pairs'][0]['rejected'],prefix+'-01')
                self.assertEqual(data['revision'],2)
            self.assertTrue((root/'g329/assets/g329-00.png').is_file())
            self.assertFalse((root/'g331/assets/g329-00.png').exists())

    def test_invalid_prefix_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cmd=self.fixture(root);out=root/'output'
            for value in ('../bad','/absolute','', 'a'*61):
                r=subprocess.run(cmd+['--output',str(out),'--asset-prefix',value],capture_output=True,text=True)
                self.assertEqual(r.returncode,2)
                self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
