# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : weekend/2026-10-17/inventory_vm.py
# Description : Read-only VM inventory for operator-run weekend validation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read-only bounded inventory; keep output private. Never executes service changes."""
import argparse
import json
from pathlib import Path
import platform
import re
import subprocess

def run(args):
    try:
        done=subprocess.run(args,capture_output=True,timeout=8)
        return {"exit_code":done.returncode,"output":done.stdout[:16384].decode(errors="replace"),
                "truncated":len(done.stdout)>16384}
    except (OSError,subprocess.TimeoutExpired):return {"state":"UNAVAILABLE"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--core-repo",required=True,type=Path)
    parser.add_argument("--memory-repo",required=True,type=Path)
    parser.add_argument("--service",action="append",default=[])
    args=parser.parse_args()
    if any(re.fullmatch(r"[a-zA-Z0-9_.@-]{1,100}\.service",s) is None or s.startswith("-") for s in args.service):
        parser.error("explicit service unit names required")
    result={"schema":"eidolon-weekend-inventory/1","python":platform.python_version(),"platform":platform.system(),
        "qualification":"NOT_EVALUATED","services":{},"repositories":{}}
    for label,path in (("core",args.core_repo),("memory",args.memory_repo)):
        result["repositories"][label]={"head":run(["git","-C",str(path),"rev-parse","HEAD"]),
            "dirty":run(["git","-C",str(path),"status","--porcelain","--untracked-files=no"])}
    for unit in args.service:
        result["services"][unit]=run(["systemctl","show",unit,"--no-pager",
            "--property=ActiveState,SubState,MainPID,User,FragmentPath"])
    result["listeners"]=run(["ss","-H","-ltn"])
    print(json.dumps(result,sort_keys=True,indent=2))

if __name__=="__main__":main()
