# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : check_darme_service.py
# Description : Installation ou recette du service passif DARME
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json, pathlib, socket, subprocess, time, os, shutil, sys
unit="eidolon-darme-acceptance.service"
root=pathlib.Path("/run")
config=root/"eidolon-darme-acceptance-config.json"
probe_unit = "eidolon-core-api.service" if len(sys.argv)>1 and sys.argv[1]=="memory" else "eidolon-memory-bridge.service"
config.write_text(json.dumps({"units":[probe_unit],"interval":5}))
launcher=root/"eidolon-darme-acceptance-launch.py"
launcher.write_text("""import sys,socket,json,os
from pathlib import Path
sys.path.insert(0,"/opt/eidolon-darme")
checks={}
try:
 s=socket.socket(socket.AF_INET);s.close();checks["ip_socket_denied"]=False
except OSError: checks["ip_socket_denied"]=True
try:
 Path("/etc/eidolon-darme-acceptance-write").write_text("unexpected")
 checks["system_write_denied"]=False
except OSError: checks["system_write_denied"]=True
checks["nonroot"]=os.getuid()!=0
Path("/run/eidolon-darme-acceptance/isolation.json").write_text(json.dumps(checks))
from eidolon_core.darme_service import main
main()
""")
content=pathlib.Path("/etc/systemd/system/eidolon-darme.service").read_text()
content=content.replace("/opt/eidolon-darme/launch.py",str(launcher)).replace("/etc/eidolon-darme/config.json",str(config)).replace("/var/lib/eidolon-darme","/var/lib/eidolon-darme-acceptance").replace("/run/eidolon-darme ","/run/eidolon-darme-acceptance ").replace("--runtime /run/eidolon-darme\n","--runtime /run/eidolon-darme-acceptance\n").replace("StateDirectory=eidolon-darme\n","StateDirectory=eidolon-darme-acceptance\n").replace("RuntimeDirectory=eidolon-darme\n","RuntimeDirectory=eidolon-darme-acceptance\n")
(root/"systemd/system"/unit).write_text(content)
def command(*args): subprocess.run(args,check=True,capture_output=True)
def request(payload=b"STATUS\n"):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(2);s.connect("/run/eidolon-darme-acceptance/status.sock");s.sendall(payload)
  return json.loads(s.recv(16384))
def ready():
 for _ in range(30):
  try: return request()
  except (OSError,ValueError): time.sleep(.1)
 raise RuntimeError("endpoint unavailable")
try:
 command("systemctl","daemon-reload");command("systemctl","start",unit)
 first=ready()
 assert first["badge"]=="red" and first["unacknowledged_alerts"]==1
 assert request(b"EXECUTE id\n")=={"error":"read-only protocol"}
 command("systemctl","restart",unit)
 second=ready()
 assert second["unacknowledged_alerts"]==1 and second["badge"]=="red"
 checks=json.loads(pathlib.Path("/run/eidolon-darme-acceptance/isolation.json").read_text())
 assert all(checks.values())
 denied=subprocess.run(["runuser","-u","nobody","--","python3","-c",'import socket;s=socket.socket(socket.AF_UNIX);s.connect("/run/eidolon-darme-acceptance/status.sock")'],capture_output=True)
 assert denied.returncode!=0 and b"PermissionError" in denied.stderr
 checks.update(alert_detected=True,restart_preserves_one_alert=True,mutation_protocol_refused=True,unauthorized_socket_denied=True)
 print(json.dumps(checks))
finally:
 subprocess.run(["systemctl","stop",unit],capture_output=True)
 (root/"systemd/system"/unit).unlink(missing_ok=True);config.unlink(missing_ok=True);launcher.unlink(missing_ok=True)
 subprocess.run(["systemctl","daemon-reload"],capture_output=True)
 shutil.rmtree("/var/lib/eidolon-darme-acceptance",ignore_errors=True)
