# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme-install.py
# Description : Installation ou recette du service passif DARME
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json, os, pathlib, shutil, subprocess, sys, tarfile, datetime
source=pathlib.Path(sys.argv[1])
units=json.loads(sys.argv[2])
account="eidolon-darme"
def run(args): subprocess.run(args,check=True)
if subprocess.run(["id","-u",account],capture_output=True).returncode:
    run(["useradd","--system","--user-group","--home-dir","/nonexistent","--shell","/usr/sbin/nologin",account])
uid=int(subprocess.check_output(["id","-u",account]))
if uid==0: raise SystemExit("Refusing privileged service account")
backup=pathlib.Path("/var/backups/eidolon")
backup.mkdir(mode=0o700,parents=True,exist_ok=True)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
with tarfile.open(backup/("darme-preinstall-"+stamp+".tar.gz"),"w:gz") as archive:
    for p in ("/opt/eidolon-darme","/etc/eidolon-darme","/etc/systemd/system/eidolon-darme.service","/var/lib/eidolon-darme"):
        if pathlib.Path(p).exists(): archive.add(p,arcname=p.lstrip("/"))
os.chmod(backup/("darme-preinstall-"+stamp+".tar.gz"),0o600)
for d in ("/opt/eidolon-darme","/opt/eidolon-darme/eidolon_core","/etc/eidolon-darme"):
    pathlib.Path(d).mkdir(parents=True,exist_ok=True)
    os.chmod(d,0o755); os.chown(d,0,0)
for name in ("darme.py","darme_store.py","darme_service.py"):
    target=pathlib.Path("/opt/eidolon-darme/eidolon_core")/name
    shutil.copyfile(source/name,target);os.chmod(target,0o644);os.chown(target,0,0)
pathlib.Path("/opt/eidolon-darme/eidolon_core/__init__.py").write_text("")
for name,target in (("launch.py","/opt/eidolon-darme/launch.py"),("eidolon-darme.service","/etc/systemd/system/eidolon-darme.service")):
    shutil.copyfile(source/name,target);os.chmod(target,0o644);os.chown(target,0,0)
pathlib.Path("/etc/eidolon-darme/config.json").write_text(json.dumps({"units":units,"interval":10})+"\n")
os.chmod("/etc/eidolon-darme/config.json",0o644)
run(["systemd-analyze","verify","/etc/systemd/system/eidolon-darme.service"])
run(["systemctl","daemon-reload"])
run(["systemctl","enable","--now","eidolon-darme.service"])
print("Installed; runtime verification required")
