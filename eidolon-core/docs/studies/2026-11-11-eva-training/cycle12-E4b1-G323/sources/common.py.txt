# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : common.py
# Description : Ecritures atomiques et preuves E4a
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,os,hashlib,time,re
P=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(exist_ok=True,parents=True);tmp=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
 with tmp.open('w') as f:json.dump(x,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p);fd=os.open(p.parent,os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def item_path(out,stage,candidate,ident):
 assert re.fullmatch(r'[A-Za-z0-9+_.-]+',ident)
 return Path(out)/'items'/(stage+'--'+candidate+'--'+ident+'.json')
