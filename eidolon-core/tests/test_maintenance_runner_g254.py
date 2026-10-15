# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_maintenance_runner_g254.py
# Description : Host observations must be current before constructing or ticking maintenance.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from eidolon_core.maintenance_observations import ObservationRefused
from eidolon_core.maintenance_runner import run_maintenance_tick
from tests.test_maintenance_observations import raw, AT

NOW = datetime.fromisoformat(AT)


def invoke(value, factory, **overrides):
    options = dict(now=NOW, expected_source='host.proc',
                   max_observation_age=timedelta(seconds=60), max_load_age=timedelta(seconds=60))
    options.update(overrides)
    return run_maintenance_tick(value, make_maintenance=factory, **options)


def spy():
    calls = []
    report = SimpleNamespace(state='ACTIVE')
    def tick(**kwargs):
        calls.append(('tick', kwargs))
        return report
    def factory():
        calls.append(('factory', None))
        return SimpleNamespace(tick=tick)
    return factory, calls, report


def test_current_observation_is_applied_once_with_explicit_clock_and_provenance():
    factory, calls, report = spy()
    value = raw()
    before = deepcopy(value)
    now = NOW + timedelta(seconds=30)
    result = invoke(value, factory, now=now)
    assert [call[0] for call in calls] == ['factory', 'tick']
    assert result.report is report and result.observed_at == NOW
    assert result.observation.at == now and result.observation.source == 'host.proc'
    assert calls[1][1] == result.observation.tick_kwargs()
    assert value == before and result.observation.notes == ()


@pytest.mark.parametrize('change', [
    {'at': '2026-10-15T03:00:00'}, {'at': '0001-01-01T00:00:00+01:00'},
    {'at': (NOW+timedelta(microseconds=1)).isoformat()},
    {'at': (NOW-timedelta(seconds=60,microseconds=1)).isoformat()},
    {'source': 'host.other'}, {'extra': 1},
    {'load': {'observed_at': AT, 'ratio': float('inf'), 'limit': 1}},
])
def test_invalid_or_stale_input_never_constructs_the_controller(tmp_path, change):
    marker = tmp_path/'controller-created'
    def factory():
        marker.touch()
        pytest.fail('invalid observation reached the factory')
    with pytest.raises(ObservationRefused):
        invoke(raw(**change), factory)
    assert not marker.exists()


@pytest.mark.parametrize('policy', [
    {'max_observation_age': timedelta(0)}, {'max_observation_age': timedelta(seconds=-1)},
    {'max_observation_age': 60}, {'max_load_age': timedelta(0)},
    {'expected_source': ''}, {'expected_source': None}, {'now': 'no clock'},
])
def test_invalid_host_policy_never_constructs_the_controller(policy):
    factory, calls, _ = spy()
    with pytest.raises(ObservationRefused):
        invoke(raw(), factory, **policy)
    assert calls == []


def test_snapshot_age_boundary_is_inclusive_and_load_age_uses_execution_time():
    factory, calls, _ = spy()
    result = invoke(raw(), factory, now=NOW+timedelta(seconds=60))
    assert result.observation.notes == ('LOAD_STALE',)
    assert not calls[1][1]['load_ok']


def test_unknown_observations_remain_conservative_at_execution_time():
    factory, calls, _ = spy()
    result = invoke({'source': 'host.proc', 'at': AT}, factory, now=NOW+timedelta(seconds=30))
    kwargs = calls[1][1]
    assert kwargs['last_activity'] == kwargs['boot_at'] == kwargs['at'] == NOW+timedelta(seconds=30)
    assert not kwargs['load_ok']
    assert result.observation.notes == ('LAST_ACTIVITY_UNKNOWN', 'BOOT_AT_UNKNOWN', 'LOAD_UNKNOWN')


@pytest.mark.parametrize('phase', ['factory', 'tick'])
def test_factory_or_tick_failure_is_not_retried_or_reported_as_success(phase):
    calls = []
    failure = RuntimeError('synthetic failure')
    def tick(**kwargs):
        calls.append('tick')
        raise failure
    def factory():
        calls.append('factory')
        if phase == 'factory':
            raise failure
        return SimpleNamespace(tick=tick)
    with pytest.raises(RuntimeError) as raised:
        invoke(raw(), factory)
    assert raised.value is failure
    assert calls == (['factory'] if phase == 'factory' else ['factory', 'tick'])


def test_capture_cannot_hide_a_future_activity_by_rebasing_to_execution_time():
    factory, calls, _ = spy()
    value = raw(last_activity=(NOW+timedelta(seconds=90)).isoformat())
    with pytest.raises(ObservationRefused):
        invoke(value, factory, now=NOW+timedelta(seconds=120), max_observation_age=timedelta(minutes=5))
    assert calls == []


@pytest.mark.parametrize('case', ['eligible', 'unknown', 'stale_load', 'high_load', 'outside_window', 'denied'])
def test_host_entrypoint_against_real_memory_cycle(tmp_path, case):
    import os
    from contextlib import closing
    if os.environ.get('EIDOLON_MEMORY_INTEGRATION') != '1':
        pytest.skip('explicit Memory integration')
    qdrant = pytest.importorskip('qdrant_client')
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.indexing.change_journal import ChangeJournal
    from core.indexing.maintenance import IndexMaintenance
    from core.indexing.qdrant_index import QdrantIndex
    from core.indexing.worker_canonical import CanonicalReader

    captured = datetime.now(timezone.utc).replace(hour=3, minute=0, second=0, microsecond=0)+timedelta(days=1)
    if case == 'outside_window':
        from zoneinfo import ZoneInfo
        captured = captured.astimezone(ZoneInfo('Europe/Paris')).replace(
            hour=7, minute=59, second=30).astimezone(timezone.utc)
    current = captured+timedelta(seconds=60)
    value = dict(source='host.proc', at=captured.isoformat(),
                 last_activity=(captured-timedelta(hours=1)).isoformat(),
                 boot_at=(captured-timedelta(hours=2)).isoformat(),
                 load=dict(observed_at=(captured-timedelta(seconds=30)).isoformat(), ratio=0.1, limit=0.7))
    if case == 'unknown':
        value = dict(source='host.proc', at=captured.isoformat())
    elif case == 'high_load':
        value['load']['ratio'] = 0.9
    root = tmp_path/'persistent'
    backend = FilesystemBackend(root, tmp_path/'history')
    backend.store(Memory('a', content='synthetic'))
    _, digest = CanonicalReader(root)('a')
    journal = ChangeJournal(tmp_path/'changes.sqlite3')
    seq = journal.begin('a', 1, 'UPSERT', digest)
    journal.published(seq)
    calls = []
    with closing(qdrant.QdrantClient(':memory:')) as client:
        index = QdrantIndex(client, 'eidolon_g254_test', embed=lambda _: [1., 0.],
                            dimensions=2, embedding_id='synthetic-v1', create=True)
        def factory():
            calls.append('factory')
            controller = IndexMaintenance(tmp_path/'cycle.sqlite3', journal,
                canonical_checkpoint=tmp_path/'canonical.sqlite3', orphan_checkpoint=tmp_path/'orphans.sqlite3',
                canonical_root=root, index=index, authorize=lambda *_: case != 'denied',
                profile_id='owner', expected_profile_id='owner', expected_model_id='synthetic-v1')
            assert not hasattr(controller.index, 'delete')
            return controller
        result = invoke(value, factory, now=current, max_observation_age=timedelta(minutes=2),
                        max_load_age=timedelta(seconds=60 if case == 'stale_load' else 120))
        assert calls == ['factory']
        assert result.observed_at == captured and result.observation.at == current
        if case in ('eligible', 'denied'):
            assert result.report.state == 'ACTIVE'
            assert result.report.detail['pass_started'] == seq
            assert index.status().documents == 0  # First tick durably records the pass fence.
            result = invoke(value, factory, now=current+timedelta(seconds=1),
                max_observation_age=timedelta(minutes=2), max_load_age=timedelta(seconds=120))
            assert calls == ['factory', 'factory']  # Explicit second host call, never an internal retry.
        if case == 'eligible':
            assert index.status().documents == 1 and journal.intent(seq).state == 'INDEXED'
        else:
            assert index.status().documents == 0 and journal.intent(seq).state != 'INDEXED'
            if case == 'denied':
                assert (seq, 'FORBIDDEN') in result.report.detail['result']['deferred']
            else:
                assert result.report.state == 'DEFERRED'
                reason = 'OUTSIDE_WINDOW' if case == 'outside_window' else 'LOAD_NOT_READY'
                assert reason in result.report.detail['reasons']
