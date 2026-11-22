#!/usr/bin/python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : preflight.py
# Description : Read-only deployment preflight
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import argparse,json,os,pwd,grp,hashlib,tarfile,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent;a=argparse.ArgumentParser();a.add_argument('--core-user',required=True);args=a.parse_args()
m=json.loads((p/'manifest.json').read_text());archive=p/'executor-source.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['archive_sha256']
with tarfile.open(archive) as t:
 entries=t.getmembers();assert {x.name for x in entries}=={'src/'+x for x in m['files']}
 for x in entries:
  assert x.isfile() and '..' not in Path(x.name).parts
  assert hashlib.sha256(t.extractfile(x).read()).hexdigest()==m['files'][x.name[4:]]
uid=pwd.getpwnam(args.core_user).pw_uid;assert uid>0,'Core must be non-root'
try:service=pwd.getpwnam('eidolon-darme-exec');service_uid=service.pw_uid;assert service_uid>0 and service_uid!=uid
except KeyError:service_uid=None
probe=subprocess.run(['/usr/bin/bwrap','--unshare-all','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','/usr/bin/true'],capture_output=True)
print(json.dumps(dict(archive_verified=True,files=len(entries),core_user=args.core_user,core_uid=uid,service_uid=service_uid,bwrap_current_account_ok=probe.returncode==0,production_deployed=False,ready_for_provisioning=probe.returncode==0,required=['create dedicated service account and socket group if absent','install pinned root-owned source','configure explicit Core UID','qualify real accounts on target','explicit Runtime remote_registry wiring; no default substitution'])))

if probe.returncode != 0:raise SystemExit(2)
