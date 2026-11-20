# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : live_check.py
# Description : Controle RAM/source avant chaque chargement E4a
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from common import P,read,save,sha
from pathlib import Path
import os,subprocess,re,time
OUT=Path(os.environ['EVA_OUTPUT']);BOOT=read(P/'config.json')['boot_id']
def progress(stage,**kw):save(OUT/'progress-check.json',dict(stage=stage,epoch=time.time(),**kw))
proof=read(P/'cpu-preflight.json')
assert proof['passed'] and proof['memtester_passed'] and proof['boot_id']==BOOT==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
k=subprocess.check_output(['journalctl','-k','-b','--no-pager'],text=True)
assert not re.search(r'Oops:|\bBUG:|Hardware Error|NVRM: Xid|Machine check|memory failure|hard LOCKUP|soft lockup',k,re.I),'Current boot kernel fault'
copies=[]
for i in range(2):
 progress('memory_copy',pass_index=i)
 r=subprocess.run([str(P/'memory_copy_test')],capture_output=True,text=True,timeout=40)
 assert r.returncode==0
 errors=[int(x) for x in re.findall(r'(?:source|destination)_errors=(\d+)',r.stdout)]
 assert len(errors)==12 and not any(errors),r.stdout
 copies.append(r.stdout);save(OUT/f'copy-{i}.json',dict(stdout=r.stdout,errors=errors,passed=True))
checks={}
for n,v in read(P/'source-manifest.json')['files'].items():
 hs=[]
 for i in range(2):progress('source_hash',file=n,pass_index=i);hs.append(sha(P/'source-model'/n))
 assert hs==[v['sha256']]*2,n
 checks[n]=hs
parent=Path(read(P/'config.json')['parent_adapter'])/'adapter_model.safetensors';hs=[sha(parent),sha(parent)]
assert hs==['c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30']*2
for n,h in read(P/'launch-manifest.json').items():assert sha(P/n)==h,n
assert not re.search(r'Oops:|\bBUG:|Hardware Error|NVRM: Xid',subprocess.check_output(['journalctl','-k','-b','--no-pager'],text=True))
save(OUT/'integrity-proof.json',dict(passed=True,boot_id=BOOT,source_hashes=checks,copies=copies,parent_hashes=hs,initial_cpu_proof_sha256=sha(P/'cpu-preflight.json'),epoch=time.time()))
progress('finished')
