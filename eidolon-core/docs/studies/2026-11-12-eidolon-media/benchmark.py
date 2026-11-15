# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : benchmark.py
# Description : Recette API locale avec mesures réelles, sans simulation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit operator benchmark. Only literal localhost endpoints are contacted.

Run with read access to telemetry snapshots for wall energy (otherwise null).
This script never starts/stops production services or changes GPU settings.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import uuid

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--suite',choices=['image','video','svd','release'],required=True)
    a = p.parse_args()
    token = (a.root/'token').read_text().strip()
    out = a.root/('benchmark-'+a.suite+'-'+time.strftime('%Y%m%d-%H%M%S'))
    out.mkdir(mode=0o700)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def api(path, data=None, key=None):
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        if key: headers['Idempotency-Key']=key
        req=urllib.request.Request('http://127.0.0.1:8190'+path,
            data=None if data is None else json.dumps(data).encode(),headers=headers)
        with opener.open(req,timeout=20) as r:
            body=r.read()
            return json.loads(body) if r.headers.get_content_type()=='application/json' else body
    def snapshot():
        d={'ts':time.time()}
        raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,power.draw,temperature.gpu,temperature.memory,utilization.gpu',
                                     '--format=csv,noheader,nounits'],text=True,timeout=4)
        d['gpu']=[x.split(', ') for x in raw.strip().splitlines()]
        for kind,file in [('power','power.json'),('host','status.json')]:
            try:d[kind]=json.loads((Path('/var/lib/eidolon-hwmon')/file).read_text().rstrip('\\n'))
            except (OSError,ValueError):d[kind]=None
        return d
    def run(name,request):
        # Explicit cache reset on this dedicated, idle engine makes repeats genuine.
        q=json.load(opener.open('http://127.0.0.1:8189/queue'))
        assert not q['queue_running'] and not q['queue_pending']
        req=urllib.request.Request('http://127.0.0.1:8189/free',data=b'{"unload_models":true,"free_memory":true}',headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=10) as r:r.read()
        time.sleep(2)
        before=snapshot();start=time.monotonic()
        job=api('/v1/jobs',request,'bench-'+uuid.uuid4().hex)
        samples=[]
        while True:
            samples.append(snapshot())
            job=api('/v1/jobs/'+job['id'])
            samples[-1]['progress']=job.get('progress')
            if job['state'] in ['SUCCEEDED','FAILED','REVIEW_REQUIRED','CANCELLED']:break
            if time.monotonic()-start>1900:raise TimeoutError('engine may still run')
            time.sleep(0.5)
        elapsed=time.monotonic()-start;after=snapshot()
        report={'name':name,'request':request,'job':job,'elapsed_seconds':elapsed,'before':before,'after':after,'samples':samples}
        report['metadata']=api('/v1/jobs/'+job['id']+'/metadata')
        if job['state']=='SUCCEEDED':
            body=api('/v1/jobs/'+job['id']+'/result')
            suffix='.mp4' if request['profile'] in ['wan21-text','svd-image'] else '.png'
            (out/(name+suffix)).write_bytes(body)
            report['sha256']=hashlib.sha256(body).hexdigest()
            if suffix=='.png':
                from PIL import Image,ImageStat
                im=Image.open(io.BytesIO(body));im.load()
                report['image']={'size':im.size,'extrema':im.getextrema(),'stddev':ImageStat.Stat(im).stddev,'pixels_sha256':hashlib.sha256(im.tobytes()).hexdigest()}
            else:
                import av,numpy as np
                frames=[]
                with av.open(io.BytesIO(body)) as c:
                    report['video']={'codec':c.streams.video[0].codec_context.name,'fps':str(c.streams.video[0].average_rate)}
                    for frame in c.decode(video=0):frames.append(frame.to_ndarray(format='rgb24'))
                report['video'].update(frames=len(frames),width=frames[0].shape[1],height=frames[0].shape[0],
                    frame_stddev=[float(x.std()) for x in frames],
                    mean_frame_change=float(np.mean([np.abs(x.astype(float)-y.astype(float)).mean() for x,y in zip(frames,frames[1:])])))
                from PIL import Image
                Image.fromarray(frames[0]).save(out/(name+'-first.png'))
                Image.fromarray(frames[-1]).save(out/(name+'-last.png'))
        (out/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'name':name,'state':job['state'],'seconds':elapsed,'id':job['id'],'file':str(out/name)}),flush=True)
        assert job['state']=='SUCCEEDED',job
        return body,report
    if a.suite=='image':
        request={'profile':'sd15-text','prompt':'A small red wooden cabin beside a lake, snowy mountains, sunrise, detailed photograph','width':512,'height':512,'steps':20,'seed':42}
        body,first=run('text',request)
        _,second=run('repeat',request)
        print('pixel_repeat_equal',first['image']['pixels_sha256']==second['image']['pixels_sha256'],flush=True)
        source=api('/v1/assets',{'png_base64':base64.b64encode(body).decode()})
        run('edit',dict(request,profile='sd15-edit',prompt='A blue wooden cabin beside a lake, snowy mountains, sunrise, detailed photograph',source=source,denoise=0.65))
        from PIL import Image,ImageDraw
        mask=Image.new('RGB',(512,512));ImageDraw.Draw(mask).rectangle((100,200,430,430),fill='white')
        b=io.BytesIO();mask.save(b,format='PNG');ref=api('/v1/assets',{'png_base64':base64.b64encode(b.getvalue()).decode()})
        run('inpaint',dict(request,profile='sd15-inpaint',prompt='A blue wooden cabin beside a lake, snowy mountains',source=source,mask=ref,denoise=0.85))
    elif a.suite=='video':
        request={'profile':'wan21-text','prompt':'A small red sailboat slowly crossing a calm blue lake, mountains in the background, static camera, gentle ripples','width':320,'height':256,'frames':9,'fps':8,'steps':10,'seed':42}
        run('wan-smoke',request)
        run('wan-repeat',request)
        run('wan-17',dict(request,frames=17,steps=20))
    elif a.suite=='svd':
        source_path=a.root/'engine/output/firstimage_00001_.png'
        source=api('/v1/assets',{'png_base64':base64.b64encode(source_path.read_bytes()).decode()})
        request={'profile':'svd-image','prompt':'','source':source,'width':320,'height':256,'frames':14,'fps':7,'steps':15,'seed':42}
        run('svd-14',request)
        run('svd-repeat',request)
    else:
        request={'profile':'sd15-text','checkpoint':'sd15-base','prompt':'A small red wooden cabin beside a lake, snowy mountains, sunrise, detailed photograph','width':512,'height':512,'steps':20,'seed':42}
        body,_=run('registered-image',request)
        source=api('/v1/assets',{'png_base64':base64.b64encode(body).decode()})
        from PIL import Image,ImageDraw
        mask=Image.new('RGB',(512,512));ImageDraw.Draw(mask).rectangle((100,200,430,430),fill='white')
        b=io.BytesIO();mask.save(b,format='PNG');ref=api('/v1/assets',{'png_base64':base64.b64encode(b.getvalue()).decode()})
        edited,_=run('masked-edit',dict(request,profile='sd15-inpaint',prompt='An empty calm blue lake, no buildings, reflections of snowy mountains',source=source,mask=ref,denoise=0.85))
        import numpy as np
        outside=np.array(mask)[:,:,0]==0
        same=bool(np.array_equal(np.array(Image.open(io.BytesIO(body)))[outside],np.array(Image.open(io.BytesIO(edited)))[outside]))
        (out/'mask-preservation.json').write_text(json.dumps({'outside_mask_pixels_equal':same}))
        assert same,'unmasked pixels changed'
        run('wan-final',{'profile':'wan21-text','prompt':'A small red sailboat slowly crossing a calm blue lake, mountains in the background, static camera, gentle ripples','width':320,'height':256,'frames':17,'fps':8,'steps':20,'seed':42})
        run('svd-final',{'profile':'svd-image','prompt':'','source':source,'width':320,'height':256,'frames':14,'fps':7,'steps':15,'seed':42})

if __name__=='__main__':main()
