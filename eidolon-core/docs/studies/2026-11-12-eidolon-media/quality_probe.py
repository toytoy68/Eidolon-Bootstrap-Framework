# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : quality_probe.py
# Description : Campagne qualité bornée, traçable, sans reprise automatique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Public synthetic cases only; file validity is never visual acceptance."""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
import uuid

from PIL import Image
from eidolon_core.media_profiles import validate, workflow
from eidolon_core.media_service import gpu_probe
from eidolon_core.media_service_client import LocalGenerationClient

GPU = 'GPU-c9d9173f-6303-6998-7a60-a379b9a0d60b'
MODEL_SHA = '31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b'
TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELLED'}
CASES = {
    'control': ('Studio photograph of one red ceramic mug on a grey table. '
                'One handle on the right, whole mug visible, soft side lighting.'),
    'hand': ('Studio photograph of one adult human hand, open palm facing the camera, '
             'five separated digits, wrist at the bottom, fingertips upwards, grey background.'),
    'katana': ('Studio product photograph of one luxury Japanese katana and its black lacquer '
               'scabbard lying separately side by side on grey fabric. Entire curved blade '
               'and entire scabbard visible, gold fittings, top-down view.'),
}
FIELDS = ['index', 'uuid', 'memory.used', 'utilization.gpu', 'power.draw',
          'temperature.gpu', 'temperature.memory', 'power.limit']

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def plan():
    result = []
    # Counterbalance first/second geometry across seeds; no winner selection.
    for case, prompt in CASES.items():
        for seed_index, seed in enumerate((104729, 130363)):
            heights = (576, 1024) if seed_index == 0 else (1024, 576)
            for height in heights:
                request = validate(dict(profile='sdxl-text', prompt=prompt, seed=seed,
                                        steps=30, width=1024, height=height))
                result.append(dict(case=case, request=request,
                                   expected_graph=workflow(request, prefix='qualityprobe')))
    return result

def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    tmp.replace(path)

def assert_idle(client, opener):
    jobs = client._call('GET', '/v1/jobs')
    if any(j['state'] not in TERMINAL for j in jobs):
        raise RuntimeError('NONTERMINAL_JOB: inspect before continuing')
    with opener.open('http://127.0.0.1:8189/queue', timeout=5) as response:
        q = json.load(response)
    if q['queue_running'] or q['queue_pending']:
        raise RuntimeError('ENGINE_BUSY')
    return len(jobs)

def free_cache(opener):
    req = urllib.request.Request('http://127.0.0.1:8189/free',
        data=b'{"unload_models":true,"free_memory":true}',
        headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=5):
        pass

def graph_matches(actual, expected):
    # The service's per-job output prefix is intentionally unique.
    actual = json.loads(json.dumps(actual))
    actual['7']['inputs']['filename_prefix'] = 'qualityprobe'
    return actual == expected

def sample_once():
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu='+','.join(FIELDS),
        '--format=csv,noheader,nounits'], text=True, timeout=4)
    item = {'monotonic': time.monotonic(), 'utc_epoch': time.time(),
            'gpus': [dict(zip(FIELDS, [x.strip() for x in line.split(',')]))
                     for line in raw.strip().splitlines()]}
    for h in Path('/sys/class/hwmon').glob('hwmon*'):
        if (h/'name').read_text().strip() == 'k10temp':
            for label in h.glob('temp*_label'):
                if label.read_text().strip() == 'Tdie':
                    item['cpu_tdie_c'] = float(label.with_name(label.name.replace('_label', '_input')).read_text()) / 1000
    return item

def summarize(samples):
    result = {'sample_errors': sum('error' in s for s in samples), 'gpus': {}}
    for index in ('0', '1', '2'):
        rows = [g for s in samples for g in s.get('gpus', []) if g['index'] == index]
        measures = {}
        for field in FIELDS[2:]:
            values = []
            for row in rows:
                try: values.append(float(row[field]))
                except ValueError: pass
            measures[field] = {'min': min(values), 'max': max(values)} if values else None
        result['gpus'][index] = measures
    values = [s['cpu_tdie_c'] for s in samples if 'cpu_tdie_c' in s]
    result['cpu_tdie_c'] = {'min': min(values), 'max': max(values)} if values else None
    return result

def run_one(client, entry, folder, key, *, timeout=180):
    folder.mkdir(mode=0o700)
    # Durable intent BEFORE POST; ambiguous outcome never automatically replayed.
    write_json(folder/'intent.json', {'idempotency_key': key, **entry})
    samples = []; stop = threading.Event()
    def collect():
        with (folder/'samples.jsonl').open('w', buffering=1) as log:
            while not stop.is_set():
                try: row = sample_once()
                except Exception as exc: row = {'error': type(exc).__name__, 'monotonic': time.monotonic()}
                samples.append(row); log.write(json.dumps(row)+'\n')
                stop.wait(.25)
    thread = threading.Thread(target=collect)
    thread.start(); started = time.monotonic(); job = None
    try:
        job = client.submit(entry['request'], idempotency_key=key)
        write_json(folder/'receipt.json', job)
        while job['state'] not in TERMINAL | {'REVIEW_REQUIRED'}:
            if time.monotonic() - started > timeout:
                client.cancel(job['id'])
                raise TimeoutError('Campaign stopped; inspect cancellation before another launch')
            time.sleep(.25); job = client.status(job['id'])
        elapsed = time.monotonic() - started
        write_json(folder/'terminal.json', job)
        if job['state'] != 'SUCCEEDED':
            raise RuntimeError('GENERATION_' + job['state'])
        metadata = client.metadata(job['id'])
        write_json(folder/'metadata.json', metadata)
        if not graph_matches(metadata['graph'], entry['expected_graph']):
            raise RuntimeError('EXECUTED_GRAPH_MISMATCH')
        body, mime = client.result(job['id'])
        if mime != 'image/png': raise RuntimeError('UNEXPECTED_MIME')
        with Image.open(io.BytesIO(body)) as image:
            image.load()
            if image.size != (entry['request']['width'], entry['request']['height']):
                raise RuntimeError('UNEXPECTED_GEOMETRY')
        (folder/'result.png').write_bytes(body)
        return dict(case=entry['case'], seed=entry['request']['seed'],
                    size=[entry['request']['width'], entry['request']['height']],
                    seconds_wall=elapsed, seconds_service=job.get('execution_seconds'),
                    sha256=hashlib.sha256(body).hexdigest(), technical='PASS',
                    visual='NOT_REVIEWED', telemetry=summarize(samples))
    except BaseException as exc:
        write_json(folder/'interruption.json', {'error': type(exc).__name__,
                   'job_id': job['id'] if job else None, 'automatic_replay': False})
        raise
    finally:
        stop.set(); thread.join()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--engine-pid', type=int, required=True)
    a = p.parse_args(); os.umask(0o077)
    with (a.root/'quality-campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Existing directory is refused, including interrupted campaigns.
        a.output.mkdir(mode=0o700)
        c = LocalGenerationClient('http://127.0.0.1:8190', (a.root/'token').read_text().strip())
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        count = assert_idle(c, opener)
        entries = plan()
        if count + len(entries) > 128: raise RuntimeError('INSUFFICIENT_QUEUE_CAPACITY')
        model = a.root/'engine/models/checkpoints/sd_xl_base_1.0.safetensors'
        with model.open('rb') as f: model_sha = hashlib.file_digest(f, 'sha256').hexdigest()
        if model_sha != MODEL_SHA: raise RuntimeError('MODEL_HASH_MISMATCH')
        cmdline = Path(f'/proc/{a.engine_pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
        if str(a.root/'engine/main.py') not in cmdline: raise RuntimeError('ENGINE_PID_MISMATCH')
        snapshot = {'model_sha256': model_sha, 'engine_cmdline': cmdline,
                    'plan_sha256': digest(entries), 'plan': entries,
                    'cache_policy': 'unload Comfy models before each trial; OS cache unchanged'}
        for name, cwd in [('source', a.root/'source'), ('engine', a.root/'engine')]:
            snapshot[name+'_head'] = subprocess.check_output(['git', '-C', str(cwd), 'rev-parse', 'HEAD'], text=True).strip()
        snapshot['runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        snapshot['python_packages'] = subprocess.check_output([os.sys.executable, '-m', 'pip', 'freeze'], text=True).splitlines()
        write_json(a.output/'manifest.json', snapshot)
        results = []; campaign = uuid.uuid4().hex
        for i, entry in enumerate(entries):
            assert_idle(c, opener)
            if not gpu_probe(GPU, a.engine_pid)['ready']: raise RuntimeError('GPU_NOT_AVAILABLE')
            free_cache(opener)
            result = run_one(c, entry, a.output/f'{i:02}', f'quality-{campaign}-{i}')
            results.append(result); write_json(a.output/'summary.json', results)
            print(json.dumps({'trial': i, **result}), flush=True)
        assert_idle(c, opener); free_cache(opener)
        write_json(a.output/'completion.json', {'technical_completed': len(results), 'visual_validation': False})

if __name__ == '__main__': main()
