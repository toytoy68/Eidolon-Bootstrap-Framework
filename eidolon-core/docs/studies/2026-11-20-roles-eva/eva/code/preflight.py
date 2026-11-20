# Eidolon Core Technologies (ECT) - current-boot training preflight
from pathlib import Path
import json,subprocess,hashlib,time,re
P=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(8388608),b''):h.update(x)
 return h.hexdigest()
t=time.time();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
r=subprocess.run(['sudo','-n','memtester','4G','1'],stdout=(P/'memtester.log').open('w'),stderr=subprocess.STDOUT,timeout=1800)
assert r.returncode==0,'memtester failed'
checks={}
for n,v in json.loads((P/'source-manifest.json').read_text())['files'].items():
 checks[n]=[sha(P/'source-model'/n),sha(P/'source-model'/n)]
 assert checks[n]==[v['sha256']]*2,n
c=json.loads((P/'config.json').read_text())
parent=Path(c['parent_adapter'])/'adapter_model.safetensors';hs=[sha(parent),sha(parent)]
assert hs==['c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30']*2
for i in range(2):
 r=subprocess.run([str(P/'memory_copy_test')],capture_output=True,text=True,timeout=60)
 errs=[int(x) for x in re.findall(r'(?:source|destination)_errors=(\d+)',r.stdout)]
 assert r.returncode==0 and len(errs)==12 and not any(errs)
 (P/f'memory-copy-{i}.txt').write_text(r.stdout)
proof=dict(passed=True,memtester_passed=True,boot_id=boot,source_hashes=checks,adapter_hashes=hs,seconds=time.time()-t,epoch=time.time())
(P/'cpu-preflight.json').write_text(json.dumps(proof,indent=2))
r=subprocess.run([str(P/'venv/bin/python'),str(P/'self_check.py')],stdout=(P/'self-check.log').open('w'),stderr=subprocess.STDOUT,timeout=180)
assert r.returncode==0
names=[f.name for f in P.iterdir() if f.is_file() and f.suffix in ['.py','.json'] and f.name not in ['launch-manifest.json','cpu-preflight-status.json']]+['memory_copy_test']
(P/'launch-manifest.json').write_text(json.dumps({n:sha(P/n) for n in sorted(names)},indent=2))
(P/'cpu-preflight-status.json').write_text(json.dumps(dict(passed=True,seconds=time.time()-t)))
print('preflight passed',flush=True)
