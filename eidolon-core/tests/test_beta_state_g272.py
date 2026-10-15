# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_beta_state_g272.py
# Description : Copie privée sans réattribution, arrêt obligatoire et reprises conservées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import pytest
from eidolon_core.beta_runtime import BetaRuntime
from eidolon_core.beta_state import copy_state, StateError
from eidolon_core.identity_runtime import IdentityRuntime
from tests.test_beta_runtime_g270 import config
from tests.test_identity_runtime_g272 import settings, synthetic, encoded


def files(tmp_path):
    cfg=config(tmp_path); new=json.loads(json.dumps(cfg))
    target=tmp_path/'new-state';target.mkdir(mode=0o700)
    new['state_directory']=str(target)
    paths=[]
    for name,data in [('old.json',cfg),('new.json',new)]:
        p=tmp_path/name;p.write_text(json.dumps(data));p.chmod(0o600);paths.append(p)
    return cfg,new,*paths


def test_stopped_copy_preview_and_preservation(tmp_path):
    cfg,new,oldfile,newfile=files(tmp_path)
    rt=BetaRuntime(cfg)
    p=rt.preview('pc0','actor','retain','remember',{'text':'Private synthetic note'})
    with rt._db() as db: db.execute("UPDATE actions SET state='INFLIGHT',day='2026-10-15'")
    identity=IdentityRuntime(settings(),rt._db,rt.profile,observer=synthetic)
    session=identity.begin('pc0','face','pending',True,True)
    identity.sample('pc0',session['session_id'],'one',encoded(1))
    with pytest.raises(StateError,match='STOP_CORE'):copy_state(oldfile,newfile,apply=True)
    rt.close()
    source=Path(cfg['state_directory'])/'actions.sqlite3';original=source.read_bytes()
    target=Path(new['state_directory'])
    assert copy_state(oldfile,newfile)['state']=='PREVIEW' and list(target.iterdir())==[]
    result=copy_state(oldfile,newfile,apply=True)
    assert result['state']=='COPIED_REVIEW_REQUIRED' and source.read_bytes()==original
    assert (target/'actions.sqlite3').stat().st_mode & 0o777 == 0o600
    with pytest.raises(StateError,match='NOT_EMPTY'):copy_state(oldfile,newfile,apply=True)
    restored=BetaRuntime(new)
    try:
        receipt=restored.receipts('pc0')[0]
        assert receipt['state']=='UNKNOWN' and receipt['proposal']==p['proposal']
        assert not restored.receipts('pc1')
        with restored._db() as db:
            assert db.execute('SELECT day FROM actions').fetchone()[0]=='2026-10-15'
            row=db.execute('SELECT status,samples FROM identity_sessions').fetchone()
            assert tuple(row)==('EXPIRED','[]')
    finally:restored.close()


@pytest.mark.parametrize('change',['client','port','token','root','quota'])
def test_no_reassignment_of_private_history_or_permissions(tmp_path,change):
    cfg,new,oldfile,newfile=files(tmp_path)
    rt=BetaRuntime(cfg);rt.close()
    if change=='client':new['clients']['pc0']='user1'
    if change=='port':new['profiles']['user0']['memory_port']=19999
    if change=='token':new['profiles']['user0']['read_token_file']='/other/token'
    if change=='root':new['profiles']['user0']['file_roots']['nas']='/other/nas'
    if change=='quota':new['profiles']['user0']['daily_web_limit']=999
    newfile.write_text(json.dumps(new))
    with pytest.raises(StateError,match='REBIND'):copy_state(oldfile,newfile,apply=True)
    assert list(Path(new['state_directory']).iterdir())==[]


def test_add_identity_config_only_on_new_state(tmp_path):
    cfg,new,oldfile,newfile=files(tmp_path)
    rt=BetaRuntime(cfg);rt.close()
    identity=tmp_path/'identity.json';identity.write_text(json.dumps(settings()));identity.chmod(0o600)
    new['identity_config']=str(identity);newfile.write_text(json.dumps(new))
    copy_state(oldfile,newfile,apply=True)
    rt=BetaRuntime(new)
    try:assert rt.capabilities('pc0')['identity_enrolment']
    finally:rt.close()


def test_sidecars_and_symlink_destinations_refused(tmp_path):
    cfg,new,oldfile,newfile=files(tmp_path)
    rt=BetaRuntime(cfg);rt.close()
    journal=Path(cfg['state_directory'])/'actions.sqlite3-journal';journal.touch()
    with pytest.raises(StateError,match='RECOVERY'):copy_state(oldfile,newfile)
    journal.unlink()
    target=Path(new['state_directory']);target.rmdir();target.symlink_to(Path(cfg['state_directory']),target_is_directory=True)
    with pytest.raises(ValueError):copy_state(oldfile,newfile,apply=True)
