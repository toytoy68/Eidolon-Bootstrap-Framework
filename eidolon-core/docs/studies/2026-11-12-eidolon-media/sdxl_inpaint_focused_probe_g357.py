# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sdxl_inpaint_focused_probe_g357.py
# Description : Retouche contrôlée de checkpoints SDXL, hors ligne et sans entraînement
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G357. SDXL Inpainting: fixed masks, raw and composited outputs."""
import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time

GPU = 'GPU-a7716f02-4fbb-b36c-8b0c-2ec78c75be75'
SEEDS = (20261113, 20261114)

def baseline_plan(root):
    info=json.loads((root/'sdxl-inpaint-g357/inputs.json').read_text())
    rows=[]
    for case in info['cases']:
        for seed in SEEDS:
            rows.append(dict(case=case['case'],prompt=case['prompt'],target=case['target'],seed=seed,steps=20,cfg=8.0,strength=.99,negative_prompt='',width=1024,height=1024,mask_kind='local',condition='quality'))
    return [{**rows[0],'condition':'smoke','width':512,'height':512}]+rows+[{**rows[0],'condition':'repeat'},{**rows[2],'condition':'mask_empty','mask_kind':'empty'},{**rows[2],'condition':'mask_full','mask_kind':'full'}]


FOCUSED_PROMPTS={'hand': 'Studio photograph of one adult human hand with exactly five anatomically correct separated digits: one thumb and four long fingers. Open palm facing the camera, all fingers spread apart, fingertips upwards, wrist downwards, natural skin, plain grey background.', 'objects': 'Exactly two objects and nothing else: one red ceramic mug with one handle on the left, and one blue ceramic bowl without handles on the right, standing separately on a plain grey table. Empty space around the two objects. Studio product photograph.', 'katana': 'One empty black lacquer katana scabbard, a smooth curved sheath with a gold end cap and a gold opening, no handle and no blade, lying parallel beside the existing Japanese sword on grey fabric. Studio product photograph.', 'duo': 'The woman wears a RED silk kimono: bright red fabric on both sleeves, shoulders, torso and long skirt. Traditional Japanese floral pattern and a black obi belt. The existing face and hands stay unchanged. Photorealistic daylight.'}
def plan(root):
    return [{**row, "prompt":FOCUSED_PROMPTS[row["case"]],"prompt_variant":"focused"} for row in baseline_plan(root)[:10]]


def check_processes(lines, own_pid):
    # No other compute client is permitted, including on the other V100.
    for line in lines.splitlines():
        if line.strip() and int(line.strip()) != own_pid:
            raise RuntimeError('OTHER_GPU_CLIENT')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--mode', choices=['smoke','quality'], required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    a.output.mkdir(mode=0o700)
    import quality_probe as probe
    if os.environ.get('CUDA_VISIBLE_DEVICES') != GPU or os.environ.get('HF_HUB_OFFLINE') != '1':
        raise RuntimeError('GPU_OFFLINE_CONFIGURATION')
    def processes():
        return subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True, timeout=4)
    check_processes(processes(), os.getpid())
    metadata = json.loads(a.manifest.read_text())
    candidates=[('sdxl_inpaint',Path(metadata['path']),metadata['revision'])]
    for row in metadata['files']:
        with Path(row['path']).open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:raise RuntimeError('MODEL_HASH_MISMATCH')
    inputs=json.loads((a.root/'sdxl-inpaint-g357/inputs.json').read_text())
    for row in inputs['cases']:
        for suffix,key in [('source','copied_sha256'),('mask','mask_sha256')]:
            path=a.root/'sdxl-inpaint-g357/inputs'/f"{row['case']}-{suffix}.png"
            assert hashlib.sha256(path.read_bytes()).hexdigest()==row[key]
    import torch
    import numpy as np
    from PIL import Image
    from diffusers import StableDiffusionXLInpaintPipeline, EulerDiscreteScheduler
    if torch.cuda.device_count() != 1 or torch.cuda.get_device_capability(0) != (7, 0):
        raise RuntimeError('EXPECTED_SINGLE_VOLTA_GPU')
    torch.set_num_threads(4)
    torch.cuda.set_per_process_memory_fraction(.88)
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cudnn.benchmark = False
    samples, results, loads = [], [], []
    stop, unsafe = threading.Event(), threading.Event()
    phase = {'model': None, 'index': None}
    def monitor():
        with (a.output/'samples.jsonl').open('w', buffering=1) as log:
            while not stop.is_set():
                try:
                    row = probe.sample_once()
                    check_processes(processes(), os.getpid())
                    gpu = next(g for g in row['gpus'] if g['uuid'] == GPU)
                    if float(gpu['temperature.gpu']) >= 65 or float(gpu['temperature.memory']) >= 70:
                        raise RuntimeError('TEMPERATURE_LIMIT')
                    row.update(phase.copy())
                except Exception as exc:
                    row = {'error': type(exc).__name__, 'message': str(exc)}
                    unsafe.set()
                samples.append(row)
                log.write(json.dumps(row)+'\n')
                stop.wait(.5)
    def check():
        if unsafe.is_set():
            raise RuntimeError('RESOURCE_GUARD_STOP')
    def callback(pipe, step, timestep, kwargs):
        check()
        if not torch.isfinite(kwargs['latents']).all():
            raise RuntimeError('NONFINITE_LATENTS')
        return kwargs
    worker = threading.Thread(target=monitor)
    worker.start()
    try:
        probe.write_json(a.output/'manifest.json', {
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'gpu_uuid': GPU, 'runtime': {'torch': torch.__version__, 'diffusers': __import__('diffusers').__version__},
            'mode': a.mode, 'models': [{'id': n, 'path': str(f), 'revision': sha, 'plan': plan(a.root)} for n, f, sha in candidates],
            'scheduler': 'Euler author scheduler; 20 nominal steps, strength 0.99, expected 19 UNet calls', 'denoiser_dtype': 'FP16', 'vae': 'upcast FP32 for decode',
            'offline_required': True, 'training_or_promotion_allowed': False})
        for name, checkpoint, expected in candidates:
            phase.update(model=name, index=None)
            check()
            start = time.monotonic()
            pipe = StableDiffusionXLInpaintPipeline.from_pretrained(str(checkpoint),local_files_only=True,variant='fp16',torch_dtype=torch.float16,add_watermarker=False)
            assert pipe.unet.config.in_channels==9 and isinstance(pipe.scheduler,EulerDiscreteScheduler)
            pipe.enable_vae_tiling()
            pipe.to('cuda')
            pipe.set_progress_bar_config(disable=True)
            calls=[];decodes=[];encodes=[]
            pipe.unet.register_forward_pre_hook(lambda module,args:calls.append(1))
            def check_decode(module,args,output):
                value=output if isinstance(output,torch.Tensor) else output[0]
                if not torch.isfinite(value).all():raise RuntimeError('NONFINITE_PIXELS')
                decodes.append(1)
            pipe.vae.decoder.register_forward_hook(check_decode)
            def check_encode(module,args,output):
                if not torch.isfinite(output).all():raise RuntimeError('NONFINITE_VAE_ENCODER')
                encodes.append(1)
            pipe.vae.encoder.register_forward_hook(check_encode)

            load_seconds = time.monotonic()-start
            loads.append({'model': name, 'load_seconds': load_seconds})
            probe.write_json(a.output/'loads.json', loads)
            print(json.dumps({'loaded': name, 'seconds': load_seconds}), flush=True)
            folder = a.output/name
            folder.mkdir(mode=0o700)
            model_config={'scheduler':dict(pipe.scheduler.config),'vae':dict(pipe.vae.config),'vae_tiling':pipe.vae.use_tiling,'components':{key:{'device':str(next(module.parameters()).device),'dtype':str(next(module.parameters()).dtype)} for key,module in [('unet',pipe.unet),('text_encoder',pipe.text_encoder),('text_encoder_2',pipe.text_encoder_2),('vae',pipe.vae)]}}
            def json_config(value):
                if isinstance(value,float) and not math.isfinite(value):return str(value)
                if isinstance(value,dict):return {k:json_config(v) for k,v in value.items()}
                if isinstance(value,(tuple,list)):return [json_config(v) for v in value]
                return value
            probe.write_json(folder/'pipeline.json',json_config(model_config))
            for i, entry in enumerate(plan(a.root)):
                if a.mode=='smoke' and i!=0:continue
                if a.mode=='quality' and name=='sdxl_inpaint' and i==0:continue
                calls.clear();decodes.clear();encodes.clear()
                pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
                check()
                phase['index'] = i
                probe.write_json(folder/f'{i:02d}-intent.json', entry)
                source=Image.open(a.root/'sdxl-inpaint-g357/inputs'/f"{entry['case']}-source.png").convert('RGB').resize((entry['width'],entry['height']),Image.Resampling.LANCZOS)
                mask=Image.open(a.root/'sdxl-inpaint-g357/inputs'/f"{entry['case']}-mask.png").convert('L').resize(source.size,Image.Resampling.NEAREST)
                if entry['mask_kind']!='local':mask=Image.new('L',source.size,255 if entry['mask_kind']=='full' else 0)
                source.save(folder/f'{i:02d}-source.png');mask.save(folder/f'{i:02d}-mask.png')
                torch.cuda.reset_peak_memory_stats()
                begin = time.monotonic()
                with torch.inference_mode():
                    result = pipe(prompt=entry['prompt'], negative_prompt=entry['negative_prompt'], image=source, mask_image=mask,strength=entry['strength'],
                        width=entry['width'], height=entry['height'], original_size=(entry['height'],entry['width']), target_size=(entry['height'],entry['width']), crops_coords_top_left=(0,0), num_inference_steps=entry['steps'],
                        guidance_scale=entry['cfg'], generator=torch.Generator('cuda').manual_seed(entry['seed']),
                        callback_on_step_end=callback)
                torch.cuda.synchronize()
                duration = time.monotonic()-begin
                assert len(calls)==19 and decodes and encodes
                raw = result.images[0]
                image = Image.composite(raw,source,mask)
                raw_target=folder/f'{i:02d}-raw.png';target=folder/f'{i:02d}-{entry["case"]}.png'
                raw.save(raw_target);image.save(target)
                outside=np.asarray(mask)==0;src=np.asarray(source,dtype=np.int16);arr=np.asarray(raw,dtype=np.int16);comp=np.asarray(image,dtype=np.int16)
                delta=np.abs(arr-src);count=int(outside.sum())
                metrics={'outside_pixels':count,'raw_outside_mae':float(delta[outside].mean()) if count else None,'raw_outside_max':int(delta[outside].max()) if count else None,'raw_outside_changed_pixels':int(np.any(delta!=0,axis=2)[outside].sum()) if count else None,'composite_outside_max':int(np.abs(comp-src)[outside].max()) if count else None}
                if count:assert metrics['composite_outside_max']==0
                preview=image.copy();preview.thumbnail((768,768));preview.save(folder/f'{i:02d}-review.jpg',quality=85)
                record={'model':name,'index':i,**entry,'seconds':duration,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'raw_sha256':hashlib.sha256(raw_target.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((folder/f'{i:02d}-source.png').read_bytes()).hexdigest(),'mask_sha256':hashlib.sha256((folder/f'{i:02d}-mask.png').read_bytes()).hexdigest(),'mask_fraction':float((np.asarray(mask)>0).mean()),'unet_calls':len(calls),'decoder_calls':len(decodes),'encoder_calls':len(encodes),'timesteps_full':pipe.scheduler.timesteps.cpu().tolist(),'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'raw_pixel_sha256':hashlib.sha256(raw.tobytes()).hexdigest(),'preservation':metrics,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'visual':'NOT_REVIEWED'}
                results.append(record)
                probe.write_json(a.output/'results.json', results)
                print(json.dumps({'generated': name, 'index': i, 'case': entry['case'], 'seconds': duration}), flush=True)
            del pipe, result, image
            gc.collect()
            torch.cuda.empty_cache()
        check()
        repeats = {}
        for name, _, _ in candidates:
            subset = [r for r in results if r['model'] == name]
            repeats[name] = (next(x['pixel_sha256'] for x in subset if x['index']==1)==next(x['pixel_sha256'] for x in subset if x['index']==9)) if a.mode=='quality' else None
        probe.write_json(a.output/'completion.json', {'generated': len(results), 'repeat_same_pixels': repeats,
            'training_or_promotion_allowed': False, 'visual_acceptance': 'PENDING_REVIEW', 'raw_repeat_same_pixels': (next(r['raw_pixel_sha256'] for r in results if r['index']==1)==next(r['raw_pixel_sha256'] for r in results if r['index']==9)) if a.mode=='quality' else None})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json', {'error': type(exc).__name__, 'message': str(exc)[:2000]})
        raise
    finally:
        stop.set()
        worker.join()
        probe.write_json(a.output/'telemetry.json', probe.summarize(samples))
        probe.write_json(a.output/'telemetry-by-model.json', {
            name: probe.summarize([s for s in samples if s.get('model') == name]) for name, _, _ in candidates})


if __name__ == '__main__':
    main()
