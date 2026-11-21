# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : zimage_base_probe_g344.py
# Description : Recette locale Z-Image non Turbo FP32 sur deux V100
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Isolated offline research run. No network generation, no production promotion."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from flux_schnell_probe_g339 import CASES, GPUS, plan as flux_plan
from zimage_attention_g342 import chunked_attention

def plan():
    return [{**r,"steps":28} for r in flux_plan()]

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work',type=Path,required=True)
    ap.add_argument('--models',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--precision',choices=['fp32'],default='fp32')
    ap.add_argument('--indices',default='0')
    a=ap.parse_args();os.umask(0o077);a.output.mkdir(mode=0o700)
    import torch
    import quality_probe as probe
    from checkpoint_probe import check_processes
    from safetensors.torch import save_file,load_file
    from torch.nn.attention import sdpa_kernel,SDPBackend
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==','.join(GPUS)
    assert os.environ.get('HF_HUB_OFFLINE')=='1'
    assert torch.cuda.device_count()==2
    assert all(torch.cuda.get_device_capability(i)==(7,0) for i in (0,1))
    torch.set_num_threads(8)
    for i in (0,1):torch.cuda.set_per_process_memory_fraction(.88,i)
    check_processes(subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True),os.getpid())
    files=json.loads((a.work/'downloads.json').read_text())
    for r in files:
        f=a.models/r['path']
        if f.is_symlink() or f.stat().st_size!=r['bytes'] or sha(f)!=r['sha256']:raise RuntimeError('MODEL_CHECKSUM')
    for r in json.loads((a.work/'small-files.json').read_text()):
        if sha(a.models/r['path'])!=r['sha256']:raise RuntimeError('CONFIG_CHECKSUM')
    samples=[];records=[];stop=threading.Event();unsafe=threading.Event()
    def event(phase,**kw):print(json.dumps({'phase':phase,**kw}),flush=True)
    def monitor():
        with (a.output/'samples.jsonl').open('w',buffering=1) as f:
            while not stop.is_set():
                try:
                    row=probe.sample_once()
                    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=4)
                    for line in raw.splitlines():
                        uuid,pid=(x.strip() for x in line.split(','))
                        if uuid in GPUS and int(pid)!=os.getpid():unsafe.set()
                    for gpu in row['gpus']:
                        if gpu['uuid'] in GPUS and (float(gpu['temperature.gpu'])>=65 or float(gpu['temperature.memory'])>=70):unsafe.set()
                    if unsafe.is_set():row['guard']='RESOURCE_CONFLICT_OR_TEMPERATURE'
                except Exception as exc:row={'error':type(exc).__name__};unsafe.set()
                samples.append(row);f.write(json.dumps(row)+'\n');stop.wait(.5)
    def check():
        if unsafe.is_set():raise RuntimeError('RESOURCE_GUARD_STOP')
    worker=threading.Thread(target=monitor);worker.start()
    try:
        from transformers import Qwen3ForCausalLM,Qwen2TokenizerFast
        from diffusers import ZImagePipeline,ZImageTransformer2DModel,AutoencoderKL,FlowMatchEulerDiscreteScheduler
        import diffusers.models.transformers.transformer_z_image as zmodule
        zmodule.dispatch_attention_fn=chunked_attention
        import diffusers,transformers
        dtype=torch.float32
        cache=a.work/'prompt-embeddings.safetensors';cachemeta=a.work/'prompt-embeddings.json'
        text_cases={**CASES,'negative':''}
        t=time.monotonic();embeddings={};reused=False
        if cache.exists() and cachemeta.exists():
            meta=json.loads(cachemeta.read_text())
            assert meta['prompts']==text_cases and meta['sha256']==sha(cache)
            embeddings=load_file(str(cache));encode_seconds=meta['encode_seconds'];reused=True
        else:
            event('encode_cpu_start')
            encoder=Qwen3ForCausalLM.from_pretrained(a.models/'text_encoder',torch_dtype=torch.float32,local_files_only=True,attn_implementation='sdpa').eval()
            tokenizer=Qwen2TokenizerFast.from_pretrained(a.models/'tokenizer',local_files_only=True)
            textpipe=ZImagePipeline(None,None,encoder,tokenizer,None)
            with torch.inference_mode():
                for name,prompt in text_cases.items():
                    check();v=textpipe._encode_prompt(prompt,device=torch.device('cpu'),max_sequence_length=512)[0]
                    if not torch.isfinite(v).all():raise RuntimeError('NONFINITE_TEXT')
                    embeddings[name]=v.cpu().contiguous();event('encoded',case=name,shape=list(v.shape))
            encode_seconds=time.monotonic()-t;save_file(embeddings,str(cache))
            probe.write_json(cachemeta,{'prompts':text_cases,'encode_seconds':encode_seconds,'sha256':sha(cache),'dtype':'CPU FP32','sequence_length':512})
            del textpipe,encoder,tokenizer;gc.collect()
        t=time.monotonic();event('load_start',precision=a.precision)
        transformer,load_info=ZImageTransformer2DModel.from_pretrained(a.models/'transformer',torch_dtype=dtype,local_files_only=True,output_loading_info=True)
        if any(load_info.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']):raise RuntimeError('TRANSFORMER_LOAD_MISMATCH')
        transformer.eval()
        from accelerate import dispatch_model
        from accelerate.utils import infer_auto_device_map
        mapping=infer_auto_device_map(transformer,max_memory={0:'12GiB',1:'13GiB'},dtype=dtype,no_split_module_classes=transformer._no_split_modules)
        assert set(mapping.values())=={0,1},mapping
        transformer=dispatch_model(transformer,device_map=mapping,main_device=0)
        vae,vae_info=AutoencoderKL.from_pretrained(a.models/'vae',torch_dtype=torch.float32,local_files_only=True,output_loading_info=True)
        if any(vae_info.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']):raise RuntimeError('VAE_LOAD_MISMATCH')
        vae.eval().to('cuda:0')
        vae.enable_tiling();vae.tile_sample_min_size=512;vae.tile_latent_min_size=64
        scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(a.models/'scheduler',local_files_only=True)
        pipe=ZImagePipeline(scheduler,vae,None,None,transformer);pipe.set_progress_bar_config(disable=True)
        distribution={}
        for v in transformer.parameters():distribution[str(v.device)]=distribution.get(str(v.device),0)+v.numel()*v.element_size()
        assert set(distribution)<= {'cuda:0','cuda:1'}
        manifest={'model':'Z-Image','precision':a.precision,'files':files,'text_encoder':'Qwen3 CPU FP32,512 tokens,penultimate hidden state','vae':'GPU0 FP32,tiled512px','attention':'PyTorch MATH FP32, query chunks256','torch':torch.__version__,'diffusers':diffusers.__version__,'transformers':transformers.__version__,'encode_seconds':encode_seconds,'embeddings_reused':reused,'load_seconds':time.monotonic()-t,'parameter_bytes_by_device':distribution,'device_map':mapping,'attention_adapter_sha256':sha(Path(__file__).with_name('zimage_attention_g342.py')),'scheduler':dict(scheduler.config),'steps':28,'guidance':4.0,'negative_prompt':'','cfg_normalization':False,'cfg_execution':'sequential conditional/unconditional','plan':plan(),'runner_sha256':sha(Path(__file__)),'promotion_allowed':False}
        probe.write_json(a.output/'manifest.json',manifest);event('loaded',distribution=distribution)
        original_forward=transformer.forward
        forwards={'calls':0,'sequences':0}
        def sequential_forward(x,t,cap_feats,return_dict=True,**kwargs):
            if return_dict or kwargs:raise RuntimeError('UNSUPPORTED_CFG_CALL')
            result=[]
            for j in range(len(x)):
                check()
                result.extend(original_forward([x[j]],t[j:j+1],[cap_feats[j]],return_dict=False)[0])
                forwards['sequences']+=1
            forwards['calls']+=1
            return (result,)
        # Check the sequential implementation against batched CFG at 512px.
        with torch.inference_mode(),sdpa_kernel(SDPBackend.MATH):
            generator=torch.Generator('cuda:0').manual_seed(344)
            xs=[torch.randn((16,1,64,64),generator=generator,device='cuda:0') for _ in range(2)]
            ts=torch.tensor([.5,.5],device='cuda:0')
            caps=[embeddings['hand'].to('cuda:0'),embeddings['negative'].to('cuda:0')]
            batched=original_forward(xs,ts,caps,return_dict=False)[0]
            serial=sequential_forward(xs,ts,caps,return_dict=False)[0]
            errors=[float((x-y).abs().max()) for x,y in zip(batched,serial)]
            ok=all(torch.allclose(x,y,atol=.003,rtol=.003) for x,y in zip(batched,serial))
            probe.write_json(a.output/'cfg-equivalence.json',{'max_abs_errors':errors,'atol':.003,'rtol':.003,'passed':ok,'scope':'two random 512px samples at t=.5; not whole trajectory'})
            if not ok:raise RuntimeError('SEQUENTIAL_CFG_MISMATCH')
            del xs,ts,caps,batched,serial
        transformer.forward=sequential_forward
        def callback(pipe,step,timestep,kwargs):
            check()
            event('step',step=step+1,total=28)
            if not torch.isfinite(kwargs['latents']).all():raise RuntimeError('NONFINITE_LATENTS')
            return kwargs
        selected=[int(x) for x in a.indices.split(',')]
        assert selected and len(selected)==len(set(selected)) and all(0<=i<len(plan()) for i in selected)
        for i in selected:
            row=plan()[i]
            forwards.update(calls=0,sequences=0)
            check();name=row['case'];probe.write_json(a.output/f'{i:02d}-intent.json',row)
            for gpu in (0,1):torch.cuda.reset_peak_memory_stats(gpu)
            t=time.monotonic()
            with torch.inference_mode():
                with sdpa_kernel(SDPBackend.MATH):
                    latents=pipe(prompt_embeds=[embeddings[name].to('cuda:0',dtype=dtype)],width=row['width'],height=row['height'],num_inference_steps=28,guidance_scale=4.0,cfg_normalization=False,negative_prompt_embeds=[embeddings['negative'].to('cuda:0',dtype=dtype)],generator=torch.Generator('cuda:0').manual_seed(row['seed']),output_type='latent',callback_on_step_end=callback).images
                if not torch.isfinite(latents).all():raise RuntimeError('NONFINITE_DECODE_LATENTS')
                save_file({'latents':latents.detach().cpu()},str(a.output/f'{i:02d}-latent.safetensors'))
                with sdpa_kernel(SDPBackend.MATH):decoded=vae.decode(latents.float()/vae.config.scaling_factor+vae.config.shift_factor,return_dict=False)[0]
                if not torch.isfinite(decoded).all():raise RuntimeError('NONFINITE_PIXELS')
                image=pipe.image_processor.postprocess(decoded,output_type='pil')[0]
            for gpu in (0,1):torch.cuda.synchronize(gpu)
            elapsed=time.monotonic()-t;path=a.output/f'{i:02d}-{name}.png';image.save(path)
            records.append({'index':i,'forward_counts':dict(forwards),**row,'prompt':CASES[name],'guidance':4.0,'seconds':elapsed,'png_sha256':sha(path),'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'visual':'NOT_REVIEWED','torch_peak_allocated_bytes':[torch.cuda.max_memory_allocated(g) for g in (0,1)]})
            probe.write_json(a.output/'results.json',records);event('generated',index=i,case=name,seconds=elapsed)
            del latents,decoded
        check();probe.write_json(a.output/'completion.json',{'generated':len(records),'repeat_same_pixels':(next(r['pixel_sha256'] for r in records if r['index']==1)==next(r['pixel_sha256'] for r in records if r['index']==9)) if {1,9}.issubset({r['index'] for r in records}) else None,'visual_acceptance':'PENDING_REVIEW','promotion_allowed':False})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json',{'error':type(exc).__name__,'message':str(exc)[:2000]});raise
    finally:
        stop.set();worker.join();probe.write_json(a.output/'telemetry.json',probe.summarize(samples))

if __name__=='__main__':main()
