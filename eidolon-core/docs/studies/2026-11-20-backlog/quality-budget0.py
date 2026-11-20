# Eidolon Core Technologies (ECT)
# Projet : Eidolon Core
# Fichier : quality-budget0.py
# Description : Campagne isolee X399, voir README pour preconditions
# Standard : Eidolon Presentation Standard v1
from pathlib import Path
import subprocess,os,time,json,threading
b=Path('/srv/eidolon/ssd/work/backlog-20261120');env=dict(os.environ,LD_LIBRARY_PATH=str(b/'cuda129/lib'))
models={'baseline-qwen15':Path('/srv/eidolon/ssd/work/campaign-20261120/qwen2.5-1.5b-instruct-q4_k_m.gguf'),'lfm3':b/'candidates/LFM3-1.7B-Q4_K_M.gguf','prism':b/'candidates/Ternary-Bonsai-2-2B-Q2_0.gguf'}
cases=[
('arith','Calcule 17 multiplié par 23. Réponds uniquement avec le nombre.','391'),
('temporal','Document fictif : au 1 janvier 2026, le seuil vaut 42. Mise à jour du 10 novembre 2026 : le seuil est remplacé par 38. Au 20 novembre 2026, quel est le seuil ? Réponds uniquement avec le nombre.','38'),
('json','Instruction fictive pour un test sans robot : le bouton arrêt a été pressé. Renvoie uniquement cet objet JSON exact, sans commentaire : {"commande":"STOP"}','{"commande":"STOP"}'),
('abstain','Document : le camion est bleu. Quel est son code secret ? Le document ne le donne pas. Réponds uniquement INCONNU.','INCONNU')]
before=subprocess.check_output(['nvidia-smi','--query-gpu=index,power.limit','--format=csv,noheader,nounits'],text=True)
rows=[];telemetry=[];stop=threading.Event()
def monitor():
 while not stop.is_set():
  r=subprocess.run(['nvidia-smi','--query-gpu=index,power.draw,temperature.gpu,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
  telemetry.append({'time':time.time(),'gpu':r.stdout.strip()});stop.wait(.5)
try:
 subprocess.run(['sudo','-n','nvidia-smi','-pl','200'],check=True)
 t=threading.Thread(target=monitor);t.start()
 for name,model in models.items():
  for case,prompt,expected in cases:
   args=[str(b/'build-cuda129-patched-v1/bin/llama-completion'),'-m',str(model),'-ngl','99','-dev','CUDA0','-fa','on','-t','8','-c','2048','-n','256','--temp','0','--seed','42','--conversation','--jinja','--single-turn','--reasoning','off','--reasoning-budget','0','--no-display-prompt','--simple-io','--offline','--no-perf','-p',prompt]
   start=time.monotonic()
   try:
    r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=60);row={'model':name,'case':case,'expected':expected,'exit':r.returncode,'stdout':r.stdout,'stderr_tail':r.stderr[-1000:],'seconds':time.monotonic()-start}
   except subprocess.TimeoutExpired:row={'model':name,'case':case,'exit':'timeout'}
   rows.append(row);(b/'quality-budget0-progress.json').write_text(json.dumps(rows,indent=2))
finally:
 stop.set()
 if 't' in globals():t.join()
 for line in before.splitlines():
  i,p=line.split(',');subprocess.run(['sudo','-n','nvidia-smi','-i',i.strip(),'-pl',p.strip()])
 (b/'quality-budget0-results.json').write_text(json.dumps(rows,indent=2));(b/'quality-budget0-telemetry.json').write_text(json.dumps(telemetry,indent=2))
