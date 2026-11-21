# Eidolon Core Technologies (ECT) - isolated Prism build, pinned source
from pathlib import Path
import subprocess,os,json
P=Path(__file__).resolve().parent;B=P.parent/'backlog-20261120'
env=dict(os.environ,PATH=str(B/'cuda129/bin')+':'+os.environ['PATH'],LD_LIBRARY_PATH=str(B/'cuda129/lib'))
commands=[
['cmake','-S',str(P/'prism-source'),'-B',str(P/'prism-build'),'-DGGML_CUDA=ON','-DCMAKE_CUDA_ARCHITECTURES=70','-DCMAKE_CUDA_COMPILER='+str(B/'cuda129/bin/nvcc'),'-DLLAMA_USE_PREBUILT_UI=OFF','-DLLAMA_BUILD_UI=OFF','-DLLAMA_BUILD_SERVER=ON','-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_EXAMPLES=OFF','-DCMAKE_BUILD_TYPE=Release'],
['cmake','--build',str(P/'prism-build'),'--target','llama-server','llama-bench','-j','10']]
for c in commands:subprocess.run(c,env=env,check=True)
(P/'prism-build-status.json').write_text(json.dumps(dict(passed=True)))
