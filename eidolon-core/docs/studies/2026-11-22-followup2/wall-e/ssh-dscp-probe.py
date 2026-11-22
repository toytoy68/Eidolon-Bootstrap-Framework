from pathlib import Path
import socket,json,time,subprocess
out={'epoch':time.time(),'target':'192.168.1.105:22','probes':[],'ssh_defaults':subprocess.check_output(['ssh','-G','wall-e-projet@192.168.1.105'],text=True,stderr=subprocess.DEVNULL).splitlines()}
out['ssh_defaults']=[s for s in out['ssh_defaults'] if s.startswith(('hostname ','port ','ipqos '))]
for repetition in range(3):
 for tos in [0,32,184,72]:
  s=socket.socket();s.settimeout(2);s.setsockopt(socket.IPPROTO_IP,socket.IP_TOS,tos);row={'repetition':repetition,'tos':tos}
  try:s.connect(('192.168.1.105',22));row['banner']=s.recv(100).decode().strip()
  except OSError as e:row['error']=type(e).__name__
  finally:s.close()
  out['probes'].append(row)
p=Path('/srv/eidolon/ssd/work/followup2-20261122/wall-e/ssh-dscp-proof.json');p.write_text(json.dumps(out,indent=2));print(json.dumps(out))
