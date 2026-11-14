# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : animatediff_probe.py
# Description : Recette vidéo locale AnimateDiff avec garde ressources et preuves
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G337 scheduler diagnostic probe. No service, training, download or production mutation."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from checkpoint_probe import GPU, check_processes

PROMPTS = {
 'boat': 'A small red sailboat slowly crossing a calm blue lake, mountains in the background, static camera, gentle ripples',
 'space': 'One silver spaceship slowly flying from left to right through a blue and purple nebula, stars in the background, wide shot, static camera',
}

def plan():
    rows = [dict(case='boat',seed=42,width=256,height=256,frames=8,steps=8,condition='smoke')]
    rows += [dict(case='boat',seed=s,width=512,height=512,frames=16,steps=20,condition='quality') for s in (42,43)]
    rows += [{**rows[1], 'condition':'repeat'}]
    rows += [dict(case='space',seed=s,width=512,height=288,frames=16,steps=20,condition='screen16x9') for s in (42,43)]
    return [{**r,'prompt':PROMPTS[r['case']],'negative_prompt':'bad quality, worse quality','cfg':7.5,'fps':8} for r in rows]


def decoded_to_uint8(decoded):
    """Reject non-finite values before clamping can hide them."""
    import numpy as np
    if not np.isfinite(decoded).all():
        raise ValueError('NONFINITE_DECODE')
    return (np.clip(decoded/2+.5,0,1)*255).round().astype('uint8')


def save_video(frames, path, fps):
    import av
    import numpy as np
    if len(frames)<2 or fps<=0:
        raise ValueError('VIDEO_LENGTH_OR_FPS')
    h,w,c=frames[0].shape
    if c!=3 or w%2 or h%2 or any(f.shape!=(h,w,3) or f.dtype!=np.uint8 for f in frames):
        raise ValueError('VIDEO_SHAPE_OR_DTYPE')
    with av.open(str(path),'w') as container:
        stream=container.add_stream('libx264',rate=fps);stream.width=w;stream.height=h;stream.pix_fmt='yuv420p';stream.options={'crf':'18','preset':'medium'}
        for pixels in frames:
            for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    with av.open(str(path)) as container:
        decoded=[f.to_ndarray(format='rgb24') for f in container.decode(video=0)]
        rate=container.streams.video[0].average_rate;codec=container.streams.video[0].codec_context.name
    if len(decoded)!=len(frames) or any(f.shape!=(h,w,3) for f in decoded) or rate!=fps:
        raise ValueError('MP4_ROUNDTRIP')
    return {'frames':len(decoded),'width':w,'height':h,'fps':str(rate),'codec':codec,'duration_s':len(decoded)/fps,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}



def configure_attention(unet):
    """UNetMotionModel lacks set_attention_slice in Diffusers 0.32.2.

    Slice spatial scores explicitly; preserve short temporal SDPA attention.
    """
    from diffusers.models.attention_processor import SlicedAttnProcessor, AttnProcessor2_0
    processors={}
    for name, processor in unet.attn_processors.items():
        if not isinstance(processor,AttnProcessor2_0):
            raise RuntimeError('UNEXPECTED_ATTENTION_PROCESSOR')
        processors[name]=processor if 'motion_modules' in name else SlicedAttnProcessor(slice_size=4)
    unet.set_attn_processor(processors)
    actual=unet.attn_processors
    if not actual or not any('motion_modules' in k for k in actual):raise RuntimeError('MOTION_ATTENTION_ABSENT')
    for name,processor in actual.items():
        expected=AttnProcessor2_0 if 'motion_modules' in name else SlicedAttnProcessor
        if not isinstance(processor,expected):raise RuntimeError('ATTENTION_NOT_APPLIED')
    return {name:type(processor).__name__ for name,processor in actual.items()}


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args()
    os.umask(0o077);a.output.mkdir(mode=0o700)
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU or os.environ.get('HF_HUB_OFFLINE')!='1':raise RuntimeError('OFFLINE_GPU_CONFIGURATION')
    def check_clients():
        raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=4);check_processes(raw,os.getpid())
    check_clients();manifest=json.loads(a.manifest.read_text());root=Path(manifest['root'])
    for row in manifest['weights']+manifest['metadata']+[dict(absolute=manifest['sd15_checkpoint'],bytes=manifest['sd15_bytes'],sha256=manifest['sd15_sha256'])]:
        f=Path(row['absolute']) if 'absolute'in row else root/row['local_path']
        with f.open('rb') as stream:
            if f.stat().st_size!=row['bytes'] or hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:raise RuntimeError('HASH_'+f.name)
    import torch
    import numpy as np
    from PIL import Image,ImageDraw
    from diffusers import StableDiffusionPipeline,AnimateDiffPipeline,MotionAdapter,DDIMScheduler
    import quality_probe as probe
    if torch.cuda.device_count()!=1 or torch.cuda.get_device_capability(0)!=(7,0):raise RuntimeError('EXPECTED_SINGLE_VOLTA')
    torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.85);torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_math_sdp(True);torch.backends.cudnn.benchmark=False
    samples=[];results=[];stop=threading.Event();unsafe=threading.Event();phase={'phase':'load','index':None}
    def monitor():
        with (a.output/'samples.jsonl').open('w',buffering=1) as log:
            while not stop.is_set():
                try:
                    s=probe.sample_once();check_clients();g=next(g for g in s['gpus'] if g['uuid']==GPU)
                    if float(g['temperature.gpu'])>=65 or float(g['temperature.memory'])>=70:raise RuntimeError('TEMPERATURE_LIMIT')
                    s.update(phase.copy())
                except Exception as e:s={'error':type(e).__name__,'message':str(e)};unsafe.set()
                samples.append(s);log.write(json.dumps(s)+'\n');stop.wait(.5)
    def check():
        if unsafe.is_set():raise RuntimeError('RESOURCE_GUARD_STOP')
    def callback(pipe,step,timestep,kwargs):
        check()
        if not torch.isfinite(kwargs['latents']).all():raise RuntimeError('NONFINITE_LATENTS')
        return kwargs
    worker=threading.Thread(target=monitor);worker.start()
    try:
        start=time.monotonic()
        base=StableDiffusionPipeline.from_single_file(manifest['sd15_checkpoint'],config=str(root/'sd15-config'),local_files_only=True,torch_dtype=torch.float16,use_safetensors=True,safety_checker=None,feature_extractor=None,requires_safety_checker=False)
        base.to('cuda');base.vae.to(torch.float32);base.enable_attention_slicing()
        controls=[]
        for schedule in ('scaled_linear','linear'):
            check();base.scheduler=DDIMScheduler.from_config(base.scheduler.config,clip_sample=False,timestep_spacing='linspace',steps_offset=1,beta_schedule=schedule)
            begin=time.monotonic()
            with torch.inference_mode():
                z=base(prompt=PROMPTS['boat'],negative_prompt='bad quality, worse quality',width=512,height=512,num_inference_steps=20,guidance_scale=7.5,generator=torch.Generator('cuda').manual_seed(42),output_type='latent',callback_on_step_end=callback).images
                d=base.vae.decode(z.float()/base.vae.config.scaling_factor).sample[0].permute(1,2,0).cpu().numpy()
            pixels=decoded_to_uint8(d);Image.fromarray(pixels).save(a.output/(schedule+'.png'))
            controls.append(dict(schedule=schedule,seconds=time.monotonic()-begin,latent_std=z.std().item(),latent_mean=z.mean().item(),pixel_std=float(pixels.std()),scaling_factor=base.vae.config.scaling_factor,sha256=hashlib.sha256(pixels.tobytes()).hexdigest()))
        probe.write_json(a.output/'controls.json',controls)
        probe.write_json(a.output/'completion.json',dict(controls=2,visual_acceptance='PENDING_REVIEW'))
        return
        adapter=MotionAdapter.from_pretrained(root/'adapter',variant='fp16',torch_dtype=torch.float16,local_files_only=True,use_safetensors=True)
        scheduler=DDIMScheduler.from_config(base.scheduler.config,clip_sample=False,timestep_spacing='linspace',steps_offset=1,beta_schedule='linear')
        pipe=AnimateDiffPipeline(vae=base.vae,text_encoder=base.text_encoder,tokenizer=base.tokenizer,unet=base.unet,motion_adapter=adapter,scheduler=scheduler)
        del base,adapter;gc.collect();cpu_load=time.monotonic()-start;start=time.monotonic();pipe.to('cuda');pipe.vae.to(torch.float32);attention=configure_attention(pipe.unet);pipe.unet.enable_forward_chunking(chunk_size=1,dim=1);pipe.set_progress_bar_config(disable=True);torch.cuda.synchronize();transfer=time.monotonic()-start
        proof={'plan':plan(),'source':manifest,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'torch':torch.__version__,'diffusers':__import__('diffusers').__version__,'cpu_load_seconds':cpu_load,'gpu_transfer_seconds':transfer,'scheduler':dict(scheduler.config),'precision':'UNet/motion/CLIP FP16, VAE FP32','attention_processors':attention,'spatial_attention_slice':4,'forward_chunking':{'chunk_size':1,'dim':1},'vae_decode_chunk':1,'training_allowed':False,'offline_required':True}
        probe.write_json(a.output/'manifest.json',proof)
        for i,row in enumerate(plan()):
            phase.update(phase='generate',index=i);check();probe.write_json(a.output/f'{i:02d}-intent.json',row);torch.cuda.reset_peak_memory_stats();begin=time.monotonic()
            with torch.inference_mode():
                latent=pipe(prompt=row['prompt'],negative_prompt=row['negative_prompt'],width=row['width'],height=row['height'],num_frames=row['frames'],num_inference_steps=row['steps'],guidance_scale=row['cfg'],generator=torch.Generator('cuda').manual_seed(row['seed']),output_type='latent',callback_on_step_end=callback).frames
                torch.cuda.synchronize();denoise=time.monotonic()-begin;begin=time.monotonic();phase['phase']='decode';frames=[]
                for frame in latent[0].permute(1,0,2,3):
                    check();decoded=pipe.vae.decode(frame[None].float()/pipe.vae.config.scaling_factor).sample[0].permute(1,2,0).cpu().numpy();frames.append(decoded_to_uint8(decoded))
                torch.cuda.synchronize();decode=time.monotonic()-begin
            if len(frames)!=row['frames'] or any(f.shape!=(row['height'],row['width'],3) for f in frames):raise RuntimeError('FRAME_SHAPE')
            phase['phase']='export';folder=a.output/f'{i:02d}-frames';folder.mkdir();hashes=[]
            for j,f in enumerate(frames):Image.fromarray(f).save(folder/f'{j:02d}.png');hashes.append(hashlib.sha256(f.tobytes()).hexdigest())
            begin=time.monotonic();video=save_video(frames,a.output/f'{i:02d}-{row["case"]}.mp4',row['fps']);export=time.monotonic()-begin
            # Every frame, numbered; this is not a single representative thumbnail.
            tw=256;th=round(row['height']*tw/row['width']);sheet=Image.new('RGB',(tw*4,(th+22)*((len(frames)+3)//4)),(240,244,248));draw=ImageDraw.Draw(sheet)
            for j,f in enumerate(frames):
                im=Image.fromarray(f);im.thumbnail((tw,th));x=(j%4)*tw;y=(j//4)*(th+22);sheet.paste(im,(x,y));draw.text((x+4,y+th+3),f'{j:02d}',fill=(0,0,0))
            sheet.save(a.output/f'{i:02d}-review.jpg',quality=90)
            record={**row,'index':i,'seconds_encode_and_denoise':denoise,'seconds_decode':decode,'seconds_export':export,'frame_pixel_sha256':hashes,'video':video,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'frame_std':[float(x.std()) for x in frames],'mean_adjacent_abs_difference':[float(np.abs(x.astype(float)-y.astype(float)).mean()) for x,y in zip(frames,frames[1:])],'visual':'NOT_REVIEWED'};results.append(record);probe.write_json(a.output/'results.json',results);print(json.dumps({'generated':i,'seconds':denoise+decode,'video':video}),flush=True);del latent,decoded,frames;check()
        probe.write_json(a.output/'completion.json',{'generated':len(results),'repeat_same_pixels':results[1]['frame_pixel_sha256']==results[3]['frame_pixel_sha256'],'visual_acceptance':'PENDING_REVIEW','training_allowed':False})
    except BaseException as e:probe.write_json(a.output/'failure.json',{'error':type(e).__name__,'message':str(e)[:2000]});raise
    finally:stop.set();worker.join();probe.write_json(a.output/'telemetry.json',probe.summarize(samples))

if __name__=='__main__':main()
