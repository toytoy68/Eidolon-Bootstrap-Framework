# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g088_slow_http_shutdown.py
# Description : Arrêt du serveur avec un appel de dialogue en cours, HTTP moteur simulé à réponse lente
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.dialogue import ChatDialogueModel
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatModel
from eidolon_core.http_api import ReadServer
from eidolon_core.store import Store

entered, release, closed = threading.Event(), threading.Event(), threading.Event()
class SlowEngine(BaseHTTPRequestHandler):
    def log_message(self, *_):pass
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        body=json.dumps({'object':'chat.completion','model':'fixture',
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(
                {'version':1,'kind':'answer','text':'Réponse synthétique.','proposal':None})}}]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        entered.set()
        try:
            index=0
            while index<len(body) and not release.is_set():
                self.wfile.write(body[index:index+1]);self.wfile.flush();index+=1
                release.wait(0.05)
            self.wfile.write(body[index:]);self.wfile.flush()
        except OSError:pass
engine=ThreadingHTTPServer(('127.0.0.1',0),SlowEngine)
engine_thread=threading.Thread(target=engine.serve_forever,kwargs={'poll_interval':0.01});engine_thread.start()
def model():
    return ChatDialogueModel(OpenAIChatModel(OpenAIChatConfig(
        endpoint='http://127.0.0.1:'+str(engine.server_port),model='fixture',
        options={'max_tokens':64},timeout_seconds=0.3)),demo_catalog())

with tempfile.TemporaryDirectory() as folder:
    state = Path(folder)/'state';store=Store(state)
    conversations=ConversationStore(store,create=True)
    cid=conversations.open(client_id='fixture',client_key='open')['conversation_id']
    key=ClientCredentials(store,create=True).pair(client_id='fixture',actor='synthetic operator')['token']
    server=ReadServer(state,secrets.token_urlsafe(32),port=0,conversations=model)
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
        assert closed.wait(0.8), 'close still waits on the model'
        assert not closer.is_alive()
        client.join(2)
        assert not client.is_alive(), 'inbound connection was not closed'
        release.set()
        assert closed.wait(3), 'close did not finish after model release'
        closer.join(2)
        assert conversations.page(cid)['items'][0]['reply'] is None
        print(json.dumps({'status':'CORRECTION_VERIFIED','source':'C121 integrated',
            'id':'G088-R2','real_http_adapter':True,'synthetic_slow_engine':True,'socket_timeout_seconds':0.3,'inbound_client_closed':True,
            'server_close_waited_for_model':False,'close_bound_checked_seconds':0.8,
            'close_finished_before_model_release':True,'reply_persisted_after_close_started':False,
            'infinite_wait_measured':False,'real_model_used':False},indent=2))
    finally:
        release.set()
        server.shutdown()
        if closer is not None:closer.join(5)
        else:server.server_close()
        serve.join(3);client.join(3)
        engine.shutdown();engine.server_close();engine_thread.join(3)
