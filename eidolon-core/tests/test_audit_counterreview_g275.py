# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_audit_counterreview_g275.py
# Description : Independent G274 counter-review, failures and boundary invariants
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import json
import math
import os
from pathlib import Path
import random
import signal
import sqlite3
import subprocess
import sys
import time

import pytest
from eidolon_core import library_sync as L
from eidolon_core.dialogue import Dialogue, recall_query
from eidolon_core.gpu_queue import Queue
from eidolon_core.identity_evaluation import evaluate
from eidolon_core.offline_state import database
from tests.test_offline_services_g273 import library, dataset


def test_recall_keeps_end_word_boundary_and_never_changes_turn():
    original = 'Ancien contexte.\n' * 80 + 'La question finale concerne le NAS.\t'
    query = recall_query(original)
    assert query.endswith('La question finale concerne le NAS.') and len(query) <= 500
    assert original.endswith('\t') and '\n' in original
    assert all(ord(c) >= 32 and ord(c) != 127 for c in query)
    class NeverMemory:
        def recall(self, _): raise AssertionError('empty query sent')
    d = Dialogue(None, None, None, memory=NeverMemory())
    assert d._recall('\x7f\n\t') == (None, [], 'EMPTY_RECALL_QUERY')


@pytest.mark.parametrize('change', ['rewrite', 'replace', 'hardlink'])
def test_large_file_changed_during_scan_preserves_previous_generation(tmp_path, monkeypatch, change):
    lib, root = library(tmp_path); lib.scan('pc0', 'nas'); before = lib.page('pc0', 'nas')
    big = root/'large.pdf'; big.write_bytes(b'X' * (L.documents.MAX_BYTES + 1))
    actual = L.inventory; calls = 0
    def inventory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == 'rewrite':
                with big.open('r+b') as f: f.write(b'Y')
            elif change == 'replace':
                replacement = tmp_path/'replacement'; replacement.write_bytes(big.read_bytes()); replacement.replace(big)
            else: os.link(big, tmp_path/'other-link')
        return actual(*args, **kwargs)
    monkeypatch.setattr(L, 'inventory', inventory)
    with pytest.raises(ValueError): lib.scan('pc0', 'nas')
    assert lib.page('pc0', 'nas') == before


def test_nonextractible_file_recovers_without_old_excerpt_becoming_current(tmp_path):
    lib, root = library(tmp_path); lib.scan('pc0', 'nas')
    note = root/'note.txt'; note.write_bytes(b'')
    result = lib.scan('pc0', 'nas')
    assert result['not_extracted'] == {'DOCUMENT_SIZE_INVALID': 1}
    row = lib.page('pc0', 'nas')['entries'][0]
    assert row['present'] == 1 and not row['excerpt_available']
    assert row['extraction_error'] == 'DOCUMENT_SIZE_INVALID'
    with database(lib.directory, 'library.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM versions').fetchone()[0] == 1
    note.write_text('Readable replacement')
    assert lib.scan('pc0', 'nas')['new_versions'] == 1
    row = lib.page('pc0', 'nas')['entries'][0]
    assert row['excerpt_available'] and row['extraction_error'] is None
    assert lib.page('pc1', 'nas')['entries'] == []


def test_large_files_are_metadata_only_and_old_schema_reads_without_mutation(tmp_path, monkeypatch):
    lib, root = library(tmp_path); lib.scan('pc0', 'nas')
    with database(lib.directory, 'library.sqlite3', write=True) as db: db.execute('DROP TABLE extraction_errors')
    state = Path(lib.directory)/'library.sqlite3'; before = state.read_bytes()
    assert lib.page('pc0', 'nas')['entries'][0]['excerpt_available']
    assert state.read_bytes() == before
    big = root/'large.pdf'
    with big.open('wb') as f: f.truncate(L.documents.MAX_BYTES + 1)
    original = L.profile_files.read_bytes
    def bounded(root, relative, **kwargs):
        assert relative != 'large.pdf'
        return original(root, relative, **kwargs)
    monkeypatch.setattr(L.profile_files, 'read_bytes', bounded)
    assert lib.scan('pc0', 'nas')['not_extracted'] == {'FILE_TOO_LARGE': 1}
    row = next(x for x in lib.page('pc0', 'nas')['entries'] if x['path'] == 'large.pdf')
    assert row['sha'] is None and not row['excerpt_available'] and row['extraction_error'] == 'FILE_TOO_LARGE'


def test_special_file_refused_without_reading(tmp_path):
    lib, root = library(tmp_path); lib.scan('pc0', 'nas'); before = lib.page('pc0', 'nas')
    os.mkfifo(root/'pipe.txt')
    with pytest.raises(ValueError, match='SPECIAL'): lib.scan('pc0', 'nas')
    assert lib.page('pc0', 'nas') == before


def queue(tmp_path):
    tmp_path.chmod(0o700)
    return Queue(dict(schema='eidolon-gpu-queue/1',directory=str(tmp_path),capacity_mib=100,resident_mib=10,dialogue_mib=40,media_mib=80))


def test_withdraw_never_releases_committed_admission(tmp_path, monkeypatch):
    q=queue(tmp_path); acquire=q.acquire
    def ambiguous(key):
        acquire(key)
        raise OSError('synthetic response lost after commit')
    monkeypatch.setattr(q, 'acquire', ambiguous)
    with pytest.raises(OSError): q.wait('first', 'dialogue')
    r=q.inspect(); assert r['counts']['ACTIVE']==1 and r['reserved_mib']==40
    assert r['review_required'] and not r['live_owners_checked']
    restarted=Queue(q.config)
    assert restarted.inspect()['jobs'][0]['state']=='ACTIVE'


def test_withdraw_failure_preserves_original_error_and_reports_uncertainty(tmp_path, monkeypatch):
    q=queue(tmp_path)
    failure=RuntimeError('original failure')
    def refuse(*_): raise failure
    monkeypatch.setattr(q, 'acquire', refuse)
    monkeypatch.setattr(q, '_withdraw', lambda _: False)
    with pytest.raises(RuntimeError) as caught: q.wait('failed', 'dialogue')
    assert caught.value is failure and 'GPU_WAITING_REVIEW_REQUIRED' in failure.__notes__[0]
    assert q.inspect()['counts']['WAITING']==1
    q.cancel_waiting('failed'); assert not q.inspect()['review_required']


def test_gpu_inventory_counts_all_reservations_even_when_listing_truncated(tmp_path):
    q=queue(tmp_path)
    with q.db(True) as db:
        db.executemany("INSERT INTO jobs VALUES (?, 'dialogue', 1, 1, 'UNKNOWN', 'lease', NULL)", [(str(i),) for i in range(1002)])
    r=q.inspect()
    assert r['jobs_truncated'] and len(r['jobs'])==1000
    assert r['counts']['UNKNOWN']==r['reserved_mib']==1002
    assert r['available_mib']==-912  # an impossible-overcommit state must not look free


def test_calibration_matches_independent_exhaustive_selection_and_holdout():
    rng=random.Random(275)
    for _ in range(100):
        data=dataset()
        calibration=[r for r in data['trials'] if r['split']=='calibration']
        for r in calibration:r['score']=rng.choice([-1., -.4, 0., .5, math.nextafter(.5, 1.), .9, 1.])
        target=rng.choice([0., .5])
        scores=sorted({r['score'] for r in calibration})
        candidates=set(scores + [math.nextafter(s, math.inf) for s in scores if s<1])
        eligible=[]
        for t in candidates:
            fp=sum(not r['genuine'] and r['score']>=t for r in calibration)
            fn=sum(r['genuine'] and r['score']<t for r in calibration)
            if fp/2<=target:eligible.append((fn,-t))
        report=evaluate(data,max_far=target)
        if not eligible:
            assert report['state']=='NO_THRESHOLD';continue
        fn, neg_t=min(eligible);t=-neg_t
        if t in scores:
            lower=max([s for s in scores if s<t],default=-1.)
            proposed=t-.15*(t-lower)
            if lower<proposed<=t:t=proposed
        assert report['candidate_threshold']==t
        assert report['calibration']['false_rejects']==fn and report['calibration']['far']<=target
        changed=copy.deepcopy(data)
        for r in changed['trials']:
            if r['split']=='validation':r['score']=rng.choice([-1.,1.])
        assert evaluate(changed,max_far=target)['candidate_threshold']==t
        assert not report['activated']


def test_real_sigterm_runs_context_cleanup_and_keeps_gpu_reservations(tmp_path):
    from eidolon_core.store import Store
    from eidolon_core.runtime import Runtime
    from eidolon_core.memory import DEMO_REQUEST
    state=Store(tmp_path/'state');Runtime(state).create(DEMO_REQUEST)
    token=tmp_path/'token';token.write_text('t'*40);token.chmod(0o600)
    gpu=tmp_path/'gpu';gpu.mkdir(mode=0o700);q=queue(gpu);q.enqueue('prior','media');q.acquire('prior');q.enqueue('inherited','dialogue')
    config=tmp_path/'gpu.json';config.write_text(json.dumps(q.config))
    marker=tmp_path/'closed';output=tmp_path/'output'
    script='''import sys
from pathlib import Path
from eidolon_core import http_api
import threading,time
init=http_api.ReadServer.__init__
def start(self,*args,**kwargs):
    init(self,*args,**kwargs)
    q=self.gpu_queue
    def pending():
        try:q.wait('owned','dialogue')
        except Exception:pass
    threading.Thread(target=pending,daemon=True).start()
    until=time.monotonic()+5
    while not any(r['id']=='owned' for r in q.inspect()['jobs']) and time.monotonic()<until:time.sleep(.01)
http_api.ReadServer.__init__=start
original=http_api.ReadServer.server_close
def close(self):
    original(self)
    Path(sys.argv[1]).write_text('closed')
http_api.ReadServer.server_close=close
raise SystemExit(http_api.main(sys.argv[2:]))
'''
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.client_credentials import ClientCredentials
    ConversationStore(state,create=True);ClientCredentials(state,create=True)
    with output.open('wb') as log:
        process=subprocess.Popen([sys.executable,'-c',script,str(marker),'--state',str(state.directory),'--token-file',str(token),'--port','0','--conversations','simulated','--gpu-queue-config',str(config)],stdout=log,stderr=log)
        try:
            until=time.monotonic()+10
            while 'Écoute sur' not in output.read_text() and process.poll() is None and time.monotonic()<until:time.sleep(.02)
            assert 'Écoute sur' in output.read_text(),output.read_text()
            process.send_signal(signal.SIGTERM);assert process.wait(timeout=5)==0
        finally:
            if process.poll() is None:process.kill();process.wait()
    assert marker.read_text()=='closed'
    assert 'GPU_QUEUE_REVIEW_REQUIRED' in output.read_text() and 't'*40 not in output.read_text()
    assert q.inspect()['counts']['ACTIVE']==1
    assert [r['id'] for r in q.inspect()['jobs'] if r['state']=='WAITING']==['inherited']
    with q.db() as db:assert db.execute("SELECT state FROM jobs WHERE id='owned'").fetchone()[0]=='CANCELLED'
