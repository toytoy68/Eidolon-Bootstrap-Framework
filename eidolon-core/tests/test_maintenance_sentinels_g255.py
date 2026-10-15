# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_maintenance_sentinels_g255.py
# Description : Independent host-path probes for implausible timestamp sentinels.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import timedelta
import pytest
from eidolon_core.maintenance_observations import ObservationRefused, normalize_host_observation
from tests.test_maintenance_runner_g254 import NOW, invoke, raw, spy

EPOCH = '1970-01-01T00:00:00+00:00'


def test_epoch_load_remains_unknown_even_with_a_century_freshness_budget():
    value = raw()
    value['load']['observed_at'] = EPOCH
    result = normalize_host_observation(value, max_load_age=timedelta(days=36500))
    assert not result.load_ok
    assert 'LOAD_IMPLAUSIBLE' in result.notes


def test_epoch_activity_and_boot_are_rebased_to_execution_time():
    factory, calls, _ = spy()
    now = NOW + timedelta(seconds=30)
    result = invoke(raw(last_activity=EPOCH, boot_at=EPOCH), factory, now=now)
    assert calls[1][1]['last_activity'] == calls[1][1]['boot_at'] == now
    assert result.observation.notes == ('LAST_ACTIVITY_IMPLAUSIBLE', 'BOOT_AT_IMPLAUSIBLE')


def test_epoch_capture_cannot_reach_factory_under_a_century_age_policy():
    factory, calls, _ = spy()
    with pytest.raises(ObservationRefused, match='implausible host clock'):
        invoke({'source': 'host.proc', 'at': EPOCH}, factory,
               max_observation_age=timedelta(days=36500))
    assert calls == []
