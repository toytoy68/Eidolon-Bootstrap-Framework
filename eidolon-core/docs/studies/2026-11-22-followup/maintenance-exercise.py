# Eidolon Core Technologies (ECT) — isolated real-service maintenance exercise
from pathlib import Path
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import hashlib
import time
from core.backend.filesystem import FilesystemBackend
from core.backend.models import Memory
from core.indexing.runtime import load_runtime, open_index
from eidolon_core.maintenance_host import run_once
from eidolon_core.maintenance_policy import validate_host_policy

P = Path('/home/toytoy/followup-20261122/maintenance')
P.mkdir(mode=0o700)
root = P / 'corpus/memory/persistent'
backend = FilesystemBackend(root, P / 'corpus/memory/history')
sources = sorted(Path('/home/toytoy/eidolon-test-corpora/eidolon-corpus-fr-100-v1/documents').glob('*.txt'))[:12]
assert len(sources) == 12
ids = []
for i, source in enumerate(sources):
    identity = f'fixture-{i:03d}'
    backend.store(Memory(identity, content=source.read_text()[:1200]))
    ids.append(identity)
def digest():
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in root.rglob('*') if f.is_file() and f.name != '.write.lock'}
before = digest()
config = json.loads(Path('/home/toytoy/eidolon-beta-memory/index.json').read_text())
config['alias'] = 'eidolon_followup_20261122_passages'
config['num_ctx'] = 2048
config['max_input_chars'] = 16000
(P / 'index.json').write_text(json.dumps(config))
cfg = load_runtime(P / 'index.json')
index = open_index(cfg, create=True)
initial = asdict(index.status()); index.client.close()
state = P / 'state'; state.mkdir(mode=0o700)
runtime = dict(schema='eidolon-maintenance-runtime/1', canonical_root=str(root),
               state_directory=str(state), index_config=str(P / 'index.json'),
               profile_id='lab', allowed_information_ids=ids)
policy = validate_host_policy(dict(schema='eidolon-host-maintenance-policy/1',
    expected_source='host.eidolon', max_observation_age_seconds=120,
    max_load_age_seconds=120, load_unit='load1_per_cpu', load_limit=0.7))
def tick(at, **changes):
    obs = dict(source='host.eidolon', at=at.isoformat(),
        last_activity=(at-timedelta(hours=1)).isoformat(),
        boot_at=(at-timedelta(hours=2)).isoformat(),
        load=dict(observed_at=at.isoformat(), ratio=0.1, unit='load1_per_cpu'))
    obs.update(changes)
    return run_once(policy, obs, now=at, runtime=runtime)

started = time.time()
night = datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc)  # simulated 05:00 Paris
outside = tick(night + timedelta(hours=8))
assert outside['report']['state'] == 'DEFERRED'
assert 'OUTSIDE_WINDOW' in outside['report']['reasons']
published = tick(night)
assert published['report']['state'] == 'PUBLISHED'
assert published['report']['embedded_documents'] == 12
unchanged = tick(night)
assert unchanged['report']['state'] == 'UNCHANGED'
recent = tick(night, last_activity=night.isoformat())
assert recent['report']['state'] == 'DEFERRED'
busy = tick(night, load=dict(observed_at=night.isoformat(),ratio=1.0,unit='load1_per_cpu'))
assert busy['report']['state'] == 'DEFERRED'
obs = dict(source='host.eidolon', at=night.isoformat(),
    last_activity=(night-timedelta(hours=1)).isoformat(),
    boot_at=(night-timedelta(hours=2)).isoformat(),
    load=dict(observed_at=night.isoformat(),ratio=0.1,unit='load1_per_cpu'))
index = open_index(cfg); stable = asdict(index.status()); index.client.close()
def active_receipt():
    now = datetime.now(timezone.utc).isoformat()
    return dict(schema='eidolon-activity-receipt/1',source='host.eidolon',
                observed_at=now,last_activity=now)
try:
    run_once(policy, obs, now=night, runtime=runtime, activity_provider=active_receipt)
    raise AssertionError('live activity must abort sync')
except InterruptedError:
    interrupted = True
index = open_index(cfg); final = asdict(index.status()); index.client.close()
assert final == stable
assert digest() == before
result = dict(passed=True, real_qdrant=True, real_embeddings=True,
    simulated_schedule=True, production_modified=False, source='12 explicit 1200-character passage fixtures derived from synthetic French documents; original documents unmodified; full-length documents not qualified',
    canonical_unchanged=True, initial=initial, final=final, outside=outside,
    published=published, unchanged=unchanged, recent_activity=recent, busy=busy,
    live_activity_abort_preserves_alias=interrupted, seconds=time.time()-started,
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
(P / 'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
