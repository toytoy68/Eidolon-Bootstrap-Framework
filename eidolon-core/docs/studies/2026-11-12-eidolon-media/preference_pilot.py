# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : preference_pilot.py
# Description : Pilote LoRA Diffusion-DPO local, borné, sans promotion
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Six optimizer attempts qualify mechanics only, never general image quality.

Objective: Wallace et al., CVPR2024, Diffusion-DPO. Reference implementation
reviewed: diffusers 560fb5f4d65b8593c13e4be50a59b1fd9c2d9992.
No external evaluator/API, uploads or download at runtime.
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

from eidolon_core.media_feedback import FeedbackLedger, verify_pair_files
import quality_probe as probe

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--engine-pid',type=int,required=True);a=p.parse_args()
    os.umask(0o077);a.output.mkdir(mode=0o700)
    import torch
    import torch.nn.functional as F
    import numpy as np
    from PIL import Image
    from diffusers import StableDiffusionXLPipeline, DDPMScheduler
    from diffusers.utils import convert_state_dict_to_diffusers
    from peft import LoraConfig, get_peft_model_state_dict
    from safetensors.torch import save_file

    data=json.loads(a.dataset.read_text());book=FeedbackLedger(a.dataset.parent/'ledger')
    if data['ledger_hash']!=book.snapshot()['ledger_hash']:raise RuntimeError('REVIEWS_CHANGED')
    pairs=data['pairs']
    if not 1<=len(pairs)<=16:raise RuntimeError('PILOT_PAIR_BUDGET')
    if any((r['width'],r['height'])!=(1024,1024) or r['model_sha256']!=probe.MODEL_SHA for r in pairs):
        raise RuntimeError('PILOT_CONFIGURATION_MISMATCH')
    paths=[verify_pair_files(r,a.dataset.parent/'assets') for r in pairs]
    token=(a.root/'token').read_text().strip()
    c=probe.LocalGenerationClient('http://127.0.0.1:8190',token)
    opener=probe.urllib.request.build_opener(probe.urllib.request.ProxyHandler({}))
    probe.assert_idle(c,opener);probe.free_cache(opener)
    if not probe.gpu_probe(probe.GPU,a.engine_pid)['ready']:raise RuntimeError('GPU_BUSY')
    model=a.root/'engine/models/checkpoints/sd_xl_base_1.0.safetensors'
    with model.open('rb') as f:base_sha=hashlib.file_digest(f,'sha256').hexdigest()
    if base_sha!=probe.MODEL_SHA:raise RuntimeError('BASE_HASH_MISMATCH')
    if torch.cuda.device_count()!=1 or torch.cuda.get_device_capability(0)!=(7,0):
        raise RuntimeError('EXPECTED_SINGLE_VOLTA_GPU')
    torch.set_num_threads(4);torch.manual_seed(20261112)
    torch.cuda.set_per_process_memory_fraction(.85)
    torch.backends.cuda.matmul.allow_tf32=False
    samples=[];stop=threading.Event();unsafe=threading.Event()
    def guard():
        with (a.output/'samples.jsonl').open('w',buffering=1) as log:
            while not stop.is_set():
                try:
                    row=probe.sample_once()
                    procs=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=4).splitlines()
                    if any(int(x.strip()) not in (os.getpid(),a.engine_pid) for x in procs if x.strip()):
                        row['guard']='FOREIGN_GPU_PROCESS';unsafe.set()
                    gpu=next(g for g in row['gpus'] if g['uuid']==probe.GPU)
                    if float(gpu['temperature.gpu'])>=65 or float(gpu['temperature.memory'])>=70:
                        row['guard']='THERMAL_LIMIT';unsafe.set()
                except Exception as exc:
                    row={'error':type(exc).__name__};unsafe.set()
                samples.append(row);log.write(json.dumps(row)+'\n');stop.wait(.5)
    def check():
        if unsafe.is_set():raise RuntimeError('RESOURCE_GUARD_STOP')
        if book.snapshot()['ledger_hash']!=data['ledger_hash']:raise RuntimeError('REVIEWS_CHANGED')
    monitor=threading.Thread(target=guard);monitor.start();started=time.monotonic()
    try:
        probe.write_json(a.output/'intent.json',{'dataset_sha256':hashlib.sha256(a.dataset.read_bytes()).hexdigest(),
            'ledger_hash':data['ledger_hash'],'base_sha256':base_sha,'attempts':6,'rank':4,
            'learning_rate':1e-5,'beta_dpo':1000,'seed':20261112,'promotion_allowed':False,
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        pipe=StableDiffusionXLPipeline.from_single_file(str(model),
            config=str(a.root/'preference-lab/sdxl-config'),local_files_only=True,
            torch_dtype=torch.float16,add_watermarker=False)
        pipe.set_progress_bar_config(disable=True)
        pipe.unet.requires_grad_(False);pipe.vae.requires_grad_(False)
        pipe.text_encoder.requires_grad_(False);pipe.text_encoder_2.requires_grad_(False)
        pipe.text_encoder.float();pipe.text_encoder_2.float()
        encodings={}
        with torch.no_grad():
            for pair in pairs:
                check()
                if pair['prompt'] not in encodings:
                    emb,_,pooled,_=pipe.encode_prompt(pair['prompt'],device=torch.device('cpu'),do_classifier_free_guidance=False)
                    encodings[pair['prompt']]=(emb.half(),pooled.half())
        pipe.vae.to(device='cuda',dtype=torch.float32);pipe.vae.enable_tiling()
        latents=[]
        with torch.no_grad():
            for row in paths:
                encoded=[]
                for path in row:
                    check()
                    with Image.open(path) as image:
                        if image.size!=(1024,1024):raise RuntimeError('DATASET_IMAGE_SIZE')
                        pixels=torch.from_numpy(np.array(image.convert('RGB'),copy=True)).permute(2,0,1).unsqueeze(0).float()/127.5-1
                    z=pipe.vae.encode(pixels.cuda()).latent_dist.mode()*pipe.vae.config.scaling_factor
                    if not torch.isfinite(z).all():raise RuntimeError('NONFINITE_LATENT')
                    encoded.append(z.half().cpu())
                latents.append(encoded)
        pipe.vae.cpu();gc.collect();torch.cuda.empty_cache()
        unet=pipe.unet
        unet.add_adapter(LoraConfig(r=4,lora_alpha=4,init_lora_weights='gaussian',
                                   target_modules=['to_q','to_k','to_v','to_out.0']))
        for name,param in unet.named_parameters():
            if param.requires_grad:
                if 'lora_' not in name:raise RuntimeError('BASE_WEIGHT_TRAINABLE')
                param.data=param.data.float()
        unet.to('cuda');unet.enable_gradient_checkpointing();unet.set_attention_slice('max');unet.train()
        params=[p for p in unet.parameters() if p.requires_grad]
        before={k:v.detach().float().cpu().clone() for k,v in get_peft_model_state_dict(unet).items()}
        optimizer=torch.optim.AdamW(params,lr=1e-5)
        scaler=torch.amp.GradScaler('cuda',init_scale=64)
        scheduler=DDPMScheduler.from_config(pipe.scheduler.config)
        if scheduler.config.prediction_type!='epsilon':raise RuntimeError('EXPECTED_EPSILON_TARGET')
        time_ids=torch.tensor([[1024,1024,0,0,1024,1024]],device='cuda',dtype=torch.float16)
        logs=[];updates=0
        for step in range(6):
            check();i=step%len(pairs);z=[x.cuda() for x in latents[i]]
            noise=torch.randn_like(z[0]);t=torch.randint(0,scheduler.config.num_train_timesteps,(1,),device='cuda')
            noisy=[scheduler.add_noise(x,noise,t) for x in z]
            emb,pooled=encodings[pairs[i]['prompt']];emb=emb.cuda();pooled=pooled.cuda()
            def mse(x):
                with torch.autocast('cuda',dtype=torch.float16):
                    predicted=unet(x,t,encoder_hidden_states=emb,
                        added_cond_kwargs={'text_embeds':pooled,'time_ids':time_ids}).sample
                return F.mse_loss(predicted.float(),noise.float())
            unet.disable_adapters()
            try:
                with torch.no_grad():reference=mse(noisy[0])-mse(noisy[1])
            finally:unet.enable_adapters()
            optimizer.zero_grad(set_to_none=True)
            difference=mse(noisy[0])-mse(noisy[1])
            margin=-500.0*(difference-reference)
            loss=-F.logsigmoid(margin)
            if not torch.isfinite(loss):raise RuntimeError('NONFINITE_LOSS')
            scaler.scale(loss).backward();scaler.unscale_(optimizer)
            grad=torch.nn.utils.clip_grad_norm_(params,1.0)
            if not torch.isfinite(grad):raise RuntimeError('NONFINITE_GRADIENT')
            scale=scaler.get_scale();scaler.step(optimizer);scaler.update()
            updated=scaler.get_scale()>=scale;updates+=int(updated)
            log={'step':step+1,'pair':i,'timestep':int(t.item()),'loss':float(loss.detach()),
                 'margin':float(margin.detach()),'gradient_norm_before_clip':float(grad),
                 'optimizer_updated':updated,'cuda_max_allocated_mib':torch.cuda.max_memory_allocated()/1024**2}
            logs.append(log);probe.write_json(a.output/'steps.json',logs);print(json.dumps(log),flush=True)
        check()
        after={k:v.detach().float().cpu().contiguous() for k,v in get_peft_model_state_dict(unet).items()}
        delta=sum(float((after[k]-before[k]).square().sum()) for k in before)**.5
        if updates==0 or delta==0:raise RuntimeError('NO_EFFECTIVE_TRAINING')
        save_file(after,str(a.output/'adapter-peft.safetensors'))
        StableDiffusionXLPipeline.save_lora_weights(str(a.output/'candidate'),
            unet_lora_layers=convert_state_dict_to_diffusers(after),safe_serialization=True)
        probe.write_json(a.output/'result.json',{'status':'TRAINED_EXPERIMENTAL','optimizer_updates':updates,
            'pairs':len(pairs),'distinct_prompts':len({r['prompt'] for r in pairs}),
            'trainable_parameters':sum(p.numel() for p in params),'adapter_delta_l2':delta,
            'seconds_wall':time.monotonic()-started,'promotion_allowed':False,
            'visual_improvement':'NOT_EVALUATED','ledger_hash':data['ledger_hash'],
            'candidate_sha256':hashlib.sha256((a.output/'candidate/pytorch_lora_weights.safetensors').read_bytes()).hexdigest()})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json',{'type':type(exc).__name__,'message':str(exc)[:1000],
            'seconds_wall':time.monotonic()-started,'promotion_allowed':False})
        raise
    finally:
        stop.set();monitor.join();probe.write_json(a.output/'telemetry.json',probe.summarize(samples))

if __name__=='__main__':main()
