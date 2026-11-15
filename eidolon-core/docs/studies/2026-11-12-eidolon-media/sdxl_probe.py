# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sdxl_probe.py
# Description : Comparaison locale SDXL, répétitions et sondes réelles
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
import uuid
from PIL import Image
from eidolon_core.media_service_client import LocalGenerationClient

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--request-file',type=Path,required=True);a=p.parse_args()
    prior=json.loads(a.request_file.read_text())['summary']['request']
    request={k:v for k,v in prior.items() if k not in ('width','height')}
    request.update(profile='sdxl-text',format='16:9',output_size='native')
    c=LocalGenerationClient('http://127.0.0.1:8190',(a.root/'token').read_text().strip())
    out=a.root/('sdxl-probe-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(mode=0o700)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    summaries=[]
    for attempt in range(2):
        assert all(j['state'] in ('SUCCEEDED','FAILED','CANCELLED') for j in c._call('GET','/v1/jobs'))
        q=json.load(opener.open('http://127.0.0.1:8189/queue'))
        assert not q['queue_running'] and not q['queue_pending']
        free=urllib.request.Request('http://127.0.0.1:8189/free',data=b'{"unload_models":true,"free_memory":true}',headers={'Content-Type':'application/json'})
        opener.open(free).close()
        fields=['index','name','memory.used','utilization.gpu','power.draw','temperature.gpu','temperature.memory','power.limit']
        samples=[];stop=threading.Event()
        def sample():
            while not stop.is_set():
                try:
                    raw=subprocess.check_output(['nvidia-smi','--query-gpu='+','.join(fields),'--format=csv,noheader,nounits'],text=True,timeout=3)
                    data={'time':time.time(),'gpus':[dict(zip(fields,[x.strip() for x in l.split(',')])) for l in raw.strip().splitlines()]}
                    for h in Path('/sys/class/hwmon').glob('hwmon*'):
                        if (h/'name').read_text().strip()=='k10temp':
                            for label in h.glob('temp*_label'):
                                if label.read_text().strip()=='Tdie':
                                    data['cpu_tdie_c']=float(label.with_name(label.name.replace('_label','_input')).read_text())/1000
                    samples.append(data)
                except Exception as e:samples.append({'error':type(e).__name__})
                stop.wait(.2)
        t=threading.Thread(target=sample);start=time.monotonic();t.start()
        try:
            j=c.submit(request,idempotency_key=uuid.uuid4().hex)
            while j['state'] not in ('SUCCEEDED','FAILED','CANCELLED','REVIEW_REQUIRED'):
                if time.monotonic()-start>300:raise TimeoutError('inspect active job; do not replay')
                time.sleep(.2);j=c.status(j['id'])
            elapsed=time.monotonic()-start
        finally:
            stop.set();t.join();(out/f'{attempt}-samples.json').write_text(json.dumps(samples,indent=2))
        assert j['state']=='SUCCEEDED',j
        body,mime=c.result(j['id']);assert mime=='image/png'
        with Image.open(io.BytesIO(body)) as im:
            assert im.size==(1024,576);im.load()
        (out/f'{attempt}.png').write_bytes(body)
        (out/f'{attempt}-metadata.json').write_text(json.dumps(c.metadata(j['id']),indent=2))
        summary={'attempt':attempt,'state':j['state'],'seconds_wall':elapsed,
                 'seconds_service':j.get('execution_seconds'),'samples':len(samples),
                 'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),
                 'generation_size':[1024,576],'steps':request['steps'],'seed':request['seed'],'gpus':[]}
        for index in ('0','1','2'):
            rows=[g for s in samples if 'gpus' in s for g in s['gpus'] if g['index']==index]
            if not rows:continue
            result={'index':index,'name':rows[0]['name']}
            for field in fields[2:]:
                values=[]
                for g in rows:
                    try:values.append(float(g[field]))
                    except ValueError:pass
                if values:result[field]={'min':min(values),'max':max(values)}
            summary['gpus'].append(result)
        cpu=[s['cpu_tdie_c'] for s in samples if 'cpu_tdie_c' in s]
        if cpu:summary['cpu_tdie_c']={'min':min(cpu),'max':max(cpu)}
        summaries.append(summary);(out/'summary.json').write_text(json.dumps(summaries,indent=2))
        print(json.dumps(summary),flush=True)
    print(json.dumps({'directory':str(out),'repeat_identical':summaries[0]['sha256']==summaries[1]['sha256']}),flush=True)

if __name__=='__main__':main()
