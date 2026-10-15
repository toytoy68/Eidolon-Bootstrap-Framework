# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/build_weekend_bundle.py
# Description : Deterministic pinned two-repository weekend source bundle
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Reproducible source ZIP from two immutable Git commits. No working-tree files.

No checkout, network, install or extraction. Includes code/tests/tools, approved
recipe files and launchers; never includes corpus, caches, credentials or state.
The archive manifest inventories bytes, not runtime compatibility or approval.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
import zipfile

PROTOCOL="eidolon-weekend-bundle/1"
FORBIDDEN=re.compile(r"(^|/)(?:__pycache__|\.git|\.env|[^/]*\.(?:pyc|pyo|sqlite3?|db|key|pem|p12|log))(/|$)",re.I)
CORE_PREFIX=("eidolon-core/","standards/",".github/workflows/")
MEMORY_PREFIX=("core/","tests/","schemas/","standards/","docs/","deployment/","services/","scripts/","templates/","tools/",".github/workflows/")
CORE_FILES={"LICENSE","AGENTS.md","eidolon-core/README.md","eidolon-core/pyproject.toml","eidolon-core/TODO.md"}
MEMORY_FILES={"LICENSE","AGENTS.md","README.md","requirements.txt","requirements-dev.txt","requirements-qdrant.txt",
              "services/memory_bridge.py","docs/G269-OFFLINE-RUNTIME.md","pytest.ini","pyproject.toml","conftest.py"}


def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args])


def collect(repo,commit,kind):
    if type(commit) is not str or re.fullmatch(r"[0-9a-f]{40}",commit) is None:
        raise ValueError("explicit full commit required")
    if git(repo,"cat-file","-t",commit).strip()!=b"commit":raise ValueError("not a commit")
    prefixes,files=(CORE_PREFIX,CORE_FILES) if kind=="core" else (MEMORY_PREFIX,MEMORY_FILES)
    result={}
    for raw in git(repo,"ls-tree","-r","-z",commit).split(b"\0"):
        if not raw:continue
        meta,path=raw.decode().split("\t",1)
        if not (path in files or path.startswith(prefixes)):continue
        if path.startswith(("eidolon-core/docs/validation/", "docs/validation/", "docs/benchmarks/")):continue
        # Historical diagnostic logs are evidence, not deployable source.
        if path.startswith(("docs/", "eidolon-core/docs/")) and FORBIDDEN.search(path):continue
        mode,typ,oid=meta.split()
        if mode not in ("100644","100755") or typ!="blob" or FORBIDDEN.search(path):
            raise ValueError("non-source or forbidden entry: "+path)
        name="sources/"+kind+"/"+path
        safe_name(name)
        data=git(repo,"cat-file","blob",oid)
        if len(data)>32*1024*1024:raise ValueError("file budget")
        result[name]=(data,mode)
    if not result:raise ValueError("empty source selection")
    return result


def safe_name(name):
    if (type(name) is not str or "\\" in name or ":" in name or any(ord(c)<32 for c in name)
            or name.startswith("/") or any(p in ("",".","..") for p in name.split("/"))):
        raise ValueError("unsafe member path")


def build(core_repo,core_commit,memory_repo,memory_commit,output):
    entries={**collect(core_repo,core_commit,"core"),**collect(memory_repo,memory_commit,"memory")}
    entries["START-HERE.md"]=(b"# Eidolon weekend 17-18 October 2026\n\nOpen sources/core/eidolon-core/weekend/2026-10-17/README.md.\nSources only; no credentials, models, corpus or installed services.\n", "100644")
    manifest={"schema":PROTOCOL,"core_commit":core_commit,"memory_commit":memory_commit,
        "files":[{"path":p,"bytes":len(data),"sha256":sha256(data).hexdigest(),"mode":mode}
                 for p,(data,mode) in sorted(entries.items())]}
    entries["MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2).encode(),"100644")
    with open(output,"xb") as stream:
        with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,(data,mode) in sorted(entries.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,10,17,0,0,0));info.create_system=3
                info.external_attr=(0o100755 if mode=="100755" else 0o100644)<<16
                info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,data,compresslevel=9)
    return verify(output)


def verify(path):
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(infos)>10000 or len(set(names))!=len(names) or "MANIFEST.json" not in names:
            raise ValueError("invalid archive inventory")
        for info in infos:
            safe_name(info.filename)
            if info.file_size>32*1024*1024 or (info.external_attr>>16)&0o170000!=0o100000:
                raise ValueError("archive member budget/type")
        if sum(i.file_size for i in infos)>256*1024*1024:raise ValueError("archive total budget")
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d:raise ValueError("duplicate manifest field")
                d[k]=v
            return d
        manifest=json.loads(archive.read("MANIFEST.json"),object_pairs_hook=unique)
        if set(manifest)!={"schema","core_commit","memory_commit","files"} or manifest["schema"]!=PROTOCOL:
            raise ValueError("invalid manifest schema")
        if any(re.fullmatch(r"[0-9a-f]{40}",manifest[k]) is None for k in ("core_commit","memory_commit")):
            raise ValueError("invalid source pin")
        rows=manifest["files"]
        if len(rows)!=len(names)-1 or {r["path"] for r in rows}!=set(names)-{"MANIFEST.json"}:
            raise ValueError("manifest member mismatch")
        for row in rows:
            if set(row)!={"path","bytes","sha256","mode"} or row["mode"] not in ("100644","100755"):
                raise ValueError("invalid manifest row")
            data=archive.read(row["path"])
            if len(data)!=row["bytes"] or sha256(data).hexdigest()!=row["sha256"]:
                raise ValueError("manifest digest mismatch")
            expected=0o100755 if row["mode"]=="100755" else 0o100644
            if archive.getinfo(row["path"]).external_attr>>16!=expected:
                raise ValueError("manifest mode mismatch")
    return {"state":"VERIFIED_BYTES","files":len(rows),"sha256":sha256(Path(path).read_bytes()).hexdigest(),
            "core_commit":manifest["core_commit"],"memory_commit":manifest["memory_commit"],"qualified":False}


def main(argv=None):
    p=argparse.ArgumentParser(description="Build or verify pinned Eidolon weekend sources")
    p.add_argument("--verify",type=Path)
    p.add_argument("--core-repo",type=Path);p.add_argument("--core-commit")
    p.add_argument("--memory-repo",type=Path);p.add_argument("--memory-commit")
    p.add_argument("--output",type=Path);a=p.parse_args(argv)
    try:
        if a.verify:
            if any(v is not None for v in (a.core_repo,a.core_commit,a.memory_repo,a.memory_commit,a.output)):
                p.error("verify cannot be combined with build")
            result=verify(a.verify)
        else:
            if any(v is None for v in (a.core_repo,a.core_commit,a.memory_repo,a.memory_commit,a.output)):
                p.error("both pinned repositories and output required")
            result=build(a.core_repo,a.core_commit,a.memory_repo,a.memory_commit,a.output)
        print(json.dumps(result,sort_keys=True));return 0
    except (ValueError,OSError,TypeError,KeyError,zipfile.BadZipFile,subprocess.CalledProcessError):
        print(json.dumps({"state":"REFUSED","qualified":False}));return 2

if __name__=="__main__":raise SystemExit(main())
