# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : flux_dev_probe.py
# Description : Essai FLUX dev réellement réparti sur deux V100, hors production
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Requires an offline systemd sandbox, verified files and two idle V100s.

Text encoders run on CPU in FP32. All denoiser parameters remain on two GPUs
in FP16. No quantization, no denoiser CPU offload and no custom CUDA kernel.
"""
import argparse
from collections import Counter
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

GPUS = ('GPU-a7716f02-4fbb-b36c-8b0c-2ec78c75be75',
        'GPU-c9d9173f-6303-6998-7a60-a379b9a0d60b')
CASES = {
    'hand': 'Studio photograph of one adult human hand, open palm facing the camera, five separated digits, wrist at the bottom, fingertips upwards, grey background.',
    'objects': 'Studio photograph of exactly two objects on a grey table: one red ceramic mug on the left and one blue ceramic bowl on the right. Both objects fully visible. Plain grey background.',
    'katana': 'Studio product photograph of one luxury Japanese katana and its black lacquer scabbard lying separately side by side on grey fabric. Entire curved blade and entire scabbard visible, gold fittings, top-down view.',
}

CASES['duo']='Photorealistic full-body portrait of exactly two adults, a samurai man in black armor on the left and a woman in a red kimono on the right, standing in front of a Japanese castle. Both visible from head to feet, hands visible, daylight.'

def plan():
    rows=[dict(case='hand',width=512,height=512,seed=20261113,steps=20,condition='smoke')]
    rows += [dict(case=case,width=1024,height=1024,seed=seed,steps=50,condition='quality') for case in CASES for seed in (20261113,20261114)]
    rows += [{**rows[1],'condition':'repeat'}]
    rows += [dict(case='duo',width=w,height=576,seed=20261113,steps=50,condition=condition) for w,condition in ((1024,'screen16x9'),(768,'screen4x3'))]
    return rows


def validate_map(mapping):
    if set(mapping.values()) != {0, 1}:
        raise ValueError('DENOISER_MUST_USE_BOTH_GPUS_ONLY')
    if not any(k.startswith('transformer_blocks.') and v == 1 for k, v in mapping.items()):
        raise ValueError('ACTUAL_BLOCK_SPLIT_REQUIRED')


def verify_files(root, rows):
    for r in rows:
        path = Path(r.get('absolute',str(root/r['name'])))
        if path.is_symlink() or path.stat().st_size != r['bytes']:
            raise RuntimeError('MODEL_FILE_SIZE_OR_SYMLINK')
        with path.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != r['sha256']:
                raise RuntimeError('MODEL_CHECKSUM')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--shared-models', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    a.output.mkdir(mode=0o700)
    import quality_probe as probe
    import torch
    if os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(GPUS):
        raise RuntimeError('EXACT_GPU_UUIDS_REQUIRED')
    if os.environ.get('HF_HUB_OFFLINE') != '1':
        raise RuntimeError('OFFLINE_REQUIRED')
    from checkpoint_probe import check_processes
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=4)
    check_processes(raw,os.getpid())
    torch.set_num_threads(8)
    if torch.cuda.device_count() != 2 or any(torch.cuda.get_device_capability(i) != (7, 0) for i in range(2)):
        raise RuntimeError('EXPECTED_TWO_VOLTA_GPUS')
    for i in range(2):
        torch.cuda.set_per_process_memory_fraction(.88, i)
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    rows = json.loads(a.manifest.read_text())
    verify_files(a.models, rows)
    samples, records = [], []
    stop, unsafe = threading.Event(), threading.Event()
    def monitor():
        with (a.output/'samples.jsonl').open('w', buffering=1) as log:
            while not stop.is_set():
                try:
                    row = probe.sample_once()
                    ps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'], text=True, timeout=4)
                    for line in ps.splitlines():
                        uuid, pid = (x.strip() for x in line.split(','))
                        if uuid in GPUS and int(pid) != os.getpid():
                            unsafe.set()
                    for gpu in row['gpus']:
                        if gpu['uuid'] in GPUS and (float(gpu['temperature.gpu']) >= 65 or float(gpu['temperature.memory']) >= 70):
                            unsafe.set()
                    if unsafe.is_set():
                        row['guard'] = 'RESOURCE_CONFLICT_OR_TEMPERATURE'
                except Exception as exc:
                    row = {'error': type(exc).__name__}
                    unsafe.set()
                samples.append(row)
                log.write(json.dumps(row)+'\n')
                stop.wait(.5)
    def check():
        if unsafe.is_set():
            raise RuntimeError('RESOURCE_GUARD_STOP')
    def nvlink():
        return {str(i): subprocess.run(['nvidia-smi', 'nvlink', '-gt', 'd', '-i', str(i)], capture_output=True, text=True, timeout=5).stdout for i in (0, 1)}
    def event(name, **kw):
        print(json.dumps({'phase': name, **kw}), flush=True)
    worker = threading.Thread(target=monitor)
    worker.start()
    try:
        started = time.monotonic()
        event('encode_cpu_start')
        # Reuse audited Comfy tokenizers and encoders, never start another server.
        sys.path.insert(0, str(a.root/'engine'))
        import comfy.sd
        import comfy.model_management as mm
        clip = comfy.sd.load_clip([str(a.shared_models/'clip_l.safetensors'), str(a.shared_models/'t5xxl_fp16.safetensors')],
            clip_type=comfy.sd.CLIPType.FLUX,
            model_options={'load_device': torch.device('cpu'), 'offload_device': torch.device('cpu'),
                           'initial_device': torch.device('cpu'), 'dtype': torch.float32})
        clip.cond_stage_model.to(dtype=torch.float32)
        embeddings = {}
        with torch.inference_mode():
            for name, prompt in CASES.items():
                check()
                cond, pooled = clip.encode_from_tokens(clip.tokenize(prompt), return_pooled=True)
                if not torch.isfinite(cond).all() or not torch.isfinite(pooled).all():
                    raise RuntimeError('NONFINITE_TEXT_ENCODING')
                embeddings[name] = (cond.detach().cpu().half(), pooled.detach().cpu().half())
                event('encoded', case=name, shape=list(cond.shape))
        encode_seconds = time.monotonic()-started
        mm.unload_all_models()
        del clip
        gc.collect()
        from accelerate import init_empty_weights, dispatch_model
        from accelerate.utils import infer_auto_device_map
        from diffusers import FluxTransformer2DModel, FluxPipeline, AutoencoderKL, FlowMatchEulerDiscreteScheduler
        from diffusers.loaders.single_file_utils import convert_flux_transformer_checkpoint_to_diffusers, convert_ldm_vae_checkpoint
        from safetensors.torch import load_file
        check()
        event('load_transformer_start')
        load_start = time.monotonic()
        with init_empty_weights():
            transformer = FluxTransformer2DModel(guidance_embeds=True)
        state = convert_flux_transformer_checkpoint_to_diffusers(load_file(str(a.models/'flux1-dev.safetensors')))
        transformer.load_state_dict(state, strict=True, assign=True)
        del state
        transformer.to(dtype=torch.float16)
        from flux_chunked_attention import ChunkedFluxAttnProcessor
        transformer.set_attn_processor(ChunkedFluxAttnProcessor(256))
        mapping = dict(infer_auto_device_map(transformer, max_memory={0: '12GiB', 1: '12GiB'},
            dtype=torch.float16, no_split_module_classes=transformer._no_split_modules))
        validate_map(mapping)
        check()
        transformer = dispatch_model(transformer, device_map=mapping, main_device=0)
        distribution = Counter()
        for value in transformer.parameters():
            distribution[str(value.device)] += value.numel()*value.element_size()
        if set(distribution) != {'cuda:0', 'cuda:1'}:
            raise RuntimeError('ACTUAL_PLACEMENT_INVALID')
        vae_config = dict(in_channels=3, out_channels=3,
            down_block_types=['DownEncoderBlock2D']*4, up_block_types=['UpDecoderBlock2D']*4,
            block_out_channels=[128, 256, 512, 512], layers_per_block=2, latent_channels=16,
            norm_num_groups=32, sample_size=1024, scaling_factor=.3611, shift_factor=.1159,
            use_quant_conv=False, use_post_quant_conv=False)
        vae = AutoencoderKL(**vae_config)
        vae.load_state_dict(convert_ldm_vae_checkpoint(load_file(str(a.shared_models/'ae.safetensors')), vae_config), strict=True)
        vae.to('cuda:0', dtype=torch.float32)
        vae.enable_tiling()
        vae.tile_sample_min_size=512
        vae.tile_latent_min_size=512//(2**(len(vae.config.block_out_channels)-1))
        pipe = FluxPipeline(FlowMatchEulerDiscreteScheduler(shift=1.0, use_dynamic_shifting=True, base_shift=.5, max_shift=1.15, base_image_seq_len=256, max_image_seq_len=4096),
            vae, None, None, None, None, transformer)
        pipe.set_progress_bar_config(disable=True)
        load_seconds = time.monotonic()-load_start
        manifest = {'model': 'FLUX.1-dev', 'files': rows, 'device_map': mapping,
            'parameter_bytes_by_device': dict(distribution), 'text_encoder': 'CPU FP32',
            'denoiser': 'FP16, all parameters resident on two V100, no CPU offload', 'vae': 'GPU0 FP32',
            'encode_seconds': encode_seconds, 'load_seconds': load_seconds,
            'torch': torch.__version__, 'peer_access': [torch.cuda.can_device_access_peer(0, 1), torch.cuda.can_device_access_peer(1, 0)],
            'steps': 50, 'guidance': 3.5, 'attention_query_chunk':256, 'vae_tile_pixels':512, 'vae_tile_overlap':vae.tile_overlap_factor, 'scheduler':dict(pipe.scheduler.config), 'plan':plan(), 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'promotion_allowed': False}
        probe.write_json(a.output/'manifest.json', manifest)
        event('loaded', parameter_bytes_by_device=dict(distribution))
        def callback(pipe, step, timestep, kwargs):
            check()
            if not torch.isfinite(kwargs['latents']).all():
                raise RuntimeError('NONFINITE_LATENTS')
            if (step+1)%10==0:
                event('step',index=i,step=step+1,total=steps)
            return kwargs
        for i, row in enumerate(plan()):
            name,width,height,seed,steps=(row[k] for k in ('case','width','height','seed','steps'))
            probe.write_json(a.output/f'{i:02d}-intent.json',row)
            check()
            for gpu in range(2):
                torch.cuda.reset_peak_memory_stats(gpu)
            before = nvlink()
            cond, pooled = (t.to('cuda:0') for t in embeddings[name])
            t0 = time.monotonic()
            with torch.inference_mode():
                packed = pipe(prompt_embeds=cond, pooled_prompt_embeds=pooled,
                    width=width, height=height, num_inference_steps=steps, guidance_scale=3.5,
                    generator=torch.Generator('cuda:0').manual_seed(seed), output_type='latent',
                    callback_on_step_end=callback).images
                from safetensors.torch import save_file
                save_file({'packed':packed.detach().cpu()},str(a.output/f'{i:02d}-latent.safetensors'))
                latents = pipe._unpack_latents(packed, height, width, pipe.vae_scale_factor)
                decoded = vae.decode(latents.float()/vae.config.scaling_factor+vae.config.shift_factor, return_dict=False)[0]
                if not torch.isfinite(decoded).all():
                    raise RuntimeError('NONFINITE_PIXELS')
                image = pipe.image_processor.postprocess(decoded, output_type='pil')[0]
            for gpu in range(2):
                torch.cuda.synchronize(gpu)
            elapsed = time.monotonic()-t0
            path = a.output/f'{i:02d}-{name}.png'
            image.save(path)
            record = {'index': i, 'case': name, 'prompt': CASES[name], 'width': width, 'height': height,
                'seed': seed, 'steps':steps, 'condition':row['condition'], 'guidance':3.5, 'seconds': elapsed, 'png_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'pixel_sha256': hashlib.sha256(image.tobytes()).hexdigest(), 'visual': 'NOT_REVIEWED',
                'nvlink_before': before, 'nvlink_after': nvlink(),
                'torch_peak_allocated_bytes': [torch.cuda.max_memory_allocated(g) for g in range(2)],
                'torch_peak_reserved_bytes': [torch.cuda.max_memory_reserved(g) for g in range(2)]}
            records.append(record)
            probe.write_json(a.output/'results.json', records)
            event('generated', case=name, seconds=elapsed)
            del packed, latents, decoded
        check()
        probe.write_json(a.output/'completion.json', {'generated': len(records),
            'repeat_same_pixels': records[1]['pixel_sha256'] == records[9]['pixel_sha256'],
            'visual_acceptance': 'PENDING_REVIEW', 'promotion_allowed': False})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json', {'error': type(exc).__name__, 'message': str(exc)[:2000]})
        raise
    finally:
        stop.set()
        worker.join()
        probe.write_json(a.output/'telemetry.json', probe.summarize(samples))


if __name__ == '__main__':
    main()
