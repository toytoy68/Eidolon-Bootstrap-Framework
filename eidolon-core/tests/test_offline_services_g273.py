# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_offline_services_g273.py
# Description : Reprise, isolation, conservation, calibration et admission G273
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from pathlib import Path
import threading
import time
import pytest
from eidolon_core.library_sync import Library
from eidolon_core.retention_preview import preview
from eidolon_core.identity_evaluation import evaluate
from eidolon_core.gpu_queue import Queue, ScheduledModel
from eidolon_core.offline_state import database
from eidolon_core.contracts import ContractError
from tests.test_beta_runtime_g270 import config


def library(tmp_path):
    c=config(tmp_path)
    return Library(c,c['state_directory']),Path(c['profiles']['user0']['file_roots']['nas'])


def test_sync_versions_restart_missing_isolation(tmp_path):
    lib,root=library(tmp_path)
    assert lib.scan('pc0','nas')['new_versions']==1
    assert lib.page('pc1','nas')['entries']==[]
    assert Library(lib.config,lib.directory).scan('pc0','nas')['new_versions']==0
    (root/'note.txt').write_text('new version')
    assert lib.scan('pc0','nas')['new_versions']==1
    (root/'note.txt').unlink();assert lib.scan('pc0','nas')['files']==0
    assert lib.page('pc0','nas')['entries'][0]['present']==0
    with database(lib.directory,'library.sqlite3') as db:assert db.execute('SELECT count(*) FROM versions').fetchone()[0]==2


def test_duplicate_cache_binds_format_and_profile(tmp_path,monkeypatch):
    lib,root=library(tmp_path);lib.scan('pc0','nas')
    (root/'copy.txt').write_bytes((root/'note.txt').read_bytes())
    def refused(*_):raise AssertionError('extraction invoked')
    monkeypatch.setattr('eidolon_core.library_sync.documents.extract',refused)
    assert lib.scan('pc0','nas')['reused_excerpts']==2
    with pytest.raises(AssertionError):lib.scan('pc1','nas')
    (root/'fake.docx').write_bytes((root/'note.txt').read_bytes())
    with pytest.raises(AssertionError):lib.scan('pc0','nas')


def test_failed_scan_preserves_previous_generation(tmp_path):
    lib,root=library(tmp_path);lib.scan('pc0','nas');before=lib.page('pc0','nas')
    (root/'evil.txt').symlink_to('/etc/passwd');(root/'note.txt').unlink()
    with pytest.raises(ValueError,match='LINK'):lib.scan('pc0','nas')
    assert lib.page('pc0','nas')==before


def test_interruption_budget_preserve_generation(tmp_path,monkeypatch):
    lib,root=library(tmp_path);lib.scan('pc0','nas');before=lib.page('pc0','nas')
    stop=threading.Event();stop.set()
    with pytest.raises(ValueError,match='INTERRUPTED'):lib.scan('pc0','nas',stopped=stop)
    monkeypatch.setattr('eidolon_core.library_sync.MAX_BYTES',1)
    with pytest.raises(ValueError,match='BUDGET'):lib.scan('pc0','nas')
    assert lib.page('pc0','nas')==before


def test_changed_during_extraction_refused(tmp_path,monkeypatch):
    lib,root=library(tmp_path);lib.scan('pc0','nas');before=lib.page('pc0','nas')
    (root/'note.txt').write_text('changed')
    from eidolon_core import documents
    original=documents.extract
    def change(raw,name):
        result=original(raw,name);(root/name).write_text('changed again');return result
    monkeypatch.setattr(documents,'extract',change)
    with pytest.raises(ValueError,match='CHANGED'):lib.scan('pc0','nas')
    assert lib.page('pc0','nas')==before


def test_scope_binding_private_permissions(tmp_path):
    lib,root=library(tmp_path);lib.scan('pc0','nas')
    with pytest.raises(ValueError,match='SCOPE'):lib.scan('stranger','nas')
    with pytest.raises(ValueError,match='SCOPE'):lib.scan('pc0','../../elsewhere')
    c=copy.deepcopy(lib.config);c['clients']['pc0']='user1'
    with pytest.raises(ValueError,match='BINDING'):Library(c,lib.directory).scan('pc0','nas')
    Path(lib.directory).chmod(0o755)
    with pytest.raises(ValueError,match='PRIVATE'):lib.page('pc0','nas')


def test_pagination(tmp_path):
    lib,root=library(tmp_path)
    for i in range(52):(root/f'{i:02}.txt').write_text('same')
    lib.scan('pc0','nas');page=lib.page('pc0','nas')
    assert len(page['entries'])==50 and page['next_after']
    rest=lib.page('pc0','nas',page['next_after']);assert len(rest['entries'])==3 and rest['next_after'] is None
    assert not set(r['path'] for r in rest['entries']) & set(r['path'] for r in page['entries'])


def test_retention_old_versions_only_no_mutation(tmp_path):
    lib,root=library(tmp_path);lib.scan('pc0','nas')
    with database(lib.directory,'library.sqlite3',write=True) as db:db.execute("UPDATE versions SET created_at='2020-01-01T00:00:00+00:00'")
    (root/'note.txt').write_text('current');lib.scan('pc0','nas')
    path=Path(lib.directory)/'library.sqlite3';before=path.read_bytes();report=preview(lib.directory,days=30)
    assert len(report['candidates'])==1 and report['protected_rows']==1
    assert report['candidate_logical_bytes']>0 and report['disk_reclaim_bytes'] is None
    assert not report['deleted'] and path.read_bytes()==before
    with pytest.raises(ValueError):preview(lib.directory,days=0)


def dataset():
    rows=[]
    for split in ('calibration','validation'):
        for i,(g,s) in enumerate([(True,.8),(True,.7),(False,.2),(False,.4)]):
            rows.append(dict(id=split+str(i),split=split,sessions=[split+'a'+str(i),split+'b'+str(i)],genuine=g,score=s))
    return {'schema':'eidolon-identity-evaluation/1','engine':{'name':'synthetic','modality':'face','model_sha256':'a'*64,'preprocessing':'test'},'synthetic':True,'trials':rows}


def test_calibration_holdout_uncertainty_no_activation():
    data=dataset();report=evaluate(data,max_far=0)
    assert report['state']=='SYNTHETIC_ONLY' and not report['activated']
    assert report['validation']['far']==report['validation']['frr']==0
    assert report['validation']['far_wilson95'][1]>.5
    changed=copy.deepcopy(data)
    for row in changed['trials']:
        if row['split']=='validation':row['score']=1
    second=evaluate(changed,max_far=0)
    assert second['candidate_threshold']==report['candidate_threshold'] and not second['validation_meets_empirical_target']


@pytest.mark.parametrize('mode',['leak','nan','bool','duplicate'])
def test_calibration_invalid_data(mode):
    d=dataset()
    if mode=='leak':d['trials'][4]['sessions'][0]=d['trials'][0]['sessions'][0]
    elif mode=='duplicate':d['trials'][1]['id']=d['trials'][0]['id']
    else:d['trials'][0]['score']=float('nan') if mode=='nan' else True
    with pytest.raises(ValueError):evaluate(d,max_far=0)


def gpu(tmp_path,clock=time.time):
    path=tmp_path/'gpu';path.mkdir(mode=0o700)
    c={'schema':'eidolon-gpu-queue/1','directory':str(path),'capacity_mib':100,'resident_mib':20,'dialogue_mib':40,'media_mib':80}
    return Queue(c,clock=clock)


def test_priority_capacity_uncertainty_restart(tmp_path):
    q=gpu(tmp_path);q.enqueue('media','media');q.enqueue('chat','dialogue')
    assert q.acquire('media')['state']=='WAITING'
    active=q.acquire('chat');assert active['state']=='ACTIVE'
    q.finish('chat',active['lease'],uncertain=True)
    assert Queue(q.config).acquire('media')['state']=='WAITING'
    with pytest.raises(ValueError,match='REVIEW'):q.finish('chat',active['lease'])
    with pytest.raises(ValueError,match='LEASE'):q.finish('chat','wrong',reviewed=True)
    q.finish('chat',active['lease'],reviewed=True);assert q.acquire('media')['state']=='ACTIVE'


def test_aging_no_starvation_no_config_rebind(tmp_path):
    now=[100.];q=gpu(tmp_path,lambda:now[0]);q.enqueue('old','media');now[0]+=3000;q.enqueue('new','dialogue')
    assert q.acquire('new')['state']=='WAITING' and q.acquire('old')['state']=='ACTIVE'
    with pytest.raises(ValueError,match='CHANGED'):Queue(dict(q.config,capacity_mib=200))


def test_concurrent_capacity(tmp_path):
    q=gpu(tmp_path);q.enqueue('a','media');q.enqueue('b','media');results=[]
    threads=[threading.Thread(target=lambda k=k:results.append(q.acquire(k)['state'])) for k in ('a','b')]
    for t in threads:t.start()
    for t in threads:t.join()
    assert sorted(results)==['ACTIVE','WAITING']


def test_model_success_release_failure_holds(tmp_path):
    q=gpu(tmp_path)
    class Model:
        model_id='synth'
        def reply(self,*a,**k):return 'done'
    assert ScheduledModel(Model(),q).reply('prompt')=='done' and q.inspect()['jobs']==[]
    class Failed(Model):
        def reply(self,*a,**k):raise RuntimeError('lost')
    with pytest.raises(RuntimeError):ScheduledModel(Failed(),q).reply('prompt')
    assert q.inspect()['jobs'][0]['state']=='UNKNOWN'


def test_abandoned_dialogue_cannot_start_later(tmp_path):
    from eidolon_core.dialogue import Dialogue
    q=gpu(tmp_path);q.enqueue('blocking','media');lease=q.acquire('blocking')['lease'];called=threading.Event()
    class Model:
        def reply(self,*a,**k):called.set();return ('reply',{})
    dialog=Dialogue.__new__(Dialogue);dialog._closing=threading.Event();dialog.gpu_queue=q
    with pytest.raises(ContractError):dialog._bounded_reply(Model(),.03,'text',[],None)
    time.sleep(.1);q.finish('blocking',lease);time.sleep(.1)
    assert not called.is_set() and not any(r['kind']=='dialogue' for r in q.inspect()['jobs'])


def test_protected_histories_inventory_no_content_read(tmp_path):
    lib,_=library(tmp_path);lib.scan('pc0','nas')
    history=tmp_path/'histories';history.mkdir();(history/'private.txt').write_bytes(b'private')
    r=preview(lib.directory,days=30,protected_roots={'histories':str(history)})
    assert r['protected_roots']['histories']['logical_bytes']==7
    assert r['protected_roots']['histories']['protected'] and not r['deleted']
    (history/'link').symlink_to('/etc')
    with pytest.raises(ValueError):preview(lib.directory,days=30,protected_roots={'histories':str(history)})


def test_real_api_session_revoke_rotation_and_library_ownership(tmp_path):
    import json
    from eidolon_core.beta_runtime import BetaRuntime
    from eidolon_core.conversation_api import ConversationAPI
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.client_credentials import ClientCredentials
    from eidolon_core.dialogue import SimulatedDialogueModel
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.store import Store
    cfg=config(tmp_path);services=BetaRuntime(cfg)
    runtime=synthetic_runtime(Store(tmp_path/'core'));ConversationStore(runtime.store,create=True)
    credentials=ClientCredentials(runtime.store,create=True)
    keys={c:credentials.pair(client_id=c,actor='operator fixture')['token'] for c in ('pc0','pc1')}
    api=ConversationAPI(runtime,dialogue_model=SimulatedDialogueModel(runtime.catalog),services=services,read_token='r'*32)
    def call(route,body,key):
        return api.handle('POST','/v1/conversations/'+route,{'Authorization':['Bearer '+key],'Content-Type':['application/json']},json.dumps(body).encode())
    try:
        Library(cfg,cfg['state_directory']).scan('pc0','nas')
        assert call('library_page',{'root':'nas'},keys['pc0'])[1]['entries']
        assert call('library_page',{'root':'nas'},keys['pc1'])[1]['entries']==[]
        assert call('session_status',{},keys['pc0'])[1]['profile_id']=='user0'
        assert call('session_revoke',{'client_id':'pc1','confirmation':'REVOKE_THIS_KEY'},keys['pc0'])[0]==409
        assert call('session_revoke',{'client_id':'pc0','confirmation':'REVOKE_THIS_KEY'},keys['pc0'])[0]==200
        assert call('session_status',{},keys['pc0'])[0]==401
        assert call('session_status',{},keys['pc1'])[0]==200
        new=credentials.rotate('pc0')['token']
        assert call('session_status',{},new)[1]['profile_id']=='user0'
        assert credentials.authenticate(keys['pc0']) is None
        assert all('token' not in row and 'token_sha256' not in row for row in credentials.inventory())
        assert call('session_status',{},'r'*32)[0]==403
    finally:api.close()


def test_concurrent_scans_refused(tmp_path):
    from eidolon_core.offline_state import lease
    lib,_=library(tmp_path)
    with lease(lib.directory,'library-scan.lock'):
        with pytest.raises(ValueError,match='BUSY'):lib.scan('pc0','nas')


def test_real_measurement_pipeline_synthetic_encoder_no_vectors_in_report(tmp_path):
    import json
    from tests.test_identity_runtime_g272 import settings, synthetic
    from eidolon_core.identity_measure import measure
    rows=[]
    for split in ('calibration','validation'):
        for i,subject in enumerate(('one','one','two')):
            name=split+str(i);(tmp_path/name).write_bytes(b'fake image')
            rows.append(dict(id=name,subject=subject,session=name,split=split,path=name))
    manifest=dict(schema='eidolon-identity-captures/1',modality='face',synthetic=True,consented=True,samples=rows)
    data=measure(settings(),manifest,str(tmp_path),observer=synthetic)
    assert len(data['trials'])==6 and 'embedding' not in json.dumps(data)
    report=evaluate(data,max_far=0)
    assert not report['activated']
    manifest['consented']=False
    with pytest.raises(ValueError,match='CONSENT'):measure(settings(),manifest,str(tmp_path),observer=synthetic)
