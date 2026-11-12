# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_service.py
# Description : Contrats du service facultatif avec moteur simulé, sans GPU
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import base64
from http.server import HTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from eidolon_core.media_agents import MediaError
from eidolon_core.media_profiles import validate, workflow
from eidolon_core.media_service import MediaService, ComfyEngine, handler

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=')

class Engine:
    def __init__(self):
        self.ready = True; self.submissions = []; self.fail = False; self.history = {}; self.cancels = []
    def available(self): return {'ready':self.ready}
    def submit(self, graph):
        self.submissions.append(graph)
        if self.fail: raise TimeoutError('possible submission')
        return 'engine-id'
    def poll(self, prompt_id): return self.history
    def cancel(self, prompt_id): self.cancels.append(prompt_id)
    def collect(self, history, job): return PNG, 'test.png'

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)/'media'
        self.engine = Engine(); self.service = MediaService(self.root, self.engine)
    def tearDown(self): self.service.close(); self.tmp.cleanup()
    def submit(self, key='one', **kw): return self.service.submit(dict(prompt='a cabin', **kw), key)
    def test_idempotence(self):
        a = self.submit(); b = self.submit(); self.assertEqual(a['id'],b['id'])
        self.service.tick(); self.service.tick(); self.assertEqual(len(self.engine.submissions),1)
    def test_idempotence_conflict(self):
        self.submit()
        with self.assertRaisesRegex(MediaError,'IDEMPOTENCY_CONFLICT'): self.submit(seed=4)
    def test_gpu_busy_defers(self):
        j = self.submit(); self.engine.ready = False; self.service.tick()
        self.assertEqual(self.service.get(j['id'])['state'],'WAITING'); self.assertFalse(self.engine.submissions)
    def test_submit_timeout_never_retries(self):
        j = self.submit(); self.engine.fail = True; self.service.tick(); self.service.tick()
        self.assertEqual(self.service.get(j['id'])['state'],'REVIEW_REQUIRED'); self.assertEqual(len(self.engine.submissions),1)
    def test_unknown_job_blocks_next_admission(self):
        self.submit(); self.submit('two'); self.engine.fail = True
        self.service.tick(); self.engine.fail = False; self.service.tick()
        self.assertEqual(len(self.engine.submissions),1)
    def test_restart_retains_unknown_without_replay(self):
        j = self.submit(); self.service.tick(); self.service.close()
        self.service = MediaService(self.root,self.engine); self.service.tick()
        self.assertEqual(self.service.get(j['id'])['state'],'REVIEW_REQUIRED'); self.assertEqual(len(self.engine.submissions),1)
    def test_waiting_cancellation_has_no_engine_effect(self):
        j = self.submit(); self.service.cancel(j['id']); self.service.tick()
        self.assertEqual(self.service.get(j['id'])['state'],'CANCELLED'); self.assertFalse(self.engine.submissions)
    def test_running_cancel_is_not_an_ack_of_stop(self):
        j = self.submit(); self.service.tick(); self.service.cancel(j['id']); self.service.tick()
        self.assertEqual(self.service.get(j['id'])['state'],'CANCEL_REQUESTED')
        self.engine.history = {'engine-id':{'status':{'status_str':'error','messages':[['execution_interrupted',{}]]}}}
        self.service.tick(); self.assertEqual(self.service.get(j['id'])['state'],'CANCELLED')
    def test_incomplete_history_not_success(self):
        j = self.submit(); self.service.tick()
        self.engine.history = {'engine-id':{'status':{'status_str':'success','completed':False}}}
        self.service.tick(); self.assertEqual(self.service.get(j['id'])['state'],'RUNNING')
    def test_result_uses_existing_artifact_store(self):
        j = self.submit(); self.service.tick()
        self.engine.history = {'engine-id':{'status':{'status_str':'success','completed':True}}}
        self.service.tick(); j = self.service.get(j['id'])
        self.assertEqual(j['state'],'SUCCEEDED'); self.assertEqual(self.service.artifacts.read(j['result']['reference'])[0],PNG)
    def test_metadata_not_in_status(self):
        j = self.submit(); self.assertNotIn('request',self.service.public(j))
    def test_dedicated_process_lock(self):
        with self.assertRaises(BlockingIOError): MediaService(self.root,self.engine)
    def test_disabled_video_refused(self):
        with self.assertRaisesRegex(MediaError,'MODEL_NOT_ENABLED'):
            self.submit(profile='wan21-text',height=320)
    def test_queue_limit(self):
        for i in range(128): self.submit(str(i))
        with self.assertRaisesRegex(MediaError,'QUEUE_CAPACITY'): self.submit('overflow')
    def test_symlink_root_refused(self):
        link = Path(self.tmp.name)/'link'; link.symlink_to(self.root)
        with self.assertRaisesRegex(MediaError,'PRIVATE_ROOT_REQUIRED'): MediaService(link,self.engine)
    def test_unconfigured_external_endpoint_refused(self):
        for url in ['https://example.com:443','http://192.168.1.2:80','http://127.0.0.1:80@evil:80']:
            with self.assertRaises(MediaError): ComfyEngine(url,'/tmp','gpu',1)

class ProfileTests(unittest.TestCase):
    def test_budget_and_numeric_limits(self):
        for request in [{'width':513},{'seed':True},{'steps':100},{'denoise':float('nan')},
                        {'profile':'wan21-text','height':320,'frames':6},
                        {'profile':'wan21-text','width':768,'height':320}, {'nodes':{}}]:
            with self.subTest(request=request), self.assertRaises(MediaError): validate(request)
    def test_untrusted_source_path_refused(self):
        with self.assertRaises(MediaError): workflow({'profile':'sd15-edit','source':{}},prefix='ok',source_name='../secret.png')
    def test_video_graph_uses_native_nodes(self):
        g = workflow({'profile':'wan21-text','height':320},prefix='ok')
        self.assertEqual(g['1']['inputs']['weight_dtype'],'default')
        self.assertEqual(g['10']['class_type'],'SaveWEBM')
        self.assertEqual(g['6']['inputs']['length'],9)

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.service=MediaService(Path(self.tmp.name)/'state',Engine())
        self.server=HTTPServer(('127.0.0.1',0),handler(self.service,'x'*40))
        self.thread=threading.Thread(target=self.server.serve_forever); self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close(); self.service.close(); self.tmp.cleanup()
    def call(self, path, value=None, **headers):
        headers={'Authorization':'Bearer '+'x'*40,'Content-Type':'application/json',**headers}
        req=urllib.request.Request(self.url+path,data=None if value is None else json.dumps(value).encode(),headers=headers)
        return urllib.request.urlopen(req,timeout=3)
    def test_authentication(self):
        with self.assertRaises(urllib.error.HTTPError) as e: self.call('/health',Authorization='bad')
        self.assertEqual(e.exception.code,401)
    def test_browser_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e: self.call('/health',Origin='https://evil.example')
        self.assertEqual(e.exception.code,401)
    def test_http_job_lifecycle(self):
        with self.call('/v1/jobs',{'prompt':'test'},**{'Idempotency-Key':'api1'}) as r: j=json.load(r)
        with self.call('/v1/jobs/'+j['id']+'/cancel',{}) as r: self.assertEqual(json.load(r)['state'],'CANCELLED')
    def test_client_path_not_accepted(self):
        with self.assertRaises(urllib.error.HTTPError): self.call('/v1/jobs',{'output':'/etc/passwd'},**{'Idempotency-Key':'api1'})

if __name__ == '__main__': unittest.main()
