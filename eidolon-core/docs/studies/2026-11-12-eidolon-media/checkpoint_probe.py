# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : checkpoint_probe.py
# Description : Comparaison contrôlée de checkpoints SDXL, hors ligne et sans entraînement
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G333. Same prompts, seeds, runtime and settings; model weights are the variable.

Requires exclusive GPU access and a systemd network sandbox. A second RealVis
condition changes steps only, separately from the shared 30-step comparison.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

GPU = 'GPU-a7716f02-4fbb-b36c-8b0c-2ec78c75be75'
PROMPTS = {
    'hand': 'Studio photograph of one adult human hand, open palm facing the camera, five separated digits, wrist at the bottom, fingertips upwards, grey background.',
    'objects': 'Studio photograph of exactly two objects on a grey table: one red ceramic mug on the left and one blue ceramic bowl on the right. Both objects fully visible. Plain grey background.',
    'katana': 'Studio product photograph of one luxury Japanese katana and its black lacquer scabbard lying separately side by side on grey fabric. Entire curved blade and entire scabbard visible, gold fittings, top-down view.',
}
SEEDS = (20261113, 20261114)


def plan(model):
    if model not in ('sdxl', 'realvis', 'juggernaut'):
        raise ValueError('UNKNOWN_MODEL')
    rows = [dict(condition='common30', case=case, prompt=prompt, seed=seed,
                 steps=30, cfg=5, negative_prompt='', width=1024, height=1024)
            for case, prompt in PROMPTS.items() for seed in SEEDS]
    rows.append({**rows[0], 'condition': 'repeat30'})
    if model == 'realvis':
        rows.extend({**r, 'condition': 'author50', 'steps': 50} for r in rows[:6])
    return rows


def check_processes(lines, own_pid):
    # No other compute client is permitted, including on the other V100.
    for line in lines.splitlines():
        if line.strip() and int(line.strip()) != own_pid:
            raise RuntimeError('OTHER_GPU_CLIENT')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
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
    rows = json.loads(a.manifest.read_text())
    candidates = [('sdxl', a.root/'engine/models/checkpoints/sd_xl_base_1.0.safetensors', probe.MODEL_SHA),
                  ('realvis', a.models/rows[0]['name'], rows[0]['sha256']),
                  ('juggernaut', a.models/rows[1]['name'], rows[1]['sha256'])]
    for name, path, expected in candidates:
        with path.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != expected:
                raise RuntimeError('CHECKPOINT_HASH_'+name)
    import torch
    from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
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
            'models': [{'id': n, 'path': str(f), 'sha256': sha, 'plan': plan(n)} for n, f, sha in candidates],
            'scheduler': 'DPM++ 2M Karras', 'denoiser_dtype': 'FP16', 'vae': 'upcast FP32 for decode',
            'offline_required': True, 'training_or_promotion_allowed': False})
        for name, checkpoint, expected in candidates:
            phase.update(model=name, index=None)
            check()
            start = time.monotonic()
            pipe = StableDiffusionXLPipeline.from_single_file(str(checkpoint),
                config=str(a.root/'preference-lab/sdxl-config'), local_files_only=True,
                torch_dtype=torch.float16, add_watermarker=False)
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config,
                algorithm_type='dpmsolver++', use_karras_sigmas=True, solver_order=2)
            pipe.enable_vae_tiling()
            pipe.to('cuda')
            pipe.set_progress_bar_config(disable=True)
            load_seconds = time.monotonic()-start
            loads.append({'model': name, 'load_seconds': load_seconds})
            probe.write_json(a.output/'loads.json', loads)
            print(json.dumps({'loaded': name, 'seconds': load_seconds}), flush=True)
            folder = a.output/name
            folder.mkdir(mode=0o700)
            for i, entry in enumerate(plan(name)):
                check()
                phase['index'] = i
                probe.write_json(folder/f'{i:02d}-intent.json', entry)
                torch.cuda.reset_peak_memory_stats()
                begin = time.monotonic()
                with torch.inference_mode():
                    result = pipe(prompt=entry['prompt'], negative_prompt=entry['negative_prompt'],
                        width=entry['width'], height=entry['height'], num_inference_steps=entry['steps'],
                        guidance_scale=entry['cfg'], generator=torch.Generator('cuda').manual_seed(entry['seed']),
                        callback_on_step_end=callback)
                torch.cuda.synchronize()
                duration = time.monotonic()-begin
                image = result.images[0]
                target = folder/f'{i:02d}-{entry["case"]}.png'
                image.save(target)
                preview = image.copy()
                preview.thumbnail((768, 768))
                preview.save(folder/f'{i:02d}-review.jpg', quality=85)
                record = {'model': name, 'index': i, **entry, 'seconds': duration,
                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                    'pixel_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                    'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                    'peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'visual': 'NOT_REVIEWED'}
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
            repeats[name] = subset[0]['pixel_sha256'] == subset[6]['pixel_sha256']
        probe.write_json(a.output/'completion.json', {'generated': len(results), 'repeat_same_pixels': repeats,
            'training_or_promotion_allowed': False, 'visual_acceptance': 'PENDING_REVIEW'})
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
