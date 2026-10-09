# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g086_sources.py
# Description : Revue des sources citées après retrait mémoire pour budget de dialogue
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import tempfile
from eidolon_core.dialogue import ChatDialogueModel, Dialogue, build_messages
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.memory import SyntheticMemory
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatModel
from eidolon_core.store import Store

class Memory(SyntheticMemory):
    def recall(self, query):
        result=super().recall(query)
        result['items'][0]['content']='SYNTHETIC_MEMORY_SENTINEL ' + 'x'*3500
        return result

class Transport:
    def __init__(self): self.bodies=[]
    def post(self, url, body, **kwargs):
        self.bodies.append(json.loads(body))
        return 200, 'application/json', json.dumps({'object':'chat.completion','model':'fixture',
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(
                {'version':1,'kind':'answer','text':'Réponse synthétique sans mémoire.','proposal':None})}}]}).encode()

def main():
    with tempfile.TemporaryDirectory(prefix='eidolon-g086-sources-') as folder:
        runtime=synthetic_runtime(Store(Path(folder)/'state'))
        store=ConversationStore(runtime.store,create=True)
        cid=store.open(client_id='fixture',client_key='source')['conversation_id']
        transport=Transport()
        adapter=OpenAIChatModel(OpenAIChatConfig(endpoint='http://127.0.0.1:9',model='fixture',
            options={'max_tokens':64},max_prompt_bytes=3000),transport=transport)
        model=ChatDialogueModel(adapter,runtime.catalog)
        base=len(model._wrap(build_messages('Bonjour',[],None,runtime.catalog)))
        assert base < 3000, base
        result=Dialogue(store,model,runtime.catalog,memory=Memory()).respond(
            cid,client_id='fixture',client_turn_key='t1',text='Bonjour')
        assert result['diagnostics']['memory_dropped'] is True
        assert len(transport.bodies)==1
        assert 'SYNTHETIC_MEMORY_SENTINEL' not in json.dumps(transport.bodies)
        assert result['reply']['sources']==[]
        print(json.dumps({'status':'FIX_VERIFIED','source':'C107 / b654a3b','id':'G086-R1',
            'synthetic_transport_only':True,'memory_dropped':True,'memory_sent':False,
            'reply_kind':result['reply']['kind'],'sources':result['reply']['sources'],
            'prompt_bytes':result['diagnostics']['prompt_bytes']},indent=2))

if __name__=='__main__': main()
