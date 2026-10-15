# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_beta_runtime_g270.py
# Description : Paired API, real isolated Memory bridges, receipts, quotas and activity
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import pytest
from eidolon_core.beta_runtime import BetaRuntime, ServiceError
from eidolon_core.activity import Activity
from eidolon_core import profile_files
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_api import ConversationAPI
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store


def config(tmp_path):
    state = tmp_path / 'services'; state.mkdir(mode=0o700)
    credentials = tmp_path / 'credentials'; credentials.mkdir(mode=0o700)
    roots = tmp_path / 'nas'; roots.mkdir()
    (roots / 'note.txt').write_text('Un fichier du NAS synthétique.')
    profiles = {}
    for i in range(2):
        read, write = credentials / f'read{i}', credentials / f'write{i}'
        read.write_text(str(i) * 40); read.chmod(0o600)
        write.write_text(str(i + 2) * 40); write.chmod(0o600)
        profiles[f'user{i}'] = dict(memory_port=18765+i, read_token_file=str(read), write_token_file=str(write),
                                  web_enabled=True, daily_web_limit=2, file_roots={'nas': str(roots)})
    return dict(schema='eidolon-beta-runtime/1', state_directory=str(state), activity_source='host.eidolon',
                clients={f'pc{i}': f'user{i}' for i in range(2)}, profiles=profiles, searxng_url='http://127.0.0.1:8888')


class Provider:
    provider_id = 'synthetic-provider'
    def __init__(self): self.calls = []
    def query(self, query, limit):
        self.calls.append(query)
        return [{'url': 'https://example.org/', 'title': 'Source synthétique', 'snippet': query}], 0


def preview(runtime, client='pc0', key='one', action='remember', parameters=None):
    return runtime.preview(client, 'actor', key, action, parameters or {'text': 'Ne pas acheter la V100.'})


def commit(runtime, value, client='pc0'):
    return runtime.commit(client, value['proposal']['id'], value['sha256'])


def test_web_quota_durable_shared_profile(tmp_path):
    conf = config(tmp_path); conf['clients']['second_pc'] = 'user0'
    provider = Provider(); runtime = BetaRuntime(conf, provider=provider)
    try:
        a = preview(runtime, key='search1', action='web.search', parameters={'query': 'exacte'})
        assert provider.calls == []
        with pytest.raises(ServiceError, match='APPROVAL'):
            runtime.commit('pc0', a['proposal']['id'], '0'*64)
        assert commit(runtime, a)['result']['status'] == 'OK'
        assert commit(runtime, a)['state'] == 'COMMITTED' and provider.calls == ['exacte']
    finally: runtime.close()
    runtime = BetaRuntime(conf, provider=provider)
    try:
        second = preview(runtime, client='second_pc', key='search2', action='web.search', parameters={'query': 'deux'})
        commit(runtime, second, 'second_pc')
        third = preview(runtime, key='search3', action='web.search', parameters={'query': 'trois'})
        with pytest.raises(ServiceError, match='QUOTA'): commit(runtime, third)
        assert len(provider.calls) == 2
        other = preview(runtime, client='pc1', action='web.search', parameters={'query': 'autre profil'})
        assert commit(runtime, other, 'pc1')['state'] == 'COMMITTED'
        with pytest.raises(ServiceError, match='NOT_FOUND'): commit(runtime, second)
    finally: runtime.close()


def test_unknown_web_is_not_resent_after_restart(tmp_path):
    conf = config(tmp_path); provider = Provider(); runtime = BetaRuntime(conf, provider=provider)
    a = preview(runtime, action='web.search', parameters={'query': 'incertaine'})
    with runtime._db() as db: db.execute("UPDATE actions SET state='INFLIGHT',day='2026-10-15'")
    runtime.close(); runtime = BetaRuntime(conf, provider=provider)
    try:
        assert commit(runtime, a)['state'] == 'UNKNOWN' and provider.calls == []
    finally: runtime.close()


def test_preview_conflict_and_profile_rebinding_refused(tmp_path):
    conf = config(tmp_path); runtime = BetaRuntime(conf)
    try:
        assert preview(runtime) == preview(runtime)
        with pytest.raises(ServiceError, match='KEY_REUSED'): preview(runtime, parameters={'text': 'autre'})
        with pytest.raises(ServiceError, match='PROFILE_NOT_BOUND'): runtime.profile('unknown')
    finally: runtime.close()
    conf['clients']['pc0'] = 'user1'
    with pytest.raises(ValueError, match='bindings changed'): BetaRuntime(conf)


def test_files_bounded_and_preview_detects_change(tmp_path):
    conf = config(tmp_path); runtime = BetaRuntime(conf)
    root = Path(conf['profiles']['user0']['file_roots']['nas'])
    try:
        a = preview(runtime, action='file.read', parameters={'root': 'nas', 'path': 'note.txt'})
        (root / 'note.txt').write_text('changed')
        assert commit(runtime, a)['state'] == 'UNKNOWN'
        for path in ('../credentials/read0', '/etc/passwd', 'a/../../x', 'a\\x'):
            with pytest.raises((ValueError, OSError)): profile_files.read(str(root), path)
        (root / 'link').symlink_to(root / 'note.txt')
        with pytest.raises(OSError): profile_files.read(str(root), 'link')
        assert all(x['name'] != 'link' for x in runtime.files('pc0', 'nas', '')['entries'])
        with pytest.raises(ServiceError): runtime.files('pc0', 'other', '')
    finally: runtime.close()


def test_activity_idle_busy_restart_single_exporter(tmp_path):
    folder = tmp_path / 'activity'; folder.mkdir(mode=0o700)
    now = [datetime(2026,10,17,3,tzinfo=timezone.utc)]
    active = Activity(folder, 'host.eidolon', clock=lambda: now[0], interval=3600)
    try:
        initial = active.flush(); now[0] += timedelta(hours=1)
        assert active.flush()['last_activity'] == initial['last_activity']
        with pytest.raises(BlockingIOError): Activity(folder, 'host.eidolon')
        with active.request():
            now[0] += timedelta(minutes=40)
            assert active.flush()['last_activity'] == now[0].isoformat()
        assert json.loads((folder/'activity.json').read_text())['last_activity'] == now[0].isoformat()
    finally: active.close()
    active.close()
    restarted = Activity(folder, 'host.eidolon', clock=lambda: now[0], interval=3600)
    try: assert restarted.flush()['last_activity'] == now[0].isoformat()
    finally: restarted.close()


def test_authenticated_chat_real_remember_and_isolation(tmp_path):
    pytest.importorskip('core.information.remember')
    from core.backend.filesystem import FilesystemBackend
    from services.memory_bridge import build_recall, BoundedRecallServer, make_handler
    from services.remember_bridge import RememberEndpoint
    conf = config(tmp_path)
    with ExitStack() as stack:
        for i in range(2):
            root = tmp_path / f'memory{i}'
            FilesystemBackend(root/'memory/persistent', root/'memory/history')
            from services.profile_binding import binding
            binding(root, f'user{i}', apply=True)
            handler = make_handler(build_recall(root), str(i)*40, remember=RememberEndpoint(root, f'user{i}'),
                                   write_token=str(i+2)*40, profile_id=f'user{i}')
            server = BoundedRecallServer(('127.0.0.1', 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            stack.callback(server.server_close); stack.callback(server.shutdown)
            conf['profiles'][f'user{i}']['memory_port'] = server.server_address[1]
        services = BetaRuntime(conf)
        runtime = synthetic_runtime(Store(tmp_path/'core-state'))
        ConversationStore(runtime.store, create=True)
        credentials = ClientCredentials(runtime.store, create=True)
        keys = [credentials.pair(client_id=f'pc{i}', actor=f'actor{i}') for i in range(2)]
        api = ConversationAPI(runtime, dialogue_model=SimulatedDialogueModel(runtime.catalog), services=services)
        def call(route, body, who=0):
            return api.handle('POST', '/v1/conversations/'+route,
                {'Authorization': ['Bearer '+keys[who]['token']], 'Content-Type': ['application/json']}, json.dumps(body).encode())
        try:
            status, opened = call('open', {'client_key': 'page'})
            assert status == 200 and opened['services']['profile_id'] == 'user0'
            status, a = call('action_preview', {'request_key': 'retain', 'action': 'remember', 'parameters': {'text': 'V100 hardware.'}})
            assert status == 200 and a['state'] == 'PREVIEW'
            assert not services.recall_for('pc0', 'V100')['items']
            assert call('action_commit', {'id': a['proposal']['id'], 'sha256': a['sha256']}, who=1)[0] == 404
            status, result = call('action_commit', {'id': a['proposal']['id'], 'sha256': a['sha256']})
            assert status == 200 and result['state'] == 'COMMITTED', result
            assert services.recall_for('pc0', 'V100')['items'][0]['content'] == 'V100 hardware.'
            assert not services.recall_for('pc1', 'V100')['items']
            with services._db() as db: db.execute("UPDATE actions SET state='INFLIGHT',result=NULL")
        finally: api.close()
        services = BetaRuntime(conf)
        try:
            restored = services.receipts('pc0')[0]
            assert restored['state'] == 'UNKNOWN'
            assert commit(services, restored)['state'] == 'COMMITTED'
            assert len(list((tmp_path/'memory0/memory/persistent').glob('*.md'))) == 1
            assert services.receipts('pc1') == []
        finally: services.close()


def test_live_activity_defers_passage_maintenance_and_scope_is_bound(tmp_path, monkeypatch):
    pytest.importorskip('core.indexing.runtime')
    from qdrant_client import QdrantClient
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.indexing.qdrant_passages import QdrantPassageIndex
    from core.indexing.runtime import IndexRuntime
    from services.profile_binding import binding
    import core.indexing.runtime as rt
    from eidolon_core.maintenance_host import run_once
    from eidolon_core.maintenance_policy import validate_host_policy
    root = tmp_path/'corpus'; persistent=root/'memory/persistent'
    FilesystemBackend(persistent,root/'memory/history').store(Memory('new',content='new V100 memory'))
    binding(root,'person',apply=True)
    state=tmp_path/'maintenance';state.mkdir(mode=0o700)
    cfg=IndexRuntime('eidolon_g270','fixture','a'*64,2,'',11434,6333,3,4096,2048,'archive_passages')
    client=QdrantClient(':memory:')
    index=QdrantPassageIndex(client,cfg.alias,embed=lambda _:[1.,0.],dimensions=2,embedding_id=cfg.embedding_id,create=True)
    close=client.close;monkeypatch.setattr(client,'close',lambda:None)
    monkeypatch.setattr(rt,'load_runtime',lambda _:cfg);monkeypatch.setattr(rt,'open_index',lambda _:index)
    runtime=dict(schema='eidolon-maintenance-runtime/2',canonical_root=str(persistent),state_directory=str(state),
                 index_config=str(tmp_path/'index.json'),profile_id='person',scope='isolated_profile_root')
    now=datetime(2026,10,17,3,tzinfo=timezone.utc)
    policy=validate_host_policy(dict(schema='eidolon-host-maintenance-policy/1',expected_source='host.eidolon',
        max_observation_age_seconds=120,max_load_age_seconds=120,load_unit='load1_per_cpu',load_limit=.7))
    observation=dict(source='host.eidolon',at=now.isoformat(),last_activity=now.isoformat(),
                     boot_at=(now-timedelta(hours=2)).isoformat(),load=dict(observed_at=now.isoformat(),ratio=.1,unit='load1_per_cpu'))
    try:
        old=index.active_generation()
        assert run_once(policy,observation,now=now,runtime=runtime)['report']['state']=='DEFERRED'
        assert index.active_generation()==old
        observation['last_activity']=(now-timedelta(hours=1)).isoformat()
        assert run_once(policy,observation,now=now,runtime=runtime)['report']['state']=='PUBLISHED'
        assert index.status().points==1
        runtime['profile_id']='other'
        with pytest.raises(ValueError,match='identity mismatch'):run_once(policy,observation,now=now,runtime=runtime)
    finally:close()
