# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : gpu-campaign.py
# Description : Campagne isolee X399, voir README pour preconditions
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,time,os,json,traceback
b=Path('/srv/eidolon/ssd/work/backlog-20261120');p=Path('/srv/eidolon/ssd/work/campaign-20261120')
deadline=time.monotonic()+3600
while not (b/'cuda129-patched-done.json').exists() or not (b/'kiri-bench-exit').exists():
 if time.monotonic()>deadline:raise TimeoutError('prerequisites incomplete')
 time.sleep(3)
env=dict(os.environ,LD_LIBRARY_PATH=str(b/'cuda129/lib'),OMP_NUM_THREADS='8')
results=[]
def call(label,args,timeout=600):
 start=time.monotonic()
 with (b/(label+'.out')).open('w') as out,(b/(label+'.err')).open('w') as err:
  try:code=subprocess.run(args,env=env,stdout=out,stderr=err,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code='timeout'
 result={'label':label,'exit':code,'seconds':time.monotonic()-start,'command':args};results.append(result)
 (b/'gpu-progress.json').write_text(json.dumps(results,indent=2))
 return code
before=subprocess.check_output(['nvidia-smi','--query-gpu=index,power.limit','--format=csv,noheader,nounits'],text=True)
(b/'gpu-before.txt').write_text(subprocess.check_output(['nvidia-smi','-q'],text=True))
try:
 subprocess.run(['sudo','-n','nvidia-smi','-pl','200'],check=True)
 for version in ['v08','v1']:
  call('backend-'+version,[str(b/('build-cuda129-patched-'+version)/'bin/test-backend-ops'),'-b','CUDA0','-o','ADD,RMS_NORM,SOFT_MAX'],300)
 baseline=p/'qwen2.5-1.5b-instruct-q4_k_m.gguf'
 for i,version in enumerate(['v08','v1','v1','v08','v1','v08','v08','v1']):
  args=[str(b/('build-cuda129-patched-'+version)/'bin/llama-bench'),'-m',str(baseline),'-p','512','-n','128','-r','3','-t','8','-ngl','99','-dev','CUDA0','-fa','on','-o','json']
  call('gpu-ab-'+str(i)+'-'+version,args,300)
 bench=str(b/'build-cuda129-patched-v1/bin/llama-bench')
 for name,file in [('lfm3',b/'candidates/LFM3-1.7B-Q4_K_M.gguf'),('prism',b/'candidates/Ternary-Bonsai-2-2B-Q2_0.gguf')]:
  call('gpu-'+name,[bench,'-m',str(file),'-p','512','-n','128','-r','5','-t','8','-ngl','99','-dev','CUDA0','-fa','on','-o','json'],300)
 moe='/srv/eidolon/models/ollama/blobs/sha256-58574f2e94b99fb9e4391408b57e5aeaaaec10f6384e9a699fc2cb43a5c8eabf'
 for name,extra in [('dual',['-dev','CUDA0/CUDA1','-sm','layer','-ts','1/1']),('expertscpu',['-dev','CUDA0','-ncmoe','48'])]:
  call('gpu-moe-'+name,[bench,'-m',moe,'-p','512','-n','128','-r','3','-t','8','-ngl','99','-fa','on','-o','json']+extra,600)
 call('build-completion',['cmake','--build',str(b/'build-cuda129-patched-v1'),'--target','llama-completion','-j','4'],300)
except Exception as e:results.append({'exception':repr(e)});traceback.print_exc()
finally:
 for row in before.splitlines():
  i,power=row.split(',');subprocess.run(['sudo','-n','nvidia-smi','-i',i.strip(),'-pl',power.strip()])
 (b/'gpu-after.txt').write_text(subprocess.check_output(['nvidia-smi','-q'],text=True))
 (b/'gpu-done.json').write_text(json.dumps(results,indent=2))
