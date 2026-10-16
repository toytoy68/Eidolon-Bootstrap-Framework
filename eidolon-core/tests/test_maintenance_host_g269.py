# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_maintenance_host_g269.py
# Description : Collector policy and actual Memory one-tick integration
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime,timedelta,timezone
import pytest
from eidolon_core.maintenance_host import capture,run_once,validate_runtime
from eidolon_core.maintenance_policy import validate_host_policy

NOW=datetime(2026,10,17,3,0,tzinfo=timezone.utc)

def policy():
    return validate_host_policy(dict(schema="eidolon-host-maintenance-policy/1",expected_source="host.eidolon",
        max_observation_age_seconds=120,max_load_age_seconds=120,load_unit="load1_per_cpu",load_limit=0.7))

def test_unknown_activity_stays_recent_and_no_runtime_import(monkeypatch):
    import builtins
    real=builtins.__import__
    def guarded(name,*a,**k):
        assert not name.startswith("core."), "check-only must not import Memory"
        return real(name,*a,**k)
    monkeypatch.setattr(builtins,"__import__",guarded)
    observation=capture(policy(),now=NOW)
    result=run_once(policy(),observation,now=NOW)
    assert "LAST_ACTIVITY_UNKNOWN" in result["notes"]
    assert result["report"]=={"state":"NOT_EXECUTED"}

def test_activity_requires_fresh_receipt():
    activity=dict(schema="eidolon-activity-receipt/1",source="host.eidolon",observed_at=NOW.isoformat(),
                  last_activity=(NOW-timedelta(hours=1)).isoformat())
    assert capture(policy(),now=NOW,activity=activity)["last_activity"]==activity["last_activity"]
    with pytest.raises(ValueError,match="stale"):
        capture(policy(),now=NOW+timedelta(minutes=3),activity=activity)

def test_invalid_observation_precedes_runtime_construction():
    with pytest.raises(ValueError):
        run_once(policy(),{"source":"other","at":NOW.isoformat()},now=NOW,runtime={})

def test_runtime_requires_explicit_allowlist():
    raw=dict(schema="eidolon-maintenance-runtime/1",canonical_root="/srv/corpus/memory/persistent",
        state_directory="/srv/state",index_config="/etc/eidolon/index.json",profile_id="owner",
        allowed_information_ids=["info-1"])
    assert validate_runtime(raw)["allowed_information_ids"]==frozenset(["info-1"])
    for key,val in [("allowed_information_ids",["*"]),("allowed_information_ids",["a","a"]),
                    ("canonical_root","relative"),("index_config","/etc/../a")]:
        with pytest.raises(ValueError):validate_runtime({**raw,key:val})

def test_execute_one_real_tick_and_close_client(tmp_path,monkeypatch):
    import os
    if os.environ.get("EIDOLON_MEMORY_INTEGRATION")!="1":pytest.skip("explicit Memory integration")
    from contextlib import closing
    from qdrant_client import QdrantClient
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.indexing.qdrant_index import QdrantIndex
    from core.indexing.runtime import IndexRuntime
    import core.indexing.runtime as rt
    root=tmp_path/"corpus/memory/persistent"
    FilesystemBackend(root,tmp_path/"corpus/memory/history").store(Memory("a",content="fixture"))
    state=tmp_path/"state";state.mkdir(mode=0o700)
    cfg=IndexRuntime("eidolon_g269", "fixture", "a"*64,2,"",11434,6333,3,4096,2048)
    client=QdrantClient(":memory:")
    index=QdrantIndex(client,cfg.alias,embed=lambda _:[1.,0.],dimensions=2,embedding_id=cfg.embedding_id,create=True)
    closed=[]
    monkeypatch.setattr(client,"close",lambda:closed.append(True))
    monkeypatch.setattr(rt,"load_runtime",lambda _:cfg)
    monkeypatch.setattr(rt,"open_index",lambda _:index)
    runtime=dict(schema="eidolon-maintenance-runtime/1",canonical_root=str(root),state_directory=str(state),
        index_config=str(tmp_path/"index.json"),profile_id="owner",allowed_information_ids=["a"])
    obs=dict(source="host.eidolon",at=NOW.isoformat(),last_activity=(NOW-timedelta(hours=1)).isoformat(),
        boot_at=(NOW-timedelta(hours=2)).isoformat(),load=dict(observed_at=NOW.isoformat(),ratio=0.1,unit="load1_per_cpu"))
    result=run_once(policy(),obs,now=NOW,runtime=runtime)
    assert result["mode"]=="EXECUTE" and result["report"]["state"]=="ACTIVE"
    assert (state/"cycle.sqlite3").is_file() and closed==[True]


def test_remote_receipt_is_observed_after_network_response(monkeypatch, capsys):
    import json
    import eidolon_core.maintenance_host as host
    import eidolon_core.activity as activity
    clock = [NOW]
    class Clock:
        @staticmethod
        def now(zone):
            return clock[0]
    def remote(*args):
        clock[0] += timedelta(seconds=1)
        return dict(schema="eidolon-activity-receipt/1", source="host.eidolon",
                    observed_at=clock[0].isoformat(), last_activity=NOW.isoformat())
    monkeypatch.setattr(host, "datetime", Clock)
    monkeypatch.setattr(host, "read_config", lambda _: {})
    monkeypatch.setattr(host, "validate_host_policy", lambda _: policy())
    monkeypatch.setattr(activity, "read_remote", remote)
    assert host.main(["--policy", "/unused", "--activity-core-port", "8767",
                      "--activity-token-file", "/unused-token", "--capture-only"]) == 0
    assert json.loads(capsys.readouterr().out)["at"] == clock[0].isoformat()
