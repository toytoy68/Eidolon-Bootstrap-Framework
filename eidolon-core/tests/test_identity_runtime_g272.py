# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_identity_runtime_g272.py
# Description : Enrôlement privé, concurrence, reprise et absence de droits
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import base64
from datetime import datetime, timedelta, timezone
import json
import threading
import pytest
from eidolon_core.identity_runtime import IdentityRuntime, IdentityError, engine, validate
from eidolon_core.identity_proposal import Observation
from eidolon_core.beta_runtime import BetaRuntime
from tests.test_beta_runtime_g270 import config

NOW = datetime(2026,10,15,22,tzinfo=timezone.utc)


def settings(samples=2):
    return {'schema':'eidolon-identity-runtime/1','modalities':{'face':{
        'samples':samples,'model':{'path':'/operator/model.onnx','sha256':'a'*64},
        'detector':{'path':'/operator/detector.onnx','sha256':'b'*64},'calibration':None}}}


def synthetic(cfg, modality, raw):
    return Observation(modality,NOW,engine(cfg,modality),faces=1,embedding=(1.0,0.1))


def encoded(n): return base64.b64encode(bytes([n])*32).decode()


def setup(tmp_path, observer=synthetic, samples=2, clock=lambda:NOW):
    rt = BetaRuntime(config(tmp_path),clock=clock)
    rt.identity = IdentityRuntime(settings(samples),rt._db,rt.profile,clock=clock,observer=observer)
    return rt, rt.identity


def complete(service, key='begin'):
    a=service.begin('pc0','face',key,True,True)
    for n in range(a['required']): a=service.sample('pc0',a['session_id'],f's{n}',encoded(n+1))
    return a


def test_consent_profile_isolation_confirm_and_delete(tmp_path):
    rt, service=setup(tmp_path)
    try:
        with pytest.raises(IdentityError,match='CONSENT'): service.begin('pc0','face','no',True,False)
        a=service.begin('pc0','face','begin',True,True)
        assert service.begin('pc0','face','begin',True,True)==a
        with pytest.raises(IdentityError,match='UNKNOWN'): service.sample('pc1',a['session_id'],'x',encoded(1))
        with pytest.raises(IdentityError,match='APPROVAL'): service.confirm('pc0',a['session_id'],'a'*64)
        a=service.sample('pc0',a['session_id'],'s0',encoded(1))
        assert service.sample('pc0',a['session_id'],'s0',encoded(1))==a
        with pytest.raises(IdentityError,match='KEY_REUSED'): service.sample('pc0',a['session_id'],'s0',encoded(2))
        a=service.sample('pc0',a['session_id'],'s1',encoded(2))
        saved=service.confirm('pc0',a['session_id'],a['approval_sha256'])
        assert saved['state']=='ENROLLED' and saved['grants']==[] and not saved['authorizes_execution']
        assert service.confirm('pc0',a['session_id'],a['approval_sha256'])==saved
        status=service.status('pc0'); assert status['modalities'][0]['enrolled']
        assert not service.status('pc1')['modalities'][0]['enrolled']
        assert 'vector' not in json.dumps(status) and 'templates' not in json.dumps(status)
        proposal=service.probe('pc0','face',encoded(3))
        assert proposal['state']=='uncalibrated' and proposal['candidates']==[] and not proposal['authorizes_execution']
        with pytest.raises(IdentityError,match='DELETE_FIRST'): service.begin('pc0','face','new',True,True)
        approved=status['modalities'][0]['delete_sha256']
        with pytest.raises(IdentityError,match='APPROVAL'): service.delete('pc0','face','0'*64)
        deleted=service.delete('pc0','face',approved)
        assert service.delete('pc0','face',approved)==deleted and not deleted['backups_erased']
        assert not service.status('pc0')['modalities'][0]['enrolled']
        assert service.begin('pc0','face','new',True,True)['state']=='COLLECTING'
    finally: rt.close()


def test_restart_preserves_confirmed_and_expires_incomplete(tmp_path):
    rt, service=setup(tmp_path)
    try:
        a=complete(service);service.confirm('pc0',a['session_id'],a['approval_sha256'])
        b=service.begin('pc1','face','second',True,True)
        service.sample('pc1',b['session_id'],'one',encoded(4))
        restarted=IdentityRuntime(settings(),rt._db,rt.profile,clock=lambda:NOW,observer=synthetic)
        assert restarted.status('pc0')['modalities'][0]['enrolled']
        old=restarted.status('pc1')['sessions'][0]
        assert old['state']=='EXPIRED' and old['samples']==0
    finally: rt.close()


def test_expiry_and_clock_rollback_clear_pending_samples(tmp_path):
    clock=[NOW];rt,service=setup(tmp_path,clock=lambda:clock[0])
    try:
        a=service.begin('pc0','face','one',True,True)
        service.sample('pc0',a['session_id'],'one',encoded(1))
        clock[0]=NOW+timedelta(minutes=11)
        assert service.status('pc0')['sessions'][0]['state']=='EXPIRED'
        b=service.begin('pc0','face','two',True,True)
        clock[0]=NOW
        assert service.status('pc0')['sessions'][0]['state']=='EXPIRED'
        with rt._db() as db: assert all(r[0]=='[]' for r in db.execute('SELECT samples FROM identity_sessions'))
    finally: rt.close()


def test_cancel_during_inference_cannot_resurrect_or_keep_capture(tmp_path):
    started=threading.Event();release=threading.Event();captures=[];failures=[]
    def slow(cfg,modality,raw):
        captures.append(raw);started.set();assert release.wait(5)
        return synthetic(cfg,modality,raw)
    rt,service=setup(tmp_path,observer=slow)
    try:
        a=service.begin('pc0','face','one',True,True)
        def run():
            try: service.sample('pc0',a['session_id'],'one',encoded(1))
            except IdentityError as exc: failures.append(str(exc))
        thread=threading.Thread(target=run);thread.start();assert started.wait(2)
        service.cancel('pc0',a['session_id']);release.set();thread.join(5)
        assert not thread.is_alive() and failures==['IDENTITY_SESSION_CLOSED']
        assert set(captures[0])=={0}
        assert service.status('pc0')['sessions'][0]['samples']==0
    finally: release.set();rt.close()


def test_changed_engine_and_stale_delete_refused(tmp_path):
    rt,service=setup(tmp_path)
    try:
        a=complete(service);service.confirm('pc0',a['session_id'],a['approval_sha256'])
        old=service.status('pc0')['modalities'][0]['delete_sha256']
        changed=settings();changed['modalities']['face']['detector']['sha256']='c'*64
        other=IdentityRuntime(changed,rt._db,rt.profile,clock=lambda:NOW,observer=synthetic)
        assert not other.status('pc0')['modalities'][0]['engine_matches']
        with pytest.raises(IdentityError,match='ENGINE_CHANGED'): other.probe('pc0','face',encoded(3))
        service.delete('pc0','face',old)
        b=complete(service,'reenrol');service.confirm('pc0',b['session_id'],b['approval_sha256'])
        with pytest.raises(IdentityError,match='APPROVAL'):service.delete('pc0','face',old)
    finally: rt.close()


@pytest.mark.parametrize('mutation',[lambda c:c['modalities']['face'].update(samples=True),
    lambda c:c['modalities']['face']['model'].update(path='../model'),
    lambda c:c['modalities']['face'].update(calibration={}),
    lambda c:c['modalities'].update(unknown={})])
def test_strict_operator_configuration(mutation):
    cfg=settings();mutation(cfg)
    with pytest.raises((ValueError,TypeError)):validate(cfg)


def test_production_api_uses_paired_profile_and_refuses_read_key(tmp_path):
    from eidolon_core.conversation_api import ConversationAPI
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.client_credentials import ClientCredentials
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.dialogue import SimulatedDialogueModel
    from eidolon_core.store import Store
    rt,service=setup(tmp_path,samples=1)
    runtime=synthetic_runtime(Store(tmp_path/'core'))
    ConversationStore(runtime.store,create=True)
    credentials=ClientCredentials(runtime.store,create=True)
    keys=[credentials.pair(client_id='pc'+str(i),actor='actor'+str(i))['token'] for i in range(2)]
    api=ConversationAPI(runtime,dialogue_model=SimulatedDialogueModel(runtime.catalog),services=rt,read_token='r'*40)
    def call(route,body,key=keys[0]):
        return api.handle('POST','/v1/conversations/'+route,{'Authorization':['Bearer '+key],'Content-Type':['application/json']},json.dumps(body).encode())
    try:
        assert call('identity_status',{},'r'*40)[0]==403
        assert call('identity_status',{},'invalid')[0]==401
        assert call('identity_status',{'profile_id':'user1'})[0]==400
        status,a=call('identity_begin',dict(modality='face',request_key='api',present=True,consent=True))
        assert status==200
        body=dict(session_id=a['session_id'],sample_key='one',capture_base64=encoded(1))
        assert call('identity_sample',body,keys[1])[0]==409
        status,a=call('identity_sample',body)
        assert status==200 and a['approval_sha256']
        assert call('identity_confirm',dict(session_id=a['session_id'],sha256=a['approval_sha256']))[0]==200
        assert not call('identity_status',{},keys[1])[1]['modalities'][0]['enrolled']
        assert call('document_preview',dict(request_key='invalid',name='x.exe',data_base64=encoded(1)))[1]['error']=='DOCUMENT_FORMAT_UNSUPPORTED'
    finally:api.close()


def test_isolated_engine_missing_model_fails_without_download():
    from eidolon_core.identity_runtime import observe_isolated
    with pytest.raises(IdentityError,match='ENGINE_UNAVAILABLE'):
        observe_isolated(settings()['modalities']['face'],'face',b'synthetic-image')
