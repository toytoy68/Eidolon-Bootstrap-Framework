#!/usr/bin/python3
# Eidolon Core Technologies — bounded WALL-E network recovery after manual suspend.
from pathlib import Path
import subprocess,json,time
P=Path('/var/lib/wall-e-resume-network')
def command(args,timeout):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 return r.returncode
def main():
 d={'schema':'wall-e-resume-network/1','start_epoch':time.time(),'probes':[],'reconnect_attempted':False}
 try:
  reachable=False
  for attempt in range(3):
   row={host:command(['/usr/bin/ping','-n','-c','1','-W','2',host],4) for host in ['192.168.1.20','192.168.1.254']}
   d['probes'].append(row)
   if 0 in row.values():reachable=True;break
   if attempt<2:time.sleep(3)
  if not reachable:
   d['reconnect_attempted']=True
   d['reconnect_returncode']=command(['/usr/bin/nmcli','--wait','20','connection','up','uuid','bf0849bf-dbe3-4882-82ac-878034510cb3'],25)
  d['finished_epoch']=time.time()
 except Exception as e:d['error']=type(e).__name__
 tmp=P/'latest.json.tmp';tmp.write_text(json.dumps(d,indent=2));tmp.replace(P/'latest.json')
 with (P/'history.jsonl').open('a') as f:f.write(json.dumps(d)+'\n')
 return 1 if 'error' in d or d.get('reconnect_returncode',0)!=0 else 0
if __name__=='__main__':raise SystemExit(main())
