# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : maintenance_runner.py
# Description : Explicit host tick with observation freshness checked before controller creation.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""One caller-driven maintenance tick; no timer, sensor, daemon or implicit retry.

The host supplies its clock, expected source, age policies and controller factory.
Source labels describe provenance, not authentication. A valid observation permits
construction, not index mutation: the controller still enforces its window, load,
permissions and durable recovery. Exceptions are propagated without replay because
the factory or tick may already have had effects.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .maintenance_observations import (
    ObservationRefused, TickObservation, _SOURCE, _aware, normalize_host_observation,
)


class MaintenanceEngine(Protocol):
    def tick(self, *, at: datetime, last_activity: datetime,
             boot_at: datetime, load_ok: bool) -> object: ...


@dataclass(frozen=True)
class HostMaintenanceResult:
    observed_at: datetime
    observation: TickObservation
    report: object


def run_maintenance_tick(raw, *, now, expected_source: str,
                         max_observation_age: timedelta, max_load_age: timedelta,
                         make_maintenance: Callable[[], MaintenanceEngine]) -> HostMaintenanceResult:
    """Validate the capture, then re-evaluate load/activity at the execution time.

    Future captures are refused; age exactly at the host's limit is accepted.
    Missing activity/boot/load stays conservative through the normalizer. The
    factory is called once, only after all observation validation, followed by one
    tick. There is no automatic clock recovery, reconstruction or deletion.
    """
    if (type(expected_source) is not str or _SOURCE.fullmatch(expected_source) is None
            or not isinstance(max_observation_age, timedelta)
            or max_observation_age <= timedelta(0)):
        raise ObservationRefused("invalid host observation policy")
    current = _aware(now, "execution time")
    value = deepcopy(raw)
    captured = normalize_host_observation(value, max_load_age=max_load_age)
    if captured.source != expected_source:
        raise ObservationRefused("unexpected observation source")
    age = current - captured.at
    if age < timedelta(0):
        raise ObservationRefused("observation capture is in the future")
    if age > max_observation_age:
        raise ObservationRefused("observation capture is stale")
    # Validate the original capture first; rebasing alone could hide a timestamp
    # that was implausibly far in the future when the snapshot was captured.
    value["at"] = current
    observation = normalize_host_observation(value, max_load_age=max_load_age)
    engine = make_maintenance()
    report = engine.tick(**observation.tick_kwargs())
    return HostMaintenanceResult(captured.at, observation, report)
