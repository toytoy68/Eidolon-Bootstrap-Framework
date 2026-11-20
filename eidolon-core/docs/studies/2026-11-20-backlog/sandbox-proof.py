# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : sandbox-proof.py
# Description : Sonde isolee de validation du backlog
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,tempfile,json,http.server,threading,os,time
b=Path('/srv/eidolon/ssd/work/backlog-20261120')
root=Path(tempfile.mkdtemp(prefix='eidolon-sandbox-proof-'));root.chmod(0o700)
work=root/'allowed';work.mkdir();secret=root/'synthetic-private.txt';secret.write_text('SYNTHETIC-ONLY')
class H(http.server.BaseHTTPRequestHandler):
 received=[]
 def do_POST(self):self.received.append(self.path);self.send_response(200);self.end_headers()
 do_PUT=do_POST
 def log_message(self,*args):pass
server=http.server.HTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
inside="""import pathlib,json,socket,urllib.request,os
p=pathlib.Path('/work/legitimate.txt');p.write_text('authorized synthetic output')
r={'legitimate_write':p.read_text()=='authorized synthetic output','outside_private_visible':pathlib.Path(SECRET).exists()}
for method in ['POST','PUT']:
 try:
  urllib.request.urlopen(urllib.request.Request(URL,data=b'SYNTHETIC',method=method),timeout=2);r[method]='unexpected-success'
 except Exception as e:r[method]=type(e).__name__
try:socket.getaddrinfo('synthetic.invalid',80);r['dns']='unexpected-success'
except Exception as e:r['dns']=type(e).__name__
r['cap_eff']=[x for x in pathlib.Path('/proc/self/status').read_text().splitlines() if x.startswith('CapEff:')][0]
print(json.dumps(r))
""".replace('SECRET',repr(str(secret))).replace('URL',repr('http://127.0.0.1:'+str(server.server_port)+'/sink'))
args=['bwrap','--unshare-all','--new-session','--die-with-parent','--cap-drop','ALL','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(work),'/work','--chdir','/work','--clearenv','--setenv','PATH','/usr/bin:/bin','/usr/bin/python3','-c',inside]
r=subprocess.run(args,capture_output=True,text=True,timeout=30);server.shutdown()
result={'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'host_received_requests':H.received,'legitimate_host_file':(work/'legitimate.txt').exists(),'scope':'isolated synthetic bwrap capability proof; not DARME deployed integration'}
(b/'sandbox-proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
