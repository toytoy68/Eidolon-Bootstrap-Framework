# Eidolon Core Technologies (ECT) - same-runtime packing speed comparison
from pathlib import Path
import subprocess,os,json,time
P=Path(__file__).resolve().parent;B=P.parent/'backlog-20261120'
env=dict(os.environ,LD_LIBRARY_PATH=str(B/'cuda129/lib'))
rows=[]
for fmt in ['PTQ1_0','PQ2_0','Q2_0']:
 model=(P/'prism-models'/('Ternary-Bonsai-2-2B-'+fmt+'.gguf')) if fmt!='Q2_0' else B/'candidates/Ternary-Bonsai-2-2B-Q2_0.gguf'
 for device in ['CUDA0','none']:
  args=[str(P/'prism-build/bin/llama-bench'),'-m',str(model),'-p','512','-n','128','-r','3','-t','8','-ngl','99' if device!='none' else '0','-dev',device,'-fa','on','-o','json']
  t=time.time();r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=600)
  (P/f'prism-perf-clean-{fmt}-{device}.log').write_text(r.stderr)
  try:result=json.loads(r.stdout)
  except Exception:result=r.stdout[-3000:]
  rows.append(dict(format=fmt,device=device,bytes=model.stat().st_size,returncode=r.returncode,seconds=time.time()-t,results=result))
  (P/'prism-perf-clean.json').write_text(json.dumps(rows,indent=2))
(P/'prism-perf-clean-status.json').write_text(json.dumps(dict(finished=True)))
