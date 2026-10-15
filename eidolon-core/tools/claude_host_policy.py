# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_host_policy.py
# Description : Contrat versionné EXPÉRIMENTAL de politique hôte pour le tick de maintenance (Claude, G256-6)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""EXPERIMENTAL, pure. Proposal: docs/proposals/2026-10-15-host-policy-and-snapshot.md.

The operator writes the policy; nothing here has a default. Every threshold (ages, load limit) and the
load unit come from the operator. The observation names the unit it measured in and never carries the
limit: a snapshot cannot loosen the operator's ceiling, and a load measured in another unit is refused
instead of being compared with a limit it was never meant for. No sensor, timer, service or launcher.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
import math
import re

from eidolon_core.maintenance_observations import ObservationRefused, _SOURCE
from eidolon_core.maintenance_runner import run_maintenance_tick

SCHEMA = "eidolon-host-maintenance-policy/1"
_KEYS = frozenset({"schema", "expected_source", "max_observation_age_seconds", "max_load_age_seconds",
                   "load_unit", "load_limit"})
_UNIT = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


class PolicyRefused(ValueError):
    """The host policy is absent, incomplete, ambiguous or of an unknown version; nothing may run."""


@dataclass(frozen=True)
class HostPolicy:
    expected_source: str
    max_observation_age: timedelta
    max_load_age: timedelta
    load_unit: str
    load_limit: float


def _positive(value, name):
    try:
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise PolicyRefused(f"invalid {name}")
        return value
    except OverflowError:
        raise PolicyRefused(f"invalid {name}") from None


def _seconds(value, name):
    try:
        return timedelta(seconds=_positive(value, name))
    except OverflowError:
        raise PolicyRefused(f"invalid {name}") from None


def validate_host_policy(raw):
    if not isinstance(raw, dict):
        raise PolicyRefused("invalid host policy")
    if raw.get("schema") != SCHEMA:
        raise PolicyRefused("unsupported host policy version")
    if set(raw) != _KEYS:
        raise PolicyRefused("incomplete host policy" if not _KEYS <= set(raw) else "unexpected host policy field")
    source, unit = raw["expected_source"], raw["load_unit"]
    if type(source) is not str or _SOURCE.fullmatch(source) is None:
        raise PolicyRefused("invalid expected_source")
    if type(unit) is not str or _UNIT.fullmatch(unit) is None:
        raise PolicyRefused("invalid load_unit")
    return HostPolicy(source, _seconds(raw["max_observation_age_seconds"], "max_observation_age_seconds"),
                      _seconds(raw["max_load_age_seconds"], "max_load_age_seconds"), unit,
                      float(_positive(raw["load_limit"], "load_limit")))


def observation_for_policy(raw, policy):
    """Return a copy shaped for normalize_host_observation, the limit taken from the policy only."""
    if not isinstance(policy, HostPolicy):
        raise PolicyRefused("a validated host policy is required")
    if not isinstance(raw, dict):
        raise ObservationRefused("invalid host observation")
    value = deepcopy(raw)
    load = value.get("load")
    if load is not None:
        if not isinstance(load, dict) or set(load) != {"observed_at", "ratio", "unit"}:
            raise ObservationRefused("invalid load observation")  # including a snapshot that brings a limit
        if load["unit"] != policy.load_unit:
            raise ObservationRefused("load unit does not match the host policy")
        value["load"] = {"observed_at": load["observed_at"], "ratio": load["ratio"], "limit": policy.load_limit}
    return value


def run_with_policy(raw, policy, *, now, make_maintenance):
    """All refusals happen before make_maintenance is called; then exactly one runner tick."""
    observation = observation_for_policy(raw, policy)
    return run_maintenance_tick(observation, now=now, expected_source=policy.expected_source,
                                max_observation_age=policy.max_observation_age,
                                max_load_age=policy.max_load_age, make_maintenance=make_maintenance)


def check_only(policy_path, snapshot_path, *, now, max_bytes=4096):
    """Dry run for the host acceptance runbook: same validation, a stub engine, no Memory, no effect."""
    import os
    from datetime import datetime
    from claude_observation_snapshot import SnapshotRefused, read_json_snapshot
    calls = []

    class Stub:
        def tick(self, **kwargs):
            calls.append(kwargs)
            return "NOT_EXECUTED"
    try:
        when = datetime.fromisoformat(now) if isinstance(now, str) and 20 <= len(now) <= 40 else None
        if when is None or when.tzinfo is None:
            raise ObservationRefused("invalid --now")
        policy = validate_host_policy(read_json_snapshot(os.path.dirname(policy_path), os.path.basename(policy_path),
                                                         max_bytes=max_bytes))
        raw = read_json_snapshot(os.path.dirname(snapshot_path), os.path.basename(snapshot_path), max_bytes=max_bytes)
        result = run_with_policy(raw, policy, now=when, make_maintenance=Stub)
    except SnapshotRefused as exc:
        return 2, {"decision": "REFUSED", "stage": "read", "code": exc.code}
    except PolicyRefused as exc:
        return 2, {"decision": "REFUSED", "stage": "policy", "code": str(exc)}
    except ObservationRefused as exc:
        return 1, {"decision": "REFUSED", "stage": "observation", "code": str(exc)}
    o = result.observation
    return 0, {"decision": "WOULD_TICK", "engine_calls": len(calls), "load_ok": o.load_ok, "notes": list(o.notes),
               "observed_at": result.observed_at.isoformat(), "at": o.at.isoformat(),
               "last_activity": o.last_activity.isoformat(), "boot_at": o.boot_at.isoformat()}


def main(argv=None):
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Host maintenance policy check (no Memory, no tick).")
    parser.add_argument("--policy", required=True, help="absolute path of the operator's policy JSON")
    parser.add_argument("--snapshot", required=True, help="absolute path of the host observation JSON")
    parser.add_argument("--now", required=True, help="execution time, ISO 8601 with time zone")
    parser.add_argument("--check-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    code, report = check_only(args.policy, args.snapshot, now=args.now)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
