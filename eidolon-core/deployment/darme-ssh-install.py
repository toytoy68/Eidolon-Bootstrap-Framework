# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme-ssh-install.py
# Description : Installe la collecte SSH passive et sa cle privee locale
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import os,pathlib,sys,subprocess,shutil,tarfile,datetime,json,pwd,grp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
source=pathlib.Path(sys.argv[1]);account="eidolon-darme-ssh"
def run(args):subprocess.run(args,check=True)
backup=pathlib.Path("/var/backups/eidolon");backup.mkdir(parents=True,exist_ok=True)
os.umask(0o077)
archive=backup/("darme-ssh-preinstall-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")+".tar.gz")
with tarfile.open(archive,"w:gz") as t:
 for p in ("/opt/eidolon-darme","/etc/eidolon-darme","/etc/eidolon-darme-ssh","/etc/systemd/system/eidolon-darme.service.d","/etc/systemd/system/eidolon-darme-ssh.service"):
  if pathlib.Path(p).exists():t.add(p,arcname=p.lstrip("/"))
if subprocess.run(["id","-u",account],capture_output=True).returncode:
 run(["useradd","--system","--user-group","--home-dir","/nonexistent","--shell","/usr/sbin/nologin",account])
if pwd.getpwnam(account).pw_uid==0:raise SystemExit("Privileged collector account refused")
keys=pathlib.Path("/etc/eidolon-darme-ssh");keys.mkdir(exist_ok=True);os.chmod(keys,0o750);os.chown(keys,0,grp.getgrnam(account).gr_gid)
private=keys/"private.raw"
if private.exists():
 if private.is_symlink():raise SystemExit("Key symlink refused")
 key=Ed25519PrivateKey.from_private_bytes(private.read_bytes())
else:
 key=Ed25519PrivateKey.generate()
 private.write_bytes(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
os.chmod(private,0o640);os.chown(private,0,grp.getgrnam(account).gr_gid)
public=pathlib.Path("/etc/eidolon-darme/ssh-public.raw")
raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
if public.exists() and public.read_bytes()!=raw:raise SystemExit("Public key mismatch refused")
public.write_bytes(raw);os.chmod(public,0o644);os.chown(public,0,0)
for name in ("darme_service.py","darme_machine.py","darme_ssh.py","monitor_tools.py"):
 target=pathlib.Path("/opt/eidolon-darme/eidolon_core")/name
 shutil.copyfile(source/name,target);os.chmod(target,0o644);os.chown(target,0,0)
for name,target in (("ssh-launch.py","/opt/eidolon-darme/ssh-launch.py"),("eidolon-darme-ssh.service","/etc/systemd/system/eidolon-darme-ssh.service")):
 shutil.copyfile(source/name,target);os.chmod(target,0o644);os.chown(target,0,0)
drop=pathlib.Path("/etc/systemd/system/eidolon-darme.service.d");drop.mkdir(exist_ok=True)
(drop/"ssh.conf").write_text("[Unit]\nWants=eidolon-darme-ssh.service\nAfter=eidolon-darme-ssh.service\n")
config=pathlib.Path("/etc/eidolon-darme/config.json");data=json.loads(config.read_text())
if "eidolon-darme-ssh.service" not in data["units"]:data["units"].append("eidolon-darme-ssh.service")
data["ssh_feed"]=True;config.write_text(json.dumps(data)+"\n");os.chmod(config,0o644)
run(["systemd-analyze","verify","/etc/systemd/system/eidolon-darme-ssh.service","/etc/systemd/system/eidolon-darme.service"])
run(["systemctl","daemon-reload"])
run(["systemctl","enable","--now","eidolon-darme-ssh.service"])
run(["systemctl","restart","eidolon-darme.service"])
print("SSH collector installed; runtime checks required")
