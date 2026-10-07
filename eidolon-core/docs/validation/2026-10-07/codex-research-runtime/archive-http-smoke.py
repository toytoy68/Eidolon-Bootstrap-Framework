# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : archive-http-smoke.py
# Description : Recette archive, projection HTTP privée et consommateur JavaScript
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core with one already verified source archive argument."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

CHILD = r"""
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
from eidolon_core.http_api import ReadServer
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.store import Store

captures=[]
for scenario, expected in [('readable','ACHIEVED'),('partial','PARTIAL'),('empty','NOT_ACHIEVED')]:
    with tempfile.TemporaryDirectory() as state:
        store=Store(state)
        runtime=ResearchRuntime(store,scenario=scenario)
        mission=runtime.run(runtime.create_research('ARCHIVE_PRIVATE_QUERY jean@example.invalid',required_pages=2)['id'])
        assert mission['outcome']['status']==expected
        files=list(Path(state).rglob('*.sqlite3'))
        before={str(p):p.read_bytes() for p in files}
        token='synthetic_archive_token_'+'x'*32
        server=ReadServer(store.directory,token,port=0)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01})
        thread.start()
        def request(path,data=None):
            c=HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            try:
                c.request('POST' if data is not None else 'GET',path,
                    body=json.dumps(data) if data is not None else None,
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                response=c.getresponse();raw=response.read()
                assert b'ARCHIVE_PRIVATE_QUERY' not in raw and b'jean@example.invalid' not in raw
                assert b'Premi' not in raw and b'query_cleanup' not in raw
                return response.status,json.loads(raw)
            finally:c.close()
        try:
            status,page=request('/v1/missions',{})
            assert status==200 and page['items'][0]['mission']['objective_kind']=='research_retrieval.synthetic'
            status,snapshot=request('/v1/missions/'+mission['id'])
            assert status==200 and snapshot['snapshot']['mission']['outcome_status']==expected
            assert snapshot['authorizes_execution'] is False
            status,delta=request('/v1/missions/'+mission['id']+'/poll',{'cursor':snapshot['cursor']})
            assert status==200 and delta['events']==[]
            for path in ('/v1/query-history','/v1/research','/v1/missions/'+mission['id']+'/research'):
                assert request(path)[0]==404
            captures.append(snapshot)
        finally:
            server.shutdown();thread.join(5);server.server_close()
        assert all(Path(p).read_bytes()==b for p,b in before.items())
print(json.dumps(captures))
"""
NODE = r"""
const fs=require('node:fs'),vm=require('node:vm');
const context={document:{readyState:'loading',addEventListener(){}}};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const envelopes=JSON.parse(fs.readFileSync(0,'utf8'));
for(const e of envelopes){const error=context.EidolonSync.validateEnvelope(e);if(error)throw Error(error);}
console.log(JSON.stringify({envelopes_accepted:envelopes.length,browser_tested:false}));
"""


def main():
    archive=Path(sys.argv[1]).resolve()
    verification=subprocess.run([sys.executable,'tools/build_beta_bundle.py','--verify',archive],check=True,capture_output=True,text=True)
    verified=json.loads(verification.stdout)
    with tempfile.TemporaryDirectory(prefix='eidolon-archive-') as directory:
        with tarfile.open(archive,'r:gz') as tar:tar.extractall(directory,filter='data')
        root=next(Path(directory).iterdir())/'eidolon-core'
        assert (root/'docs/QUERY-HISTORY.md').is_file() and (root/'docs/RESEARCH-MISSIONS.md').is_file()
        env=dict(os.environ,PYTHONPATH=str(root/'src'))
        captures=subprocess.run([sys.executable,'-c',CHILD],cwd=root,env=env,check=True,capture_output=True,text=True,timeout=30).stdout
        client=subprocess.run(['node','-e',NODE,str(root/'desktop/connected/app.js')],input=captures,check=True,capture_output=True,text=True,timeout=10)
        result={'status':'PASS','commit':verified['commit'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'files_verified':verified['files'],'research_scenarios':['readable','partial','empty'],
                'private_query_absent_from_http':True,'history_routes_absent':True,
                'consultation_did_not_mutate_state':True,'client':json.loads(client.stdout)}
    result['temporary_files_removed']=not Path(directory).exists()
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
