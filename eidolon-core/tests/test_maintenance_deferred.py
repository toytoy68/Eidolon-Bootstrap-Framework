# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_maintenance_deferred.py
# Description : Deferred maintenance avoids index I/O; safe failure stages
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime, timedelta, timezone
import json
import os
import pytest
from eidolon_core import maintenance_host as host
from eidolon_core.maintenance_policy import validate_host_policy


def policy():
    return validate_host_policy(dict(schema="eidolon-host-maintenance-policy/1",
        expected_source="host.eidolon", max_observation_age_seconds=120,
        max_load_age_seconds=120, load_unit="load1_per_cpu", load_limit=0.7))


@pytest.mark.parametrize("hour,idle,boot,load,reason", [
    (21,3600,7200,0.1,"OUTSIDE_WINDOW"),
    (4,0,7200,0.1,"ACTIVITY_RECENT"),
    (4,3600,60,0.1,"BOOT_RECENT"),
    (4,3600,7200,0.9,"LOAD_NOT_READY"),
])
def test_deferred_does_not_contact_index(tmp_path, monkeypatch, hour, idle, boot, load, reason):
    if os.environ.get("EIDOLON_MEMORY_INTEGRATION") != "1":
        pytest.skip("explicit Memory integration")
    import core.indexing.runtime as rt
    root=tmp_path/"corpus";root.mkdir()
    state=tmp_path/"state";state.mkdir(mode=0o700)
    cfg=rt.IndexRuntime("eidolon_deferred", "fixture", "a"*64, 2, "",11434,6333,3,4096,2048,"archive_passages")
    monkeypatch.setattr(rt,"load_runtime",lambda _:cfg)
    def forbidden(*a,**kw):
        pytest.fail("deferred tick contacted Qdrant")
    monkeypatch.setattr(rt,"open_index",forbidden)
    now=datetime(2026,11,21,hour,tzinfo=timezone.utc)
    obs=dict(source="host.eidolon",at=now.isoformat(),
        last_activity=(now-timedelta(seconds=idle)).isoformat(),
        boot_at=(now-timedelta(seconds=boot)).isoformat(),
        load=dict(observed_at=now.isoformat(),ratio=load,unit="load1_per_cpu"))
    runtime=dict(schema="eidolon-maintenance-runtime/1",canonical_root=str(root),
        state_directory=str(state),index_config=str(tmp_path/"index.json"),
        profile_id="owner",allowed_information_ids=["fixture"])
    result=host.run_once(policy(),obs,now=now,runtime=runtime)
    assert result["report"]["state"]=="DEFERRED"
    assert reason in result["report"]["reasons"]
    assert list(state.iterdir())==[]


@pytest.mark.parametrize("failure,expected_effects", [("ACTIVITY","NONE"),("TICK","UNKNOWN")])
def test_failure_reports_phase_without_exception_text(monkeypatch,capsys,failure,expected_effects):
    import eidolon_core.activity as activity
    monkeypatch.setattr(host,"read_config",lambda _: {})
    monkeypatch.setattr(host,"validate_host_policy",lambda _:policy())
    def fail(*a,**kw):
        raise ValueError("PRIVATE_SENTINEL_DO_NOT_LOG")
    if failure=="ACTIVITY":
        monkeypatch.setattr(activity,"read_remote",fail)
    else:
        monkeypatch.setattr(activity,"read_remote",lambda *a:None)
        monkeypatch.setattr(host,"run_once",fail)
    assert host.main(["--policy","/unused","--activity-core-port","8767",
        "--activity-token-file","/unused","--runtime","/unused","--execute"])==2
    output=capsys.readouterr().out
    assert "PRIVATE_SENTINEL" not in output
    assert json.loads(output)==dict(state="REFUSED_OR_INCOMPLETE",effects=expected_effects,stage=failure)


def test_eligible_passage_tick_opens_syncs_and_closes(tmp_path,monkeypatch):
    if os.environ.get("EIDOLON_MEMORY_INTEGRATION") != "1":
        pytest.skip("explicit Memory integration")
    import core.indexing.runtime as rt
    root=tmp_path/"corpus";root.mkdir()
    state=tmp_path/"state";state.mkdir(mode=0o700)
    cfg=rt.IndexRuntime("eidolon_eligible","fixture","a"*64,2,"",11434,6333,3,4096,2048,"archive_passages")
    monkeypatch.setattr(rt,"load_runtime",lambda _:cfg)
    calls=[]
    class Client:
        def close(self):calls.append("close")
    class Index:
        client=Client()
        def sync(self,path,*,authorize,should_continue):
            assert path==root and authorize("fixture") and not authorize("outside")
            assert should_continue()
            calls.append("sync")
            return {"state":"UNCHANGED"}
    def opening(config):
        assert config==cfg;calls.append("open");return Index()
    monkeypatch.setattr(rt,"open_index",opening)
    now=datetime(2026,11,21,4,tzinfo=timezone.utc)
    obs=dict(source="host.eidolon",at=now.isoformat(),
        last_activity=(now-timedelta(hours=1)).isoformat(),boot_at=(now-timedelta(hours=2)).isoformat(),
        load=dict(observed_at=now.isoformat(),ratio=0.1,unit="load1_per_cpu"))
    runtime=dict(schema="eidolon-maintenance-runtime/1",canonical_root=str(root),
        state_directory=str(state),index_config=str(tmp_path/"index.json"),
        profile_id="owner",allowed_information_ids=["fixture"])
    assert host.run_once(policy(),obs,now=now,runtime=runtime)["report"]["state"]=="UNCHANGED"
    assert calls==["open","sync","close"]
