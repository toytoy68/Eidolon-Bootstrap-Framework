# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : matmul-quant.py
# Description : Campagne isolee X399, voir README pour preconditions
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,time,os,json
b=Path('/srv/eidolon/ssd/work/backlog-20261120')
while not (b/'quality-budget0-results.json').exists():time.sleep(1)
env=dict(os.environ,LD_LIBRARY_PATH=str(b/'cuda129/lib'));out=[]
before=subprocess.check_output(['nvidia-smi','--query-gpu=index,power.limit','--format=csv,noheader,nounits'],text=True)
try:
 subprocess.run(['sudo','-n','nvidia-smi','-pl','200'],check=True)
 for version in ['v08','v1']:
  for gpu in ['CUDA0','CUDA1']:
   name='matmul-quant-'+version+'-'+gpu
   with (b/(name+'.log')).open('w') as log:
    try:r=subprocess.run([str(b/('build-cuda129-patched-'+version)/'bin/test-backend-ops'),'-b',gpu,'-o','MUL_MAT','-p','type_a=(q4_K|q2_0|f16)'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180);code=r.returncode
    except subprocess.TimeoutExpired:code='timeout'
   out.append({'name':name,'exit':code})

finally:
 for line in before.splitlines():
  i,p=line.split(',');subprocess.run(['sudo','-n','nvidia-smi','-i',i.strip(),'-pl',p.strip()])
 (b/'matmul-quant-done.json').write_text(json.dumps(out,indent=2))
