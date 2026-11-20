# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_feedback.py
# Description : Intégrité des jugements et séparation apprentissage/évaluation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from eidolon_core.media_agents import MediaError
from eidolon_core.media_feedback import FeedbackLedger, pair_records, verify_pair_files

def record(asset='a', decision='ACCEPT', **changes):
    result = dict(asset_id=asset, image_sha256=hashlib.sha256(asset.encode()).hexdigest(),
        prompt='one hand', config_sha256='1'*64, model_sha256='2'*64, width=1024,
        height=1024, split='train', decision=decision, reason='visible evidence',
        reviewer='gpt', confidence='high', scores=dict(fidelity=3,structure=3,composition=3,finish=3))
    result.update(changes); return result

class FeedbackTests(unittest.TestCase):
    def test_only_bad_or_uncertain_never_creates_a_winner(self):
        self.assertEqual(pair_records([record('a','REJECT'),record('b','REJECT')]),[])
        self.assertEqual(pair_records([record('a','UNCERTAIN'),record('b','REJECT')]),[])

    def test_valid_pair_requires_same_prompt_geometry_model_and_settings(self):
        a=record(); b=record('b','REJECT')
        self.assertEqual(len(pair_records([a,b])),1)
        for change in ({'prompt':'another prompt'},{'height':576},{'model_sha256':'3'*64},
                       {'config_sha256':'3'*64},{'confidence':'medium'}):
            with self.subTest(change=change):
                self.assertEqual(pair_records([a,{**b,**change}]),[])

    def test_prompt_and_image_leakage_refused(self):
        for b in (record('b','REJECT',split='holdout'),
                  record('b','REJECT',split='holdout',prompt='another prompt',image_sha256=record()['image_sha256'])):
            with self.assertRaisesRegex(MediaError,'TRAIN_HOLDOUT_LEAKAGE'):pair_records([record(),b])

    def test_no_cartesian_inflation_or_identical_image_pair(self):
        self.assertEqual(len(pair_records([record('a'),record('b','REJECT'),record('c','REJECT')])),1)
        self.assertEqual(pair_records([record('a'),record('b','REJECT',image_sha256=record('a')['image_sha256'])]),[])

    def test_user_correction_is_versioned_and_has_precedence(self):
        with tempfile.TemporaryDirectory() as d:
            book=FeedbackLedger(Path(d)/'reviews'); r=record()
            book.append(r,expected_revision=0)
            book.append({**r,'reviewer':'user','decision':'UNCERTAIN'},expected_revision=1)
            self.assertEqual(len(book.read()),2)
            self.assertEqual(book.snapshot()['records'][0]['decision'],'UNCERTAIN')
            with self.assertRaisesRegex(MediaError,'USER_REVIEW_TAKES_PRECEDENCE'):
                book.append(r,expected_revision=2)

    def test_stale_revision_identity_change_and_tampering_refused(self):
        with tempfile.TemporaryDirectory() as d:
            book=FeedbackLedger(Path(d)/'reviews'); book.append(record(),expected_revision=0)
            with self.assertRaisesRegex(MediaError,'REVISION_CONFLICT'):book.append(record(),expected_revision=0)
            with self.assertRaisesRegex(MediaError,'IDENTITY_CHANGED'):
                book.append(record(prompt='different'),expected_revision=1)
            book.path.write_text(book.path.read_text().replace('visible evidence','changed evidence'))
            with self.assertRaisesRegex(MediaError,'CHAIN_CORRUPT'):book.read()

    def test_unacceptable_scores_cannot_be_accepted(self):
        r=record();r['scores']['structure']=1
        with self.assertRaisesRegex(MediaError,'ACCEPTANCE_CRITERIA_NOT_MET'):pair_records([r])

    def test_asset_bytes_and_symlinks_checked_before_training(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a.png').write_bytes(b'a');(root/'b.png').write_bytes(b'b')
            pair=pair_records([record(),record('b','REJECT')])[0]
            self.assertEqual(len(verify_pair_files(pair,root)),2)
            (root/'a.png').write_bytes(b'changed')
            with self.assertRaisesRegex(MediaError,'IMAGE_CHANGED'):verify_pair_files(pair,root)
            (root/'a.png').unlink();(root/'a.png').symlink_to(root/'b.png')
            with self.assertRaises(OSError):verify_pair_files(pair,root)

if __name__=='__main__':unittest.main()
