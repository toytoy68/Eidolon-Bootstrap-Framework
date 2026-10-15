# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_observation_range_g251.py
# Description : Out-of-range host observations are refused through the public error contract.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import pytest
from eidolon_core.maintenance_observations import ObservationRefused, normalize_host_observation
from tests.test_maintenance_observations import raw


@pytest.mark.parametrize('field', ['ratio', 'limit'])
def test_unrepresentable_load_is_refused(field):
    value = raw()
    value['load'][field] = 10 ** 400
    with pytest.raises(ObservationRefused, match='invalid load'):
        normalize_host_observation(value)


def test_timezone_conversion_outside_datetime_range_is_refused():
    value = raw()
    value['at'] = '0001-01-01T00:00:00+01:00'
    with pytest.raises(ObservationRefused, match='invalid at'):
        normalize_host_observation(value)


def test_representable_upper_date_does_not_overflow_the_skew_comparison():
    value = raw()
    value['at'] = '9999-12-31T23:59:59+00:00'
    result = normalize_host_observation(value)
    assert result.at.year == 9999
    assert not result.load_ok and 'LOAD_STALE' in result.notes
