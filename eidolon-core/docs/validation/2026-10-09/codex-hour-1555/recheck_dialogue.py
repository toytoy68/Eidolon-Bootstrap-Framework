# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recheck_dialogue.py
# Description : Contre-vérification des corrections G090-R1 et G088-R2
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

with tempfile.TemporaryDirectory() as folder:
    runtime = synthetic_runtime(Store(Path(folder) / 'state'))
    store = ConversationStore(runtime.store, create=True)
    cid = store.open(client_id='fixture', client_key='open')['conversation_id']
    entered, release = threading.Event(), threading.Event()
    class Model:
        calls = 0
        def reply(self, *args):
            self.calls += 1
            entered.set(); assert release.wait(5)
            return SimulatedDialogueModel(runtime.catalog).reply(*args)
    model = Model(); dialogue = Dialogue(store, model, runtime.catalog)
    def send():
        return dialogue.respond(cid, client_id='fixture', client_turn_key='one', text='Bonjour')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send)
        try:
            assert entered.wait(3)
            pending = pool.submit(send).result(timeout=3)
            assert pending['pending'] is True
        finally:
            release.set()
        recorded = first.result(timeout=3)
    replay = send()
    assert model.calls == 1
    assert replay['reply'] == recorded['reply']
    assert len(store.page(cid)['items']) == 1
    print(json.dumps({'status': 'PASS', 'case': 'G090-R1', 'model_calls': model.calls,
                      'concurrent_pending': True, 'stored_turns': 1, 'replayed_identically': True,
                      'real_model': False}))
