# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_registry.py
# Description : Catalogue et bindings génériques, sans chargement GPU des poids
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from eidolon_core.media_agents import MediaError
from eidolon_core.media_profiles import workflow, validate
from eidolon_core.media_registry import ModelRegistry

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.document={'schema':'eidolon-media-models/1','entries':{}}
        for key,kind,folder in [('base','checkpoint','checkpoints'),('style','lora','loras')]:
            (self.root/folder).mkdir();(self.root/folder/(key+'.safetensors')).write_bytes(b'test fixture, not real weights')
            self.document['entries'][key]={'type':kind,'family':'sd15','filename':key+'.safetensors',
                'sha256':hashlib.sha256(b'test fixture, not real weights').hexdigest(),'license':'fixture only',
                'source':'local unit-test fixture','approved_uses':['unit tests'],'reviewed':True}
    def tearDown(self):self.tmp.cleanup()
    def test_binds_registered_ids_only(self):
        reg=ModelRegistry(self.document,self.root)
        req=validate({'checkpoint':'base','loras':[{'id':'style','strength':0.5}]})
        graph=reg.apply(workflow(req,prefix='test'),req)
        self.assertEqual(graph['1']['inputs']['ckpt_name'],'base.safetensors')
        self.assertEqual(graph['20']['inputs']['lora_name'],'style.safetensors')
        self.assertEqual(graph['5']['inputs']['model'],['20',0])
    def test_hash_mismatch_rejected(self):
        self.document['entries']['base']['sha256']='a'*64
        with self.assertRaisesRegex(MediaError,'MODEL_HASH_MISMATCH'):ModelRegistry(self.document,self.root)
    def test_unreviewed_license_refused(self):
        self.document['entries']['base']['reviewed']=False
        with self.assertRaisesRegex(MediaError,'MODEL_REVIEW_REQUIRED'):ModelRegistry(self.document,self.root)
    def test_paths_symlinks_and_pickle_refused(self):
        for name in ['../base.safetensors','base.ckpt','/base.safetensors']:
            d=copy.deepcopy(self.document);d['entries']['base']['filename']=name
            with self.assertRaises(MediaError):ModelRegistry(d,self.root)
        (self.root/'checkpoints/base.safetensors').unlink()
        (self.root/'checkpoints/base.safetensors').symlink_to(self.root/'loras/style.safetensors')
        with self.assertRaisesRegex(MediaError,'MODEL_FILE_UNAVAILABLE'):ModelRegistry(self.document,self.root)
    def test_unknown_id_and_wrong_type_refused(self):
        reg=ModelRegistry(self.document,self.root)
        for req in [{'checkpoint':'unknown'},{'checkpoint':'style'},{'loras':[{'id':'base','strength':0.5}]}]:
            with self.assertRaises(MediaError):reg.validate(validate(req))
    def test_lora_limits_and_family(self):
        for req in [{'loras':[{'id':'style','strength':float('nan')}]},
                    {'loras':[{'id':'style','strength':2}]},
                    {'loras':[{'id':'style','strength':0.5}]*3},
                    {'profile':'wan21-text','height':320,'checkpoint':'base'}]:
            with self.assertRaises(MediaError):validate(req)

if __name__=='__main__':unittest.main()
