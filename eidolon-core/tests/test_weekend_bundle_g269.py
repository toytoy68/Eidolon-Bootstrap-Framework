# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_weekend_bundle_g269.py
# Description : Archive byte integrity and evidence completeness contract
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import importlib.util
import json
import subprocess
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
bundle=load("weekend_bundle",ROOT/"tools/build_weekend_bundle.py")
evidence=load("weekend_evidence",ROOT/"weekend/2026-10-17/check_results.py")

def repo(tmp,name,path):
    root=tmp/name;root.mkdir()
    def git(*args):return subprocess.check_output(["git","-C",str(root),*args])
    git("init","-q");git("config","user.name","Test");git("config","user.email","test@example.invalid")
    f=root/path;f.parent.mkdir(parents=True);f.write_text("# source\n")
    git("add",".");git("commit","-qm","fixture")
    return root,git("rev-parse","HEAD").decode().strip()

def test_bundle_immutable_deterministic_and_tampering(tmp_path):
    cr,cs=repo(tmp_path,"core","eidolon-core/src/eidolon_core/fixture.py")
    mr,ms=repo(tmp_path,"memory","core/fixture.py")
    (cr/"eidolon-core/src/eidolon_core/fixture.py").write_text("UNCOMMITTED")
    a=tmp_path/"a.zip";b=tmp_path/"b.zip"
    result=bundle.build(cr,cs,mr,ms,a);bundle.build(cr,cs,mr,ms,b)
    assert a.read_bytes()==b.read_bytes() and result["qualified"] is False
    with pytest.raises(FileExistsError):bundle.build(cr,cs,mr,ms,a)
    with zipfile.ZipFile(a) as src,zipfile.ZipFile(tmp_path/"bad.zip","w") as dst:
        for info in src.infolist():dst.writestr(info,b"tampered" if info.filename.endswith("fixture.py") else src.read(info))
    with pytest.raises(ValueError,match="digest"):bundle.verify(tmp_path/"bad.zip")

@pytest.mark.parametrize("path",["../bad","/absolute","x/../bad","x\\bad","x:bad"])
def test_member_paths_refused(path):
    with pytest.raises(ValueError):bundle.safe_name(path)

def test_evidence_never_promotes_missing_rows_or_guesses_results():
    raw=json.loads((ROOT/"weekend/2026-10-17/results.template.json").read_text())
    report,code=evidence.check(raw)
    assert code==1 and report["counts"]["NOT_RUN"]==44 and not report["beta_authorized"]
    raw["core_commit"]="a"*40;raw["memory_commit"]="b"*40
    for row in raw["checks"]:
        row.update(status="PASS",observed_at="2026-10-17T12:00:00+02:00",evidence="private report case")
    report,code=evidence.check(raw)
    assert code==0 and report["state"]=="EVIDENCE_COMPLETE_REVIEW_REQUIRED" and not report["beta_authorized"]
    raw["checks"][0]["evidence"]=None
    with pytest.raises(ValueError):evidence.check(raw)
