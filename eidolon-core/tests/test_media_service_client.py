# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_service_client.py
# Description : Contrat HTTP Core vers le service local, moteur simulé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from http.server import HTTPServer
import tempfile
from pathlib import Path
import threading
import unittest
from eidolon_core.media_agents import MediaError
from eidolon_core.media_service import MediaService,handler
from eidolon_core.media_service_client import LocalGenerationClient

class ClientTests(unittest.TestCase):
    def test_real_http_submit_status_cancel_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=MediaService(Path(tmp)/'state',None)
            server=HTTPServer(('127.0.0.1',0),handler(service,'a'*40))
            thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                client=LocalGenerationClient('http://127.0.0.1:'+str(server.server_port),'a'*40)
                job=client.submit({'prompt':'test'},idempotency_key='one')
                self.assertEqual(client.status(job['id'])['state'],'WAITING')
                self.assertEqual(client.cancel(job['id'])['state'],'CANCELLED')
                self.assertIn('sd15-text',client.models()['profiles'])
            finally:server.shutdown();thread.join();server.server_close();service.close()
    def test_nonlocal_endpoint_refused(self):
        with self.assertRaises(MediaError):LocalGenerationClient('https://example.com:443','a'*40)
    def test_job_path_injection_refused(self):
        client=LocalGenerationClient('http://127.0.0.1:8190','a'*40)
        with self.assertRaises(MediaError):client.status('../secret')

if __name__=='__main__':unittest.main()
