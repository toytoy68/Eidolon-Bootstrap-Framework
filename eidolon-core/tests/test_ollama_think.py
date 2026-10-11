# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_ollama_think.py
# Description : Explicit thinking mode reaches planner and dialogue unchanged.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import unittest
from eidolon_core.ollama_model import OllamaConfig,OllamaModel
from eidolon_core.model_config import _decode,ModelConfigError
from eidolon_core.dialogue import ChatDialogueModel
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.contracts import ContractError

class Transport:
    def post(self,url,body,**kwargs):
        self.body=json.loads(body)
        raw={"model":"synthetic","message":{"role":"assistant","content":"{}"},
             "done":True,"done_reason":"stop"}
        return 200,"application/json",json.dumps(raw).encode()

class ThinkTests(unittest.TestCase):
    def test_explicit_modes_reach_both_protocols_and_identity(self):
        identities=[]
        for mode in (None,False,True):
            transport=Transport()
            adapter=OllamaModel(OllamaConfig("http://127.0.0.1:11434","synthetic",think=mode),transport)
            adapter.messages=lambda request,context: [{"role":"user","content":"synthetic"}]
            adapter.propose("synthetic",{})
            dialogue=json.loads(ChatDialogueModel(adapter,demo_catalog())._wrap([]))
            if mode is None:
                self.assertNotIn("think",transport.body)
                self.assertNotIn("think",dialogue)
                self.assertNotIn("think",adapter.config.manifest())
            else:
                self.assertIs(transport.body["think"],mode)
                self.assertIs(dialogue["think"],mode)
                self.assertIs(adapter.config.manifest()["think"],mode)
            identities.append(adapter.model_id)
        self.assertEqual(len(set(identities)),3)

    def test_private_loader_accepts_boolean_and_rejects_wrong_types(self):
        base={"version":1,"provider":"ollama","endpoint":"http://127.0.0.1:11434",
              "model":"synthetic","options":{"num_predict":64}}
        self.assertIs(_decode(json.dumps(dict(base,think=False)).encode()).config.think,False)
        for value in (0,1,"false",[],{}):
            with self.subTest(value=value),self.assertRaises(ModelConfigError):
                _decode(json.dumps(dict(base,think=value)).encode())
        with self.assertRaises(ContractError):
            OllamaConfig("http://127.0.0.1:11434","synthetic",think=0)

    def test_previous_positional_non_loopback_argument_keeps_its_meaning(self):
        config=OllamaConfig("http://192.0.2.1:11434","synthetic",{},
                            60.0,64000,256000,64000,True)
        self.assertTrue(config.allow_non_loopback)
        self.assertIsNone(config.think)
