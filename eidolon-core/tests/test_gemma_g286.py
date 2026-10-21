# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_gemma_g286.py
# Description : Format Gemma, provenance et limites de contexte
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import json
import unittest
from eidolon_core import gemma_dialogue
from eidolon_core.dialogue import ChatDialogueModel
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.ollama_model import OllamaConfig, OllamaModel


class Capture:
    def post(self,url,body,**kwargs):
        self.body=json.loads(body)
        return 200,'application/json',json.dumps({'model':self.body['model'],'done':True,'message':{'role':'assistant','content':'{"version":1,"kind":"answer","text":"Test","proposal":null}'}}).encode()


class GemmaTests(unittest.TestCase):
    def model(self,name='gemma3:4b',budget=24000):
        capture=Capture()
        adapter=OllamaModel(OllamaConfig(endpoint='http://127.0.0.1:11434',model=name,options={'num_ctx':8192,'num_predict':512},max_prompt_bytes=budget),transport=capture)
        return ChatDialogueModel(adapter,demo_catalog()),capture

    def test_full_contract_and_all_sources_preserved_without_mutation(self):
        memory={'items':[{'information_id':'first','revision':9,'content':'ALPHA_FIRST'},{'information_id':'second','revision':2,'content':'OMEGA_SECOND'}], 'index_status':{'state':'INDEX_STALE'}}
        original=copy.deepcopy(memory);model,transport=self.model()
        model.reply('Question exacte',[],memory)
        messages=transport.body['messages'];self.assertEqual(len(messages),1)
        text=messages[0]['content'];self.assertEqual(messages[0]['role'],'user')
        self.assertIn('TRUSTED CAPABILITIES',text);self.assertIn('untrusted recalled data',text);self.assertIn('INDEX_STALE',text)
        self.assertLess(text.index('OMEGA_SECOND'),text.index('ALPHA_FIRST'))
        self.assertTrue(text.endswith('MESSAGE:\nQuestion exacte'));self.assertEqual(memory,original)

    def test_other_models_keep_their_original_roles(self):
        model,transport=self.model('qwen3:4b');model.reply('Bonjour',[],None)
        self.assertEqual([m['role'] for m in transport.body['messages']],['system','user'])
        self.assertNotIn(gemma_dialogue.EXAMPLES,transport.body['messages'][0]['content'])

    def test_examples_cannot_escape_the_existing_byte_budget(self):
        model,transport=self.model(budget=10000)
        _,info=model.reply('Question préservée',[],{'items':[{'content':'x'*12000}]})
        self.assertTrue(info['memory_dropped']);self.assertLessEqual(info['prompt_bytes'],10000)
        self.assertTrue(transport.body['messages'][0]['content'].endswith('Question préservée'))

    def test_model_identity_includes_adaptation(self):
        model,_=self.model();self.assertIn('/',model.model_id.rsplit('@',1)[1])
        self.assertFalse(gemma_dialogue.supported('some/gemma3:4b'))
