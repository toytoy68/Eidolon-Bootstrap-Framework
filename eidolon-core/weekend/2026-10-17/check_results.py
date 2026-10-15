# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : weekend/2026-10-17/check_results.py
# Description : Reject missing weekend evidence without declaring a beta qualified
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Validate evidence completeness. Does not execute tests or attest their truth."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

IDS={"V%02d"%i for i in range(1,13)}|{"P%02d"%i for i in range(1,11)}|{"O%02d"%i for i in range(1,5)}|{"G%02d"%i for i in range(1,11)}

def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError("duplicate field")
        result[k]=v
    return result

def check(raw):
    if type(raw) is not dict or set(raw)!={"schema","core_commit","memory_commit","checks"} or raw["schema"]!="eidolon-weekend-evidence/1":
        raise ValueError("invalid evidence schema")
    pinned=all(type(raw[k]) is str and re.fullmatch(r"[0-9a-f]{40}",raw[k]) for k in ("core_commit","memory_commit"))
    checks=raw["checks"]
    if type(checks) is not list or len(checks)!=len(IDS):raise ValueError("missing evidence rows")
    seen=set();counts={k:0 for k in ("PASS","FAIL","BLOCKED","NOT_RUN")}
    for row in checks:
        if type(row) is not dict or set(row)!={"id","criterion","status","observed_at","evidence"}:
            raise ValueError("invalid evidence row")
        ident=row["id"]
        if type(ident) is not str or ident not in IDS or ident in seen:raise ValueError("duplicate or unknown test")
        seen.add(ident)
        status=row["status"]
        if type(status) is not str or status not in counts:raise ValueError("unknown status")
        if type(row["criterion"]) is not str or not row["criterion"].strip():raise ValueError("missing criterion")
        if status!="NOT_RUN":
            if type(row["evidence"]) is not str or not row["evidence"].strip() or len(row["evidence"])>2048:
                raise ValueError("dated evidence required")
            at=datetime.fromisoformat(row["observed_at"])
            if at.tzinfo is None or at.year<2000:raise ValueError("dated evidence required")
        counts[status]+=1
    complete=pinned and counts["PASS"]==len(IDS)
    return {"state":"EVIDENCE_COMPLETE_REVIEW_REQUIRED" if complete else "INCOMPLETE",
            "counts":counts,"revisions_pinned":bool(pinned),"beta_authorized":False},0 if complete else 1

def main(argv=None):
    p=argparse.ArgumentParser(description="Check weekend evidence completeness")
    p.add_argument("input",type=Path);args=p.parse_args(argv)
    try:
        with args.input.open("rb") as f:data=f.read(131073)
        if len(data)>131072:raise ValueError("evidence budget")
        raw=json.loads(data.decode("utf-8"),object_pairs_hook=unique)
        report,code=check(raw)
    except (OSError,ValueError,TypeError,RecursionError):
        report,code={"state":"INVALID","beta_authorized":False},2
    print(json.dumps(report,sort_keys=True));return code

if __name__=="__main__":raise SystemExit(main())
