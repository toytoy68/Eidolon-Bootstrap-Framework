# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g088_shutdown.py
# Description : Arrêt du serveur avec un appel de dialogue en cours, modèle synthétique contrôlé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.http_api import ReadServer
from eidolon_core.store import Store

entered, release, closed = threading.Event(), threading.Event(), threading.Event()
class ControlledModel:
    def reply(self, *args):
        entered.set()
        if not release.wait(10):
            raise RuntimeError('probe cleanup deadline')
        return SimulatedDialogueModel(demo_catalog()).reply(*args)

with tempfile.TemporaryDirectory() as folder:
    state = Path(folder)/'state';store=Store(state)
    conversations=ConversationStore(store,create=True)
    cid=conversations.open(client_id='fixture',client_key='open')['conversation_id']
    key=ClientCredentials(store,create=True).pair(client_id='fixture',actor='synthetic operator')['token']
    server=ReadServer(state,secrets.token_urlsafe(32),port=0,conversations=ControlledModel)
    serve=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01});serve.start()
    def request():
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        try:
            connection.request('POST','/v1/conversations/turn',body=json.dumps({
                'conversation_id':cid,'client_turn_key':'pending','text':'Bonjour'}),
                headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            response=connection.getresponse();response.read()
        except (OSError,http.client.HTTPException):
            pass
        finally:connection.close()
    client=threading.Thread(target=request);client.start()
    closer=None
    try:
        assert entered.wait(3), 'model not entered'
        server.shutdown();serve.join(2)
        def close():
            server.server_close();closed.set()
        closer=threading.Thread(target=close);closer.start()
        assert not closed.wait(0.5), 'close already returned'
        assert closer.is_alive()
        client.join(2)
        assert not client.is_alive(), 'inbound connection was not closed'
        release.set()
        assert closed.wait(3), 'close did not finish after model release'
        closer.join(2)
        assert conversations.page(cid)['items'][0]['reply'] is not None
        print(json.dumps({'status':'OBSERVATION_REPRODUCED','source':'C110 / code f021878',
            'id':'G088-R2','synthetic_controlled_model':True,'inbound_client_closed':True,
            'server_close_waited_for_model':True,'wait_observed_seconds':0.5,
            'close_finished_only_after_model_release':True,'reply_persisted_after_close_started':True,
            'infinite_wait_measured':False,'real_model_used':False},indent=2))
    finally:
        release.set()
        server.shutdown()
        if closer is not None:closer.join(5)
        else:server.server_close()
        serve.join(3);client.join(3)
