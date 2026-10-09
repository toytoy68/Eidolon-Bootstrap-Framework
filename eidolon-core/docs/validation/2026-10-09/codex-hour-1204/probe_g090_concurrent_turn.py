# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g090_concurrent_turn.py
# Description : Même tour concurrent : compteur d'appels modèle, aucune mission
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import Dialogue, SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store

with tempfile.TemporaryDirectory() as tmp:
    runtime=synthetic_runtime(Store(Path(tmp)/'state'))
    conversations=ConversationStore(runtime.store,create=True)
    cid=conversations.open(client_id='fixture',client_key='same')['conversation_id']
    class Model:
        calls=0
        lock=threading.Lock()
        barrier=threading.Barrier(2)
        def reply(self,*args):
            with self.lock:self.calls+=1
            self.barrier.wait(timeout=5)
            return SimulatedDialogueModel(runtime.catalog).reply(*args)
    model=Model(); dialogue=Dialogue(conversations,model,runtime.catalog)
    def send():
        return dialogue.respond(cid,client_id='fixture',client_turn_key='identical',text='Bonjour')
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures=[workers.submit(send) for _ in range(2)]
        results=[f.result(timeout=10) for f in futures]
    page=conversations.page(cid)
    assert model.calls==2
    assert len(page['items'])==1
    assert results[0]['reply']==results[1]['reply']
    print(json.dumps({'status':'FINDING_REPRODUCED','source':'C110/8f20041',
        'id':'G090-R1','same_client_turn_key':True,'model_calls':model.calls,
        'stored_turns':len(page['items']),'same_recorded_reply':True,
        'duplicate_mission_claimed':False,'synthetic_model_only':True},indent=2))
