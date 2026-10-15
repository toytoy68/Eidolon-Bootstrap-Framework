# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : src/eidolon_core/maintenance_host.py
# Description : Production host collector and explicit one-tick maintenance entry
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit host entry point for one maintenance tick, no installed daemon.

check-only never imports Memory or opens Qdrant. execute requires an explicit
operator allow-list of Information IDs in a trusted configuration. No delete
permission is granted. Paths and sources are operator-owned; labels do not
provide authentication. The collector does not guess human inactivity from CPU
load. Without a fresh activity receipt, maintenance remains deferred.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone, time as walltime
import json
import math
import os
from pathlib import Path
import re
import time

from .runtime_json import read_json_snapshot
from .maintenance_policy import validate_host_policy, run_with_policy
from .maintenance_observations import _aware


def read_config(path):
    path=Path(path).absolute()
    return read_json_snapshot(str(path.parent),path.name,max_bytes=65536,max_depth=6)


def capture(policy, *, now, activity=None):
    if policy.load_unit!="load1_per_cpu":
        raise ValueError("collector requires load1_per_cpu")
    at=_aware(now,"now")
    value={"source":policy.expected_source,"at":at.isoformat()}
    try:
        elapsed=time.clock_gettime(time.CLOCK_BOOTTIME)
        if math.isfinite(elapsed) and elapsed>=0:
            value["boot_at"]=(at-timedelta(seconds=elapsed)).isoformat()
    except (AttributeError,OSError,OverflowError):
        pass
    try:
        count=os.cpu_count()
        load=os.getloadavg()[0]
        if type(count) is int and count>0 and math.isfinite(load) and load>=0:
            value["load"]={"observed_at":at.isoformat(),"ratio":load/count,"unit":"load1_per_cpu"}
    except (AttributeError,OSError):
        pass
    if activity is not None:
        if (type(activity) is not dict or set(activity)!={"schema","source","observed_at","last_activity"}
                or activity["schema"]!="eidolon-activity-receipt/1"
                or activity["source"]!=policy.expected_source):
            raise ValueError("invalid activity receipt")
        observed=_aware(activity["observed_at"],"activity observation")
        last=_aware(activity["last_activity"],"last activity")
        if not timedelta(0)<=at-observed<=policy.max_observation_age or last>observed:
            raise ValueError("stale or future activity receipt")
        value["last_activity"]=last.isoformat()
    return value


def validate_runtime(raw):
    fields={"schema","canonical_root","state_directory","index_config","profile_id","allowed_information_ids"}
    profile_scope = (type(raw) is dict and raw.get("schema") == "eidolon-maintenance-runtime/2"
                     and set(raw) == (fields - {"allowed_information_ids"}) | {"scope"}
                     and raw.get("scope") == "isolated_profile_root")
    if not profile_scope and (type(raw) is not dict or set(raw)!=fields or raw["schema"]!="eidolon-maintenance-runtime/1"):
        raise ValueError("invalid maintenance runtime")
    result=dict(raw)
    for key in ("canonical_root","state_directory","index_config"):
        v=raw[key]
        if type(v) is not str or not Path(v).is_absolute() or ".." in Path(v).parts:
            raise ValueError("explicit absolute runtime paths required")
        result[key]=Path(v)
    if type(raw["profile_id"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",raw["profile_id"]):
        raise ValueError("invalid maintenance profile")
    ids=[] if profile_scope else raw["allowed_information_ids"]
    if (type(ids) is not list or len(ids)>1000 or any(type(i) is not str or
        not re.fullmatch(r"[A-Za-z0-9._-]{1,256}",i) for i in ids) or len(ids)!=len(set(ids))):
        raise ValueError("explicit distinct Information allow-list required")
    result["allowed_information_ids"]=None if profile_scope else frozenset(ids)
    return result


def run_once(policy, observation, *, now, runtime=None, activity_provider=None):
    opened=[]
    class Preview:
        def tick(self, **kwargs):
            return {"state":"NOT_EXECUTED"}
    def factory():
        if runtime is None:
            return Preview()
        from core.persistence import has_symlink_component
        from core.indexing.runtime import load_runtime,open_index
        from core.indexing.change_journal import ChangeJournal
        from core.indexing.maintenance import IndexMaintenance
        r=validate_runtime(runtime)
        root,state=r["canonical_root"],r["state_directory"]
        if (any(has_symlink_component(p) for p in (root,state,r["index_config"]))
                or not root.is_dir() or not state.is_dir() or state.stat().st_mode & 0o077
                or state==root or root in state.parents or state in root.parents):
            raise ValueError("separate existing canonical and private state directories required")
        config=load_runtime(r["index_config"])
        index=open_index(config);opened.append(index.client)
        profile=r["profile_id"];allowed=r["allowed_information_ids"]
        if allowed is None:
            from services.profile_binding import require_binding
            if root.name != "persistent" or root.parent.name != "memory":
                raise ValueError("isolated profile canonical layout required")
            require_binding(root.parent.parent, profile)
        authorize=lambda who,ident,action: who==profile and (allowed is None or ident in allowed) and action=="index.upsert"
        if config.projection == "archive_passages":
            from core.maintenance.window import preview_window
            class PassageTick:
                def tick(self, *, at, last_activity, boot_at, load_ok):
                    decision = preview_window(at=at, last_activity=last_activity, start=walltime(4), end=walltime(8),
                                              zone="Europe/Paris", minimum_idle_minutes=30)
                    reasons = list(decision["reasons"])
                    if (at-boot_at).total_seconds() < 1800:
                        reasons.append("BOOT_RECENT")
                    if load_ok is not True:
                        reasons.append("LOAD_NOT_READY")
                    if reasons:
                        return {"state": "DEFERRED", "reasons": reasons}
                    def idle():
                        if activity_provider is None:
                            return True  # explicit snapshot invocation; no live observation claimed
                        current = datetime.now(timezone.utc)
                        fresh = capture(policy, now=current, activity=activity_provider())
                        previous = _aware(fresh["last_activity"], "activity")
                        return (current-previous).total_seconds() >= 1800
                    return index.sync(root, authorize=lambda ident: authorize(profile, ident, "index.upsert"),
                                      should_continue=idle)
            return PassageTick()
        return IndexMaintenance(state/"cycle.sqlite3",ChangeJournal(state/"changes.sqlite3"),
            canonical_checkpoint=state/"canonical.sqlite3",orphan_checkpoint=state/"orphans.sqlite3",
            canonical_root=root,index=index,authorize=authorize,profile_id=profile,
            expected_profile_id=profile,expected_model_id=config.embedding_id)
    try:
        result=run_with_policy(observation,policy,now=now,make_maintenance=factory)
        report=result.report if isinstance(result.report,dict) else asdict(result.report)
        return {"schema":"eidolon-maintenance-tick/1","mode":"CHECK_ONLY" if runtime is None else "EXECUTE",
                "observed_at":result.observed_at.isoformat(),"at":result.observation.at.isoformat(),
                "load_ok":result.observation.load_ok,"notes":list(result.observation.notes),"report":report}
    finally:
        for client in opened:
            client.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description="One explicit host observation or maintenance tick")
    parser.add_argument("--policy",required=True,type=Path)
    parser.add_argument("--snapshot",type=Path)
    parser.add_argument("--activity",type=Path)
    parser.add_argument("--activity-core-port", type=int)
    parser.add_argument("--activity-token-file", type=Path)
    parser.add_argument("--runtime",type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture-only",action="store_true")
    mode.add_argument("--check-only",action="store_true")
    mode.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)
    if args.execute != (args.runtime is not None):
        parser.error("--execute requires --runtime; other modes forbid it")
    if (args.activity_core_port is None) != (args.activity_token_file is None):
        parser.error("remote activity requires both Core port and read token file")
    if args.activity is not None and args.activity_core_port is not None:
        parser.error("select either local or remote activity")
    if args.snapshot is not None and (args.activity is not None or args.activity_core_port is not None or args.capture_only):
        parser.error("snapshot cannot be combined with capture or activity")
    try:
        policy=validate_host_policy(read_config(args.policy))
        now=datetime.now(timezone.utc)
        from .activity import read_remote
        activity_provider = ((lambda: read_remote(args.activity_core_port, args.activity_token_file))
                             if args.activity_core_port is not None else
                             (lambda: read_config(args.activity)) if args.activity else None)
        observation=read_config(args.snapshot) if args.snapshot else capture(policy,now=now,
            activity=activity_provider() if activity_provider else None)
        if args.capture_only:
            report=observation
        else:
            runtime=read_config(args.runtime) if args.execute else None
            report=run_once(policy,observation,now=now,runtime=runtime,
                activity_provider=activity_provider)
        print(json.dumps(report,sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({"state":"REFUSED_OR_INCOMPLETE","effects":"UNKNOWN" if args.execute else "NONE"}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
