# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : display_probe.py
# Description : Recette matérielle des formats écran, résultats privés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import io
import json
from pathlib import Path
import time
import urllib.request
import uuid
from PIL import Image
from eidolon_core.media_service_client import LocalGenerationClient

def main():
    import argparse
    import av
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    root=a.root;out=root/('display-probe-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(mode=0o700)
    c=LocalGenerationClient('http://127.0.0.1:8190',(root/'token').read_text().strip())
    results=[];sources={}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for profile in ('sd15-text','wan21-text','svd-image'):
        for format in ('16:9','4:3-pillarbox'):
            q=json.load(opener.open('http://127.0.0.1:8189/queue'))
            assert not q['queue_running'] and not q['queue_pending']
            free=urllib.request.Request('http://127.0.0.1:8189/free',data=b'{"unload_models":true,"free_memory":true}',headers={'Content-Type':'application/json'})
            opener.open(free).close()
            r={'profile':profile,'format':format,'output_size':'1080p','seed':42,
               'steps':12 if profile=='sd15-text' else 6,
               'prompt':'A small red sailboat moving slowly on a blue lake, distant mountains, daylight'}
            if profile!='sd15-text':r.update(frames=5,fps=8)
            if profile=='svd-image':r['source']=sources[format]
            start=time.monotonic();j=c.submit(r,idempotency_key=uuid.uuid4().hex)
            while j['state'] not in ('SUCCEEDED','FAILED','CANCELLED','REVIEW_REQUIRED'):
                if time.monotonic()-start>600:raise TimeoutError('job not complete; inspect before retry')
                time.sleep(.3);j=c.status(j['id'])
            assert j['state']=='SUCCEEDED',j
            elapsed=time.monotonic()-start;body,mime=c.result(j['id'])
            name=profile+'-'+format.replace(':','-');(out/(name+('.png' if mime=='image/png' else '.mp4'))).write_bytes(body)
            metadata=c.metadata(j['id']);(out/(name+'-metadata.json')).write_text(json.dumps(metadata,indent=2))
            if mime=='image/png':
                im=Image.open(io.BytesIO(body)).convert('RGB');frames=1
                if format=='4:3-pillarbox':
                    src=im.crop((240,0,1680,1080))
                else:src=im
                data=io.BytesIO();src.save(data,format='PNG');sources[format]=c.upload_png(data.getvalue())
            else:
                with av.open(io.BytesIO(body)) as container:
                    track=container.streams.video[0]
                    assert track.average_rate==8
                    assert abs(float(track.duration*track.time_base)-5/8)<.001
                    frames=0
                    for frame in container.decode(video=0):
                        frames+=1;im=frame.to_image()
                        assert im.size==(1920,1080)
                        if format=='4:3-pillarbox':
                            assert max(x[1] for x in im.crop((0,0,232,1080)).getextrema())<=3
                            assert max(x[1] for x in im.crop((1688,0,1920,1080)).getextrema())<=3
                    assert frames==5
            assert im.size==(1920,1080)
            if mime=='image/png' and format=='4:3-pillarbox':
                assert im.crop((0,0,240,1080)).getbbox() is None
                assert im.crop((1680,0,1920,1080)).getbbox() is None
            row={'profile':profile,'format':format,'output_size':[1920,1080],
                 'generation_size':[metadata['request']['width'],metadata['request']['height']],
                 'frames':frames,'seconds':elapsed,'state':j['state'],
                 'bars_verified':format=='4:3-pillarbox','quality_assessment':False}
            results.append(row);(out/'summary.json').write_text(json.dumps(results,indent=2))
            print(json.dumps(row),flush=True)
    print('proof_directory',out,flush=True)

if __name__=='__main__':main()
