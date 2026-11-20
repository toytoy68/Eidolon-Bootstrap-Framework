# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sd35_medium_probe_g346.py
# Description : Recette locale SD3.5 Medium sur une V100
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
import inspect

def plan():
    return [{**r,"steps":40} for r in flux_plan()]

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work',type=Path,required=True)
    ap.add_argument('--models',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--precision',choices=['fp16','fp32'],default='fp16')
    ap.add_argument('--indices',default='0')
    a=ap.parse_args();os.umask(0o077);a.output.mkdir(mode=0o700)
    import torch
    import quality_probe as probe
    from checkpoint_probe import check_processes
    from safetensors.torch import save_file,load_file
    from torch.nn.attention import sdpa_kernel,SDPBackend
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==GPUS[0]
    assert os.environ.get('HF_HUB_OFFLINE')=='1'
    assert torch.cuda.device_count()==1
    assert all(torch.cuda.get_device_capability(i)==(7,0) for i in (0,))
    torch.set_num_threads(8)
    for i in (0,):torch.cuda.set_per_process_memory_fraction(.88,i)
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
        from transformers import CLIPTextModelWithProjection,CLIPTokenizer,T5EncoderModel,T5Tokenizer
        from diffusers import StableDiffusion3Pipeline,SD3Transformer2DModel,AutoencoderKL,FlowMatchEulerDiscreteScheduler
        import diffusers,transformers
        dtype=torch.float16 if a.precision=='fp16' else torch.float32
        cache=a.work/'prompt-embeddings.safetensors';cachemeta=a.work/'prompt-embeddings.json'
        t=time.monotonic();embeddings={};reused=False
        if cache.exists() and cachemeta.exists():
            meta=json.loads(cachemeta.read_text())
            assert meta['prompts']==CASES and meta['sha256']==sha(cache)
            embeddings=load_file(str(cache));encode_seconds=meta['encode_seconds'];reused=True
        else:
            event('encode_cpu_start')
            encoders=[CLIPTextModelWithProjection.from_pretrained(a.models/folder,torch_dtype=torch.float32,local_files_only=True,attn_implementation='eager').eval() for folder in ['text_encoder','text_encoder_2']]
            encoders.append(T5EncoderModel.from_pretrained(a.models/'text_encoder_3',torch_dtype=torch.float32,local_files_only=True).eval())
            tokenizers=[CLIPTokenizer.from_pretrained(a.models/folder,local_files_only=True) for folder in ['tokenizer','tokenizer_2']]
            tokenizers.append(T5Tokenizer.from_pretrained(a.models/'tokenizer_3',local_files_only=True))
            textpipe=StableDiffusion3Pipeline(tokenizer=tokenizers[0],tokenizer_2=tokenizers[1],tokenizer_3=tokenizers[2],text_encoder=encoders[0],text_encoder_2=encoders[1],text_encoder_3=encoders[2],vae=None,transformer=None,scheduler=None)
            with torch.inference_mode():
                for name,prompt in {**CASES,'negative':''}.items():
                    check();v,_,pool,_=textpipe.encode_prompt(prompt,None,None,device=torch.device('cpu'),max_sequence_length=256,do_classifier_free_guidance=False)
                    if not torch.isfinite(v).all() or not torch.isfinite(pool).all():raise RuntimeError('NONFINITE_TEXT')
                    embeddings[name]=v.cpu().contiguous();embeddings[name+'_pool']=pool.cpu().contiguous();event('encoded',case=name,shape=list(v.shape))
            encode_seconds=time.monotonic()-t;save_file(embeddings,str(cache))
            probe.write_json(cachemeta,{'prompts':CASES,'negative_prompt':'','sha256':sha(cache),'encode_seconds':encode_seconds,'dtype':'CPU FP32','sequence_length':256})
            del textpipe,encoders,tokenizers;gc.collect()
        t=time.monotonic();event('load_start',precision=a.precision)
        transformer,load_info=SD3Transformer2DModel.from_pretrained(a.models/'transformer',torch_dtype=dtype,local_files_only=True,output_loading_info=True)
        if any(load_info.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']):raise RuntimeError('TRANSFORMER_LOAD_MISMATCH')
        transformer.eval()
        transformer.to('cuda:0')
        mapping={'':0}
        vae,vae_info=AutoencoderKL.from_pretrained(a.models/'vae',torch_dtype=torch.float32,local_files_only=True,output_loading_info=True)
        if any(vae_info.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']):raise RuntimeError('VAE_LOAD_MISMATCH')
        vae.eval().to('cuda:0')
        vae.enable_tiling()
        scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(a.models/'scheduler',local_files_only=True)
        pipe=StableDiffusion3Pipeline(scheduler=scheduler,vae=vae,text_encoder=None,tokenizer=None,text_encoder_2=None,tokenizer_2=None,text_encoder_3=None,tokenizer_3=None,transformer=transformer);pipe.set_progress_bar_config(disable=True)
        distribution={}
        for v in transformer.parameters():distribution[str(v.device)]=distribution.get(str(v.device),0)+v.numel()*v.element_size()
        assert set(distribution)<= {'cuda:0'}
        manifest={'model':'SD3.5-Medium','precision':a.precision,'files':files,'text_encoder':'CLIP-L + CLIP-G + T5-XXL CPU FP32,256 T5 tokens','vae':'GPU0 FP32, native tiling','attention':'PyTorch EFFICIENT_ATTENTION transformer; MATH VAE','torch':torch.__version__,'diffusers':diffusers.__version__,'transformers':transformers.__version__,'encode_seconds':encode_seconds,'embeddings_reused':reused,'load_seconds':time.monotonic()-t,'parameter_bytes_by_device':distribution,'device_map':mapping,'scheduler':dict(scheduler.config),'steps':40,'guidance':4.5,'negative_prompt':'','skip_guidance_layers':None,'plan':plan(),'pipeline_source_sha256':sha(Path(inspect.getfile(StableDiffusion3Pipeline))),'runner_sha256':sha(Path(__file__)),'promotion_allowed':False}
        probe.write_json(a.output/'manifest.json',manifest);event('loaded',distribution=distribution)
        def callback(pipe,step,timestep,kwargs):
            check()
            if not torch.isfinite(kwargs['latents']).all():raise RuntimeError('NONFINITE_LATENTS')
            return kwargs
        selected=[int(x) for x in a.indices.split(',')]
        assert selected and len(selected)==len(set(selected)) and all(0<=i<len(plan()) for i in selected)
        for i in selected:
            row=plan()[i]
            check();name=row['case'];probe.write_json(a.output/f'{i:02d}-intent.json',row)
            for gpu in (0,):torch.cuda.reset_peak_memory_stats(gpu)
            t=time.monotonic()
            with torch.inference_mode():
                with sdpa_kernel(SDPBackend.EFFICIENT_ATTENTION):
                    latents=pipe(prompt_embeds=embeddings[name].to('cuda:0',dtype=dtype),pooled_prompt_embeds=embeddings[name+'_pool'].to('cuda:0',dtype=dtype),negative_prompt_embeds=embeddings['negative'].to('cuda:0',dtype=dtype),negative_pooled_prompt_embeds=embeddings['negative_pool'].to('cuda:0',dtype=dtype),width=row['width'],height=row['height'],num_inference_steps=40,guidance_scale=4.5,skip_guidance_layers=None,generator=torch.Generator('cuda:0').manual_seed(row['seed']),output_type='latent',callback_on_step_end=callback).images
                if not torch.isfinite(latents).all():raise RuntimeError('NONFINITE_DECODE_LATENTS')
                save_file({'latents':latents.detach().cpu()},str(a.output/f'{i:02d}-latent.safetensors'))
                with sdpa_kernel(SDPBackend.MATH):decoded=vae.decode(latents.float()/vae.config.scaling_factor+vae.config.shift_factor,return_dict=False)[0]
                if not torch.isfinite(decoded).all():raise RuntimeError('NONFINITE_PIXELS')
                image=pipe.image_processor.postprocess(decoded,output_type='pil')[0]
            for gpu in (0,):torch.cuda.synchronize(gpu)
            elapsed=time.monotonic()-t;path=a.output/f'{i:02d}-{name}.png';image.save(path)
            records.append({'index':i,**row,'prompt':CASES[name],'guidance':4.5,'seconds':elapsed,'png_sha256':sha(path),'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'visual':'NOT_REVIEWED','torch_peak_allocated_bytes':[torch.cuda.max_memory_allocated(g) for g in (0,)]})
            probe.write_json(a.output/'results.json',records);event('generated',index=i,case=name,seconds=elapsed)
            del latents,decoded
        check();probe.write_json(a.output/'completion.json',{'generated':len(records),'repeat_same_pixels':(next(r['pixel_sha256'] for r in records if r['index']==1)==next(r['pixel_sha256'] for r in records if r['index']==9)) if {1,9}.issubset({r['index'] for r in records}) else None,'visual_acceptance':'PENDING_REVIEW','promotion_allowed':False})
    except BaseException as exc:
        probe.write_json(a.output/'failure.json',{'error':type(exc).__name__,'message':str(exc)[:2000]});raise
    finally:
        stop.set();worker.join();probe.write_json(a.output/'telemetry.json',probe.summarize(samples))

if __name__=='__main__':main()
