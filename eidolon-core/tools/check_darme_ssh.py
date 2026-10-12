# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : check_darme_ssh.py
# Description : Recette locale unique de refus SSH et acquittement de test
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import pathlib,tempfile,subprocess,socket,json,time,datetime,pwd,hashlib,sqlite3
probe_user="eidolon-darme-local-check"
try:
 pwd.getpwnam(probe_user)
 raise SystemExit("Existing test identity refused")
except KeyError:pass
started=datetime.datetime.now(datetime.timezone.utc)
with tempfile.NamedTemporaryFile(mode="w",prefix="darme-known-host-") as known:
 known.write("127.0.0.1 "+pathlib.Path("/etc/ssh/ssh_host_ed25519_key.pub").read_text());known.flush()
 result=subprocess.run(["ssh","-F","/dev/null","-T","-o","BatchMode=yes","-o","HostKeyAlgorithms=ssh-ed25519","-o","StrictHostKeyChecking=yes","-o","GlobalKnownHostsFile=/dev/null","-o","UserKnownHostsFile="+known.name,"-o","PubkeyAuthentication=no","-o","PasswordAuthentication=no","-o","KbdInteractiveAuthentication=no","-o","PreferredAuthentications=none","-o","ConnectTimeout=5",probe_user+"@127.0.0.1","true"],capture_output=True,timeout=7)
 assert result.returncode==255
def status():
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(2);s.connect("/run/eidolon-darme/status.sock");s.sendall(b"STATUS\n")
  return json.loads(s.recv(32768))
cursor_ids=[]
deadline=time.monotonic()+21
while time.monotonic()<deadline:
 logs=subprocess.run(["journalctl","-u","ssh.service","--since",started.isoformat(),"-n","30","--no-pager","-o","json"],capture_output=True,text=True,check=True)
 for line in logs.stdout.splitlines():
  row=json.loads(line)
  if probe_user in row.get("MESSAGE","") and row.get("MESSAGE","").startswith("Invalid user "):
   cursor_ids.append(hashlib.sha256(row["__CURSOR"].encode()).hexdigest())
 db=sqlite3.connect("file:/var/lib/eidolon-darme/journal.sqlite?mode=ro",uri=True)
 found=[i for i in set(cursor_ids) if db.execute("SELECT 1 FROM events WHERE id=?",(i,)).fetchone()]
 db.close()
 current=status()
 if found and current["badge"]=="red":break
 time.sleep(.25)
else:raise SystemExit("Local SSH event was not detected in time")
script='import sys;sys.path.insert(0,"/opt/eidolon-darme");from eidolon_core.darme_store import DarmeJournal;j=DarmeJournal("/var/lib/eidolon-darme/journal.sqlite");[j.acknowledge(i,"Codex authorized operator test","Controlled local SSH refusal; acceptance test") for i in '+repr(found)+'];j.close()'
subprocess.run(["runuser","-u","eidolon-darme","--","python3","-I","-c",script],check=True,capture_output=True)
print(json.dumps({"single_local_ssh_refusal":True,"red_badge_verified":True,"matching_events_durable":len(found),"test_events_acknowledged":True,"raw_auth_logs_published":False}))
