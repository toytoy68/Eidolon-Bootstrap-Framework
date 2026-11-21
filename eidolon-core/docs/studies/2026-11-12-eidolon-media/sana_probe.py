# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sana_probe.py
# Description : Qualification locale Sana FP16 sur Volta, encodeur CPU FP32
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G334: bounded offline research probe, no training or production changes."""
import argparse
import gc
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from checkpoint_probe import GPU, PROMPTS, check_processes

CASES = {**PROMPTS, 'duo': 'Photograph of two adults standing in front of a Japanese castle. A samurai in black armour on the left and a woman in a red kimono on the right. Both visible from head to foot, daylight.'}


def plan():
    rows = [dict(case='hand', seed=20261113, width=512, height=512, condition='smoke')]
    rows.extend(dict(case=c, seed=s, width=1024, height=1024, condition='native')
                for c in CASES for s in (20261113, 20261114))
    rows.append({**rows[1], 'condition': 'repeat'})
    rows.append(dict(case='duo', seed=20261113, width=1024, height=576, condition='screen16x9'))
    rows.append(dict(case='duo', seed=20261113, width=768, height=576, condition='screen4x3'))
    return [{**r, 'prompt': CASES[r['case']], 'steps': 20, 'cfg': 4.5, 'negative_prompt': ''} for r in rows]


def pad_screen(image):
    from PIL import Image
    if image.size != (768, 576):
        raise ValueError('EXPECTED_768x576')
    canvas = Image.new('RGB', (1024, 576), (0, 0, 0))
    canvas.paste(image, (128, 0))
    return canvas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    a.output.mkdir(mode=0o700)
    import quality_probe as probe
    if os.environ.get('CUDA_VISIBLE_DEVICES') != GPU or os.environ.get('HF_HUB_OFFLINE') != '1':
        raise RuntimeError('OFFLINE_GPU_CONFIGURATION')
    def check_clients():
        raw = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True, timeout=4)
        check_processes(raw, os.getpid())
    check_clients()
    manifest = json.loads(a.manifest.read_text())
    root = Path(manifest['root'])
    for row in manifest['weights'] + manifest['metadata']:
        f = root/row['path']
        with f.open('rb') as stream:
            if f.stat().st_size != row['bytes'] or hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise RuntimeError('FILE_HASH_'+row['path'])
    import torch
    import numpy as np
    from PIL import Image
    from diffusers import SanaPipeline, SanaTransformer2DModel, AutoencoderDC, DPMSolverMultistepScheduler
    from transformers import Gemma2Model, GemmaTokenizerFast
    if torch.cuda.device_count() != 1 or torch.cuda.get_device_capability(0) != (7, 0):
        raise RuntimeError('EXPECTED_SINGLE_VOLTA')
    torch.set_num_threads(4)
    torch.cuda.set_per_process_memory_fraction(.88)
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cudnn.benchmark = False
    samples, results = [], []
    stop, unsafe = threading.Event(), threading.Event()
    phase = {'phase': 'load', 'index': None}
    def monitor():
        with (a.output/'samples.jsonl').open('w', buffering=1) as log:
            while not stop.is_set():
                try:
                    s = probe.sample_once()
                    check_clients()
                    g = next(g for g in s['gpus'] if g['uuid'] == GPU)
                    if float(g['temperature.gpu']) >= 65 or float(g['temperature.memory']) >= 70:
                        raise RuntimeError('TEMPERATURE_LIMIT')
                    s.update(phase.copy())
                except Exception as exc:
                    s = {'error': type(exc).__name__, 'message': str(exc)}
                    unsafe.set()
                samples.append(s)
                log.write(json.dumps(s)+'\n')
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
        start = time.monotonic()
        encoder = Gemma2Model.from_pretrained(root/'text_encoder', torch_dtype=torch.float32,
                    local_files_only=True, attn_implementation='eager', use_safetensors=True).eval()
        tokenizer = GemmaTokenizerFast.from_pretrained(root/'tokenizer', local_files_only=True)
        transformer = SanaTransformer2DModel.from_pretrained(root/'transformer', variant='fp16',
                    torch_dtype=torch.float16, local_files_only=True, use_safetensors=True).eval()
        vae = AutoencoderDC.from_pretrained(root/'vae', variant='fp16', torch_dtype=torch.float32,
                    local_files_only=True, use_safetensors=True).eval()
        scheduler = DPMSolverMultistepScheduler.from_pretrained(root/'scheduler', local_files_only=True)
        pipe = SanaPipeline(text_encoder=encoder, tokenizer=tokenizer, vae=vae,
                            transformer=transformer, scheduler=scheduler)
        load_seconds = time.monotonic()-start
        defaults = inspect.signature(SanaPipeline.__call__).parameters['complex_human_instruction'].default
        encodings = {}
        phase['phase'] = 'encode_cpu'
        for case, prompt in CASES.items():
            check()
            begin = time.monotonic()
            with torch.inference_mode():
                embeds = pipe.encode_prompt(prompt, device=torch.device('cpu'), clean_caption=False,
                    complex_human_instruction=defaults)
            for x in embeds:
                if not torch.isfinite(x).all():
                    raise RuntimeError('NONFINITE_ENCODING')
            encodings[case] = {'tensors': embeds, 'seconds': time.monotonic()-begin}
            print(json.dumps({'encoded': case, 'seconds': encodings[case]['seconds']}), flush=True)
        pipe.text_encoder = None
        # Sana 0.32.2 still sets tokenizer.padding_side with cached embeddings.
        # Keep this lightweight object while releasing the large text model.
        del encoder, tokenizer
        gc.collect()
        start = time.monotonic()
        pipe.to('cuda')
        # AutoencoderDC 0.32.2 exposes tiling methods but raises NotImplementedError.
        pipe.vae.disable_tiling()
        pipe.set_progress_bar_config(disable=True)
        transfer_seconds = time.monotonic()-start
        proof = {'plan': plan(), 'source': manifest, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'torch': torch.__version__, 'diffusers': __import__('diffusers').__version__, 'transformers': __import__('transformers').__version__,
            'cpu_load_seconds': load_seconds, 'gpu_transfer_seconds': transfer_seconds,
            'encoding_seconds': {k:v['seconds'] for k,v in encodings.items()}, 'text_encoder': 'CPU FP32 eager',
            'transformer': 'GPU0 FP16', 'vae': 'GPU0 FP32 full decode', 'resolution_binning': False,
            'prompt_instruction': defaults, 'clean_caption': False,
            'scheduler': {k: str(v) if isinstance(v, float) and not np.isfinite(v) else v for k,v in scheduler.config.items()},
            'training_allowed': False, 'offline_required': True}
        probe.write_json(a.output/'manifest.json', proof)
        phase['phase'] = 'generate'
        for i, row in enumerate(plan()):
            phase['index'] = i
            check()
            probe.write_json(a.output/f'{i:02d}-intent.json', row)
            embeds = {k:v.to('cuda') for k,v in zip(('prompt_embeds','prompt_attention_mask','negative_prompt_embeds','negative_prompt_attention_mask'), encodings[row['case']]['tensors'])}
            torch.cuda.reset_peak_memory_stats()
            begin = time.monotonic()
            with torch.inference_mode():
                latents = pipe(**embeds, negative_prompt=None, width=row['width'], height=row['height'],
                    num_inference_steps=row['steps'], guidance_scale=row['cfg'],
                    use_resolution_binning=False, output_type='latent', callback_on_step_end=callback,
                    generator=torch.Generator('cuda').manual_seed(row['seed'])).images
                decoded = pipe.vae.decode(latents.float()/pipe.vae.config.scaling_factor, return_dict=False)[0]
                if not torch.isfinite(decoded).all():
                    raise RuntimeError('NONFINITE_DECODE')
                array = pipe.image_processor.postprocess(decoded, output_type='np')[0]
            torch.cuda.synchronize()
            seconds = time.monotonic()-begin
            if not np.isfinite(array).all():
                raise RuntimeError('NONFINITE_PIXELS')
            im = Image.fromarray((array*255).round().astype('uint8'))
            if im.size != (row['width'], row['height']):
                raise RuntimeError('OUTPUT_DIMENSIONS')
            target = a.output/f'{i:02d}-{row["case"]}.png'
            im.save(target)
            preview = im.copy(); preview.thumbnail((768,768)); preview.save(a.output/f'{i:02d}-review.jpg', quality=85)
            record = {**row, 'index': i, 'seconds_gpu_decode': seconds, 'encoding_seconds_cached': encodings[row['case']]['seconds'],
                'peak_allocated_bytes': torch.cuda.max_memory_allocated(), 'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                'png_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'pixel_sha256': hashlib.sha256(im.tobytes()).hexdigest(),
                'pixel_std_float01': float(array.std()), 'visual': 'NOT_REVIEWED'}
            if row['condition'] == 'screen4x3':
                padded = pad_screen(im); f=a.output/'11-duo-padded16x9.png'; padded.save(f)
                padded.thumbnail((1024,576)); padded.save(a.output/'11-padded-review.jpg', quality=85)
                record['padded_sha256'] = hashlib.sha256(f.read_bytes()).hexdigest()
            results.append(record)
            probe.write_json(a.output/'results.json', results)
            print(json.dumps({'generated': i, 'seconds': seconds, 'case': row['case']}), flush=True)
            del decoded, latents, array, embeds
        check()
        probe.write_json(a.output/'completion.json', {'generated': len(results),
            'repeat_same_pixels': results[1]['pixel_sha256']==results[9]['pixel_sha256'],
            'visual_acceptance': 'PENDING_REVIEW', 'training_allowed': False})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json', {'error': type(exc).__name__, 'message': str(exc)[:2000]})
        raise
    finally:
        stop.set(); worker.join()
        probe.write_json(a.output/'telemetry.json', probe.summarize(samples))


if __name__ == '__main__':
    main()
