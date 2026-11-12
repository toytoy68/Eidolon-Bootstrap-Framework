# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_service.py
# Description : Service média facultatif, file durable et moteur local dédié
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Experimental standalone media API. Does not import Core runtime or Memory.

Reuses Core's private artifact store, local HTTP, and Comfy output verification.
One process, one dedicated engine, one GPU. Unknown effects block admission;
no replay after a crash. Cooperative GPU checks cannot reserve against Eva or
Ollama clients which bypass this service. Deployment must retain that limitation.
"""
from __future__ import annotations
import argparse
import base64
import contextlib
import fcntl
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import threading
import time
import urllib.parse
import uuid

from .media_agents import MediaError, parse_json, read_regular
from .media_artifacts import ArtifactStore, initialize
from .media_backends import endpoint, json_http
from .media_http import exchange
from .media_outputs import descriptors
from .media_profiles import PROFILES, validate, workflow

TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELLED', 'REVIEW_REQUIRED'}

def gpu_probe(gpu_uuid, engine_pid):
    """Fail closed on missing telemetry or any other compute process (all GPUs)."""
    def smi(*args):
        return subprocess.check_output(['nvidia-smi', *args, '--format=csv,noheader,nounits'],
                                       text=True, timeout=4)
    rows = smi('--query-compute-apps=pid,gpu_uuid').strip().splitlines()
    if any(line.split(',')[0].strip() != str(engine_pid) for line in rows):
        return {'ready': False, 'reason': 'OTHER_GPU_CLIENT'}
    raw = smi('-i', gpu_uuid, '--query-gpu=memory.free,temperature.gpu,temperature.memory,power.draw')
    free, temp, hbm, watts = [float(v.strip()) for v in raw.strip().split(',')]
    return {'ready': free >= 2048 and temp < 65 and hbm < 70,
            'free_mib': free, 'gpu_c': temp, 'hbm_c': hbm, 'watts': watts}

def png(body):
    # Decode and re-encode locally: no embedded paths or arbitrary image format.
    from PIL import Image
    if len(body) > 8 * 1024 * 1024 or not body.startswith(b'\x89PNG\r\n\x1a\n'):
        raise MediaError('PNG_REQUIRED')
    with Image.open(io.BytesIO(body)) as im:
        if im.width > 2048 or im.height > 2048:
            raise MediaError('IMAGE_DIMENSIONS_EXCEEDED')
        out = io.BytesIO()
        im.convert('RGB').save(out, format='PNG')
    return out.getvalue()

class ComfyEngine:
    """Dedicated engine: no arbitrary paths/nodes or third-party endpoints."""
    def __init__(self, url, input_directory, gpu_uuid, engine_pid):
        self.url = endpoint(url)
        self.inputs = Path(input_directory)
        self.gpu_uuid, self.engine_pid = gpu_uuid, engine_pid

    def call(self, method, path, payload=None):
        return json_http(method, self.url + path, payload, timeout=10)

    def available(self):
        probe = gpu_probe(self.gpu_uuid, self.engine_pid)
        q = self.call('GET', '/queue')
        probe['ready'] = probe['ready'] and not q['queue_running'] and not q['queue_pending']
        return probe

    def stage(self, body):
        name = uuid.uuid4().hex + '.png'
        # Operator-owned directory; never accept a client filename.
        fd = os.open(self.inputs / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(png(body)); f.flush(); os.fsync(f.fileno())
        return name

    def submit(self, graph):
        r = self.call('POST', '/prompt', {'prompt': graph})
        if r.get('node_errors') or r.get('error') or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', r.get('prompt_id', '')):
            raise MediaError('INVALID_ENGINE_RECEIPT')
        return r['prompt_id']

    def poll(self, prompt_id):
        return self.call('GET', '/history/' + prompt_id)

    def cancel(self, prompt_id):
        q = self.call('GET', '/queue')
        running = [x[1] for x in q['queue_running']]
        pending = [x[1] for x in q['queue_pending']]
        if any(x != prompt_id for x in running + pending):
            raise MediaError('ENGINE_NOT_EXCLUSIVE')
        # ComfyUI 0.3.26 interrupt is global; dedicated instance is mandatory.
        if prompt_id in pending:
            exchange('POST', self.url + '/queue', json.dumps({'delete': [prompt_id]}).encode(),
                     {'Content-Type': 'application/json'}, 4096, timeout=5)
        if prompt_id in running:
            exchange('POST', self.url + '/interrupt', b'{}', {'Content-Type': 'application/json'}, 4096, timeout=5)
        return 'CANCEL_REQUESTED'  # never equate an HTTP ACK with a stopped task

    def collect(self, history, job):
        graph = job['graph']
        record = {'schema': 'media-job/1', 'id': 'media-'+job['id'], 'agent': PROFILES[job['request']['profile']]['kind'],
                  'operation': 'create', 'state': 'QUEUED', 'result': {'prompt_id': job['prompt_id']},
                  'backend': {'adapter': 'comfyui-prompt/2', 'endpoint': self.url,
                              'workflow_sha256': hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()}}
        refs = descriptors(history, record)
        if len(refs) != 1:
            raise MediaError('EXPECTED_ONE_OUTPUT')
        ref = refs[0]
        _, body = exchange('GET', self.url+'/view?'+urllib.parse.urlencode({k: ref[k] for k in ('filename','subfolder','type')}),
                           None, {}, 64*1024*1024, timeout=30)
        if ref['media_type'] == 'video/webm':
            # PyAV uses bundled FFmpeg; CPU H.264 export, no network subprocess.
            import av
            output = io.BytesIO()
            with av.open(io.BytesIO(body)) as src, av.open(output, 'w', format='mp4') as dst:
                stream = dst.add_stream('libx264', rate=job['request']['fps'])
                stream.width = job['request']['width']; stream.height = job['request']['height']
                stream.pix_fmt = 'yuv420p'; stream.options = {'crf': '18', 'threads': '2'}
                count = 0
                for frame in src.decode(video=0):
                    count += 1
                    if count > 25:
                        raise MediaError('FRAME_LIMIT')
                    frame.pts = None
                    for packet in stream.encode(frame): dst.mux(packet)
                for packet in stream.encode(): dst.mux(packet)
                if count != job['request']['frames']:
                    raise MediaError('FRAME_COUNT_MISMATCH')
            return output.getvalue(), 'result.mp4'
        return png(body), 'result.png'

class MediaService:
    def __init__(self, root, engine, *, enabled=('sd15-text', 'sd15-edit', 'sd15-inpaint'), clock=time.time):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=False, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise MediaError('PRIVATE_ROOT_REQUIRED')
        self.process_lock = os.open(self.root/'service.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db_path = self.root/'jobs.sqlite3'
        if db_path.is_symlink(): raise MediaError('SYMLINK_REFUSED')
        if not (self.root/'artifacts').exists(): initialize(self.root/'artifacts')
        self.artifacts = ArtifactStore(self.root/'artifacts')
        self.engine, self.clock, self.enabled = engine, clock, tuple(enabled)
        if not set(self.enabled) <= PROFILES.keys(): raise MediaError('UNKNOWN_PROFILE')
        self.lock = threading.RLock()
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        os.chmod(db_path, 0o600)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, idem TEXT UNIQUE, body TEXT NOT NULL)')
        self.db.commit()
        # Unknown submission/execution is retained, never automatically resent.
        for j in self.jobs():
            if j['state'] in {'SUBMITTING', 'RUNNING', 'CANCEL_REQUESTED', 'COLLECTING'}:
                j.update(state='REVIEW_REQUIRED', error='PROCESS_INTERRUPTED'); self.save(j)

    def close(self):
        self.db.close(); os.close(self.process_lock)

    def save(self, job):
        job['updated_at'] = self.clock()
        with self.db:
            self.db.execute('INSERT INTO jobs VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                            (job['id'], job['idempotency_key'], json.dumps(job, allow_nan=False)))

    def jobs(self):
        with self.lock:
            return [json.loads(x[0]) for x in self.db.execute('SELECT body FROM jobs ORDER BY rowid')]

    def get(self, job_id):
        with self.lock:
            row = self.db.execute('SELECT body FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None: raise MediaError('JOB_NOT_FOUND')
            return json.loads(row[0])

    def submit(self, request, key):
        req = validate(request)
        if req['profile'] not in self.enabled: raise MediaError('MODEL_NOT_ENABLED')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key):
            raise MediaError('IDEMPOTENCY_KEY_REQUIRED')
        with self.lock:
            jobs = self.jobs()
            for j in jobs:
                if j['idempotency_key'] == key:
                    if j['request'] != req: raise MediaError('IDEMPOTENCY_CONFLICT')
                    return j
            if len(jobs) >= 128: raise MediaError('QUEUE_CAPACITY')
            for field in ('source','mask'):
                if field in req: png(self.artifacts.read(req[field])[0])
            now = self.clock()
            j = dict(id=uuid.uuid4().hex, idempotency_key=key, request=req, state='WAITING',
                     created_at=now, updated_at=now, progress={'stage':'waiting'}, result=None)
            self.save(j); return j

    def cancel(self, job_id):
        with self.lock:
            j = self.get(job_id)
            if j['state'] == 'WAITING':
                j['state'] = 'CANCELLED'
            elif j['state'] == 'RUNNING':
                j['state'] = 'CANCEL_REQUESTED'; self.save(j)
                try: self.engine.cancel(j['prompt_id'])
                except Exception: j.update(state='REVIEW_REQUIRED', error='CANCEL_UNCERTAIN')
            self.save(j); return j

    def tick(self):
        with self.lock:
            jobs = self.jobs()
            if any(j['state'] == 'REVIEW_REQUIRED' for j in jobs): return
            active = next((j for j in jobs if j['state'] in {'RUNNING','CANCEL_REQUESTED'}), None)
            if active is not None:
                j = active
                try:
                    history = self.engine.poll(j['prompt_id'])
                    entry = history.get(j['prompt_id'])
                    if entry:
                        status = entry.get('status', {})
                        if status.get('status_str') == 'error':
                            interrupted = any(x[0] == 'execution_interrupted' for x in status.get('messages', []))
                            j.update(state='CANCELLED' if interrupted else 'FAILED', error='ENGINE_INTERRUPTED' if interrupted else 'ENGINE_FAILED')
                        elif status.get('completed') is True and status.get('status_str') == 'success':
                            j['state'] = 'COLLECTING'; self.save(j)
                            body, name = self.engine.collect(history, j)
                            result = self.artifacts.import_bytes(body, display_name=name)
                            j.update(state='SUCCEEDED', result=result, progress={'stage':'complete'},
                                     execution_seconds=self.clock()-j['started_at'])
                    if j['state'] not in TERMINAL and self.clock()-j['started_at'] > 1800:
                        j.update(state='REVIEW_REQUIRED', error='DEADLINE_ENGINE_MAY_STILL_RUN')
                    self.save(j)
                except Exception:
                    j.update(state='REVIEW_REQUIRED', error='ENGINE_OR_COLLECTION_UNCERTAIN'); self.save(j)
                return
            j = next((j for j in jobs if j['state'] == 'WAITING'), None)
            if j is None: return
            try:
                probe = self.engine.available()
                j['resource_observation'] = probe
                if not probe['ready']:
                    self.save(j); return
            except Exception:
                j['progress'] = {'stage':'waiting_for_engine_or_gpu'}; self.save(j); return
            # Durable intent BEFORE staging or POST. A failed POST may have effects.
            j.update(state='SUBMITTING', started_at=self.clock()); self.save(j)
            try:
                names = {}
                for field in ('source','mask'):
                    if field in j['request']:
                        names[field+'_name'] = self.engine.stage(self.artifacts.read(j['request'][field])[0])
                j['staged_inputs'] = names
                j['graph'] = workflow(j['request'], prefix=j['id'], **names)
                self.save(j)
                j['prompt_id'] = self.engine.submit(j['graph'])
                j.update(state='RUNNING', progress={'stage':'engine_running', 'fraction':None})
            except Exception:
                j.update(state='REVIEW_REQUIRED', error='SUBMISSION_UNCERTAIN')
            self.save(j)

    def public(self, job):
        # Private prompt/graph remain in local DB, never in routine status logs.
        return {k:v for k,v in job.items() if k not in {'request','graph','staged_inputs','idempotency_key'}}

def handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def setup(self):
            super().setup(); self.connection.settimeout(10)
        def send(self, status, value, content_type='application/json'):
            data = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(status); self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data)
        def dispatch(self):
            try:
                if self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
                    self.send(401, {'error':'UNAUTHORIZED'}); return
                if self.command == 'GET':
                    if self.path == '/health': self.send(200, {'service':'Eidolon-Media','experimental':True}); return
                    if self.path == '/v1/models': self.send(200, {k:PROFILES[k] for k in service.enabled}); return
                    if self.path == '/v1/jobs': self.send(200, [service.public(j) for j in service.jobs()]); return
                    m = re.fullmatch(r'/v1/jobs/([0-9a-f]{32})(/result|/metadata)?', self.path)
                    if not m: raise MediaError('NOT_FOUND')
                    j = service.get(m[1])
                    if m[2] == '/result':
                        if j['state'] != 'SUCCEEDED': raise MediaError('RESULT_NOT_READY')
                        body, meta = service.artifacts.read(j['result']['reference'])
                        self.send(200, body, meta['media_type']); return
                    self.send(200, j if m[2] == '/metadata' else service.public(j)); return
                if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
                    raise MediaError('JSON_REQUIRED')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isdigit(): raise MediaError('LENGTH_REQUIRED')
                size = int(lengths[0])
                if not 0 < size <= 12*1024*1024: raise MediaError('BODY_TOO_LARGE')
                data = self.rfile.read(size)
                if len(data) != size: raise MediaError('INCOMPLETE_BODY')
                value = parse_json(data)
                if self.path == '/v1/jobs':
                    j = service.submit(value, self.headers.get('Idempotency-Key'))
                    self.send(202, service.public(j)); return
                if self.path == '/v1/assets':
                    if type(value) is not dict or set(value) != {'png_base64'}: raise MediaError('INVALID_ASSET')
                    body = png(base64.b64decode(value['png_base64'], validate=True))
                    with service.lock: meta = service.artifacts.import_bytes(body, display_name='input.png')
                    self.send(201, meta['reference']); return
                m = re.fullmatch(r'/v1/jobs/([0-9a-f]{32})/cancel', self.path)
                if not m or value != {}: raise MediaError('NOT_FOUND')
                self.send(200, service.public(service.cancel(m[1])))
            except MediaError as e: self.send(400, {'error':e.code})
            except Exception: self.send(400, {'error':'REQUEST_FAILED'})
        do_GET = dispatch
        do_POST = dispatch
    return Handler

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True); p.add_argument('--token-file', required=True)
    p.add_argument('--engine', default='http://127.0.0.1:8189'); p.add_argument('--inputs', required=True)
    p.add_argument('--gpu-uuid', required=True); p.add_argument('--engine-pid', type=int, required=True)
    p.add_argument('--port', type=int, default=8190); p.add_argument('--enable', action='append', choices=PROFILES)
    a = p.parse_args(argv); os.umask(0o077)
    info = os.lstat(a.token_file)
    if info.st_uid != os.getuid() or info.st_mode & 0o077: raise MediaError('PRIVATE_TOKEN_REQUIRED')
    token = read_regular(a.token_file, 256).decode().strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token): raise MediaError('INVALID_TOKEN')
    engine = ComfyEngine(a.engine, a.inputs, a.gpu_uuid, a.engine_pid)
    service = MediaService(a.root, engine, enabled=a.enable or ('sd15-text','sd15-edit','sd15-inpaint'))
    stop = threading.Event()
    def work():
        while not stop.wait(0.5):
            try: service.tick()
            except Exception: stop.set()  # never silently retry an uncertain mutation
    worker = threading.Thread(target=work, daemon=True); worker.start()
    server = HTTPServer(('127.0.0.1', a.port), handler(service, token))
    try: server.serve_forever()
    finally:
        stop.set(); server.server_close(); worker.join(40); service.close()

if __name__ == '__main__': main()
