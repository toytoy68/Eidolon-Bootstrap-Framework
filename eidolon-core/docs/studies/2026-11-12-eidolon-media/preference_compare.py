# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : preference_compare.py
# Description : Comparaison avant/après LoRA sur trois prompts tenus à part
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Same Diffusers engine on both sides; no claim of equivalence to Comfy output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import quality_probe as probe
from eidolon_core.media_feedback import FeedbackLedger

PROMPTS = [
    'Photograph of two adults standing in front of a Japanese castle. A samurai in black armour on the left and a woman in a red kimono on the right. Both visible from head to foot, daylight.',
    'Photograph of a stone bridge with three arches crossing a river, a medieval town behind it, clear daylight, wide view.',
    'Studio photograph of one metal bicycle on a grey background, side view, two wheels, complete frame and chain visible.',
]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--pilot',type=Path,required=True);p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--engine-pid',type=int,required=True)
    a=p.parse_args();os.umask(0o077);a.output.mkdir(mode=0o700)
    import torch
    from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
    data=json.loads(a.dataset.read_text());result=json.loads((a.pilot/'result.json').read_text())
    book=FeedbackLedger(a.dataset.parent/'ledger')
    if book.snapshot()['ledger_hash']!=result['ledger_hash']:raise RuntimeError('REVIEWS_CHANGED')
    if set(PROMPTS)&{r['prompt'] for r in data['records']}:raise RuntimeError('HOLDOUT_LEAKAGE')
    adapter=a.pilot/'candidate/pytorch_lora_weights.safetensors'
    if hashlib.sha256(adapter.read_bytes()).hexdigest()!=result['candidate_sha256']:raise RuntimeError('ADAPTER_HASH_MISMATCH')
    client=probe.LocalGenerationClient('http://127.0.0.1:8190',(a.root/'token').read_text().strip())
    opener=probe.urllib.request.build_opener(probe.urllib.request.ProxyHandler({}))
    probe.assert_idle(client,opener);probe.free_cache(opener)
    if not probe.gpu_probe(probe.GPU,a.engine_pid)['ready']:raise RuntimeError('GPU_BUSY')
    model=a.root/'engine/models/checkpoints/sd_xl_base_1.0.safetensors'
    with model.open('rb') as f:base_sha=hashlib.file_digest(f,'sha256').hexdigest()
    if base_sha!=probe.MODEL_SHA:raise RuntimeError('BASE_HASH_MISMATCH')
    torch.set_num_threads(4);torch.manual_seed(20261112)
    if torch.cuda.device_count()!=1 or torch.cuda.get_device_capability(0)!=(7,0):raise RuntimeError('EXPECTED_SINGLE_VOLTA_GPU')
    torch.cuda.set_per_process_memory_fraction(.85)
    samples=[];stop=threading.Event();unsafe=threading.Event()
    def monitor():
        with (a.output/'samples.jsonl').open('w',buffering=1) as log:
            while not stop.is_set():
                try:
                    row=probe.sample_once()
                    procs=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=4).splitlines()
                    gpu=next(g for g in row['gpus'] if g['uuid']==probe.GPU)
                    if any(int(x.strip()) not in (os.getpid(),a.engine_pid) for x in procs if x.strip()) or float(gpu['temperature.gpu'])>=65 or float(gpu['temperature.memory'])>=70:
                        unsafe.set();row['guard']='RESOURCE_CONFLICT'
                except Exception as exc:row={'error':type(exc).__name__};unsafe.set()
                samples.append(row);log.write(json.dumps(row)+'\n');stop.wait(.5)
    def check(*args):
        if unsafe.is_set():raise RuntimeError('RESOURCE_GUARD_STOP')
        if book.snapshot()['ledger_hash']!=result['ledger_hash']:raise RuntimeError('REVIEWS_CHANGED')
    worker=threading.Thread(target=monitor);worker.start()
    try:
        manifest={'prompts':PROMPTS,'seed':155921,'steps':30,'cfg':6,'width':1024,'height':1024,
                  'base_sha256':base_sha,'candidate_sha256':result['candidate_sha256'],
                  'ledger_hash':result['ledger_hash'],'promotion_allowed':False,
                  'scope':'three unseen prompts, one seed each; smoke comparison only',
                  'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        probe.write_json(a.output/'manifest.json',manifest)
        pipe=StableDiffusionXLPipeline.from_single_file(str(model),
            config=str(a.root/'preference-lab/sdxl-config'),local_files_only=True,
            torch_dtype=torch.float16,add_watermarker=False)
        pipe.scheduler=DPMSolverMultistepScheduler.from_config(pipe.scheduler.config,
            algorithm_type='dpmsolver++',use_karras_sigmas=True)
        pipe.enable_attention_slicing('max');pipe.enable_vae_tiling();pipe.set_progress_bar_config(disable=True)
        pipe.to('cuda');records=[]
        for condition in ('base','candidate'):
            if condition=='candidate':
                pipe.load_lora_weights(str(adapter.parent),weight_name=adapter.name,local_files_only=True)
            for i,prompt in enumerate(PROMPTS):
                check();started=time.monotonic()
                image=pipe(prompt=prompt,negative_prompt='blurry, distorted, text, watermark',
                    width=1024,height=1024,num_inference_steps=30,guidance_scale=6,
                    generator=torch.Generator(device='cuda').manual_seed(155921),
                    callback=check,callback_steps=1).images[0]
                path=a.output/f'{condition}-{i}.png';image.save(path)
                record={'condition':condition,'case':i,'seconds_wall':time.monotonic()-started,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'visual':'NOT_REVIEWED'}
                records.append(record);probe.write_json(a.output/'results.json',records)
                print(json.dumps(record),flush=True)
        check();probe.write_json(a.output/'completion.json',{'generated':len(records),'promotion_allowed':False})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json',{'error':type(exc).__name__,'message':str(exc)[:1000]});raise
    finally:
        stop.set();worker.join();probe.write_json(a.output/'telemetry.json',probe.summarize(samples))

if __name__=='__main__':main()
