# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_host_policy_g256.py
# Description : Contrat versionné de politique hôte et lecture bornée de l'instantané (Claude, G256-6/7)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic values only; thresholds below are test fixtures, not recommendations. No sensor, no launcher."""
from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

import pytest

from eidolon_core.maintenance_observations import ObservationRefused

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hp = load("claude_host_policy")
snap = load("claude_observation_snapshot")

AT = "2026-10-15T03:00:00+00:00"
NOW = datetime.fromisoformat(AT)


def policy_raw(**over):
    value = {"schema": hp.SCHEMA, "expected_source": "host.proc", "max_observation_age_seconds": 60,
             "max_load_age_seconds": 60, "load_unit": "load1_per_cpu", "load_limit": 0.7}
    value.update(over)
    return value


def observation(**over):
    value = {"source": "host.proc", "at": AT, "last_activity": "2026-10-15T01:00:00+00:00",
             "boot_at": "2026-10-14T20:00:00+00:00",
             "load": {"observed_at": "2026-10-15T02:59:30+00:00", "ratio": 0.2, "unit": "load1_per_cpu"}}
    value.update(over)
    return value


def spy():
    calls = []

    def factory():
        calls.append("factory")

        class Engine:
            def tick(self, **kwargs):
                calls.append(("tick", kwargs))
                return "REPORT"
        return Engine()
    return factory, calls


# --- G256-6: policy contract ---------------------------------------------------------------------

def test_a_complete_policy_drives_one_tick_with_the_operator_limit():
    policy = hp.validate_host_policy(policy_raw())
    factory, calls = spy()
    raw = observation()
    before = deepcopy(raw)
    result = hp.run_with_policy(raw, policy, now=NOW + timedelta(seconds=30), make_maintenance=factory)
    assert calls[0] == "factory" and calls[1][1]["load_ok"] is True and result.report == "REPORT"
    assert raw == before
    high = hp.run_with_policy(observation(load={"observed_at": AT, "ratio": 0.71, "unit": "load1_per_cpu"}),
                              policy, now=NOW, make_maintenance=spy()[0])
    assert high.observation.load_ok is False and "LOAD_HIGH" in high.observation.notes


@pytest.mark.parametrize("change", [
    dict(schema="eidolon-host-maintenance-policy/2"), dict(schema=None), dict(extra=1),
    dict(expected_source="Host"), dict(expected_source=""), dict(load_unit="per cpu"), dict(load_unit=1),
    dict(max_observation_age_seconds=0), dict(max_observation_age_seconds=-1),
    dict(max_observation_age_seconds=True), dict(max_observation_age_seconds="60"),
    dict(max_load_age_seconds=float("nan")), dict(max_load_age_seconds=float("inf")),
    dict(max_load_age_seconds=10 ** 400), dict(max_load_age_seconds=1e300), dict(load_limit=0),
    dict(load_limit=True), dict(load_limit=float("nan")),
])
def test_an_ambiguous_or_unknown_policy_is_refused(change):
    with pytest.raises(hp.PolicyRefused):
        hp.validate_host_policy(policy_raw(**change))


@pytest.mark.parametrize("key", sorted(hp._KEYS - {"schema"}))
def test_no_field_has_a_default(key):
    raw = policy_raw()
    del raw[key]
    with pytest.raises(hp.PolicyRefused, match="incomplete"):
        hp.validate_host_policy(raw)


@pytest.mark.parametrize("load", [
    {"observed_at": AT, "ratio": 0.2, "unit": "load5_per_cpu"},             # another unit
    {"observed_at": AT, "ratio": 0.2, "unit": "load1_per_cpu", "limit": 9},  # a snapshot cannot bring a limit
    {"observed_at": AT, "ratio": 0.2, "limit": 0.7},                         # the G254 shape, unit unknown
    {"observed_at": AT, "ratio": 0.2},
])
def test_a_load_in_another_unit_or_with_its_own_limit_never_constructs_the_controller(load):
    factory, calls = spy()
    with pytest.raises(ObservationRefused):
        hp.run_with_policy(observation(load=load), hp.validate_host_policy(policy_raw()), now=NOW,
                           make_maintenance=factory)
    assert calls == []


def test_an_unknown_load_stays_conservative_and_a_raw_dict_is_not_a_policy():
    factory, calls = spy()
    result = hp.run_with_policy(observation(load=None), hp.validate_host_policy(policy_raw()), now=NOW,
                                make_maintenance=factory)
    assert result.observation.load_ok is False and "LOAD_UNKNOWN" in result.observation.notes
    with pytest.raises(hp.PolicyRefused):
        hp.run_with_policy(observation(), policy_raw(), now=NOW, make_maintenance=factory)


# --- G256-7: bounded snapshot read ---------------------------------------------------------------

def write(directory, name, data, mode=0o600):
    path = directory / name
    path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
    path.chmod(mode)
    return path


def read(directory, name="observation.json", **options):
    options.setdefault("max_bytes", 4096)
    return snap.read_json_snapshot(str(directory), name, **options)


def refused(code, directory, name="observation.json", **options):
    with pytest.raises(snap.SnapshotRefused) as caught:
        read(directory, name, **options)
    assert caught.value.code == code


def test_a_snapshot_flows_into_the_policy_runner(tmp_path):
    write(tmp_path, "observation.json", observation())
    factory, calls = spy()
    result = hp.run_with_policy(read(tmp_path), hp.validate_host_policy(policy_raw()), now=NOW,
                                make_maintenance=factory)
    assert result.observation.load_ok is True and len(calls) == 2


@pytest.mark.parametrize("data, code", [
    (b'{"source": "host.proc", "source": "host.other"}', "SNAPSHOT_DUPLICATE_KEY"),
    (b'{"load": {"ratio": 0.1, "ratio": 0.9}}', "SNAPSHOT_DUPLICATE_KEY"),
    (b'{"load": {"ratio": NaN}}', "SNAPSHOT_INVALID_JSON"),
    (b'{"load": {"ratio": Infinity}}', "SNAPSHOT_INVALID_JSON"),
    (b'["not", "an", "object"]', "SNAPSHOT_INVALID_JSON"),
    (b'{"a": 1} trailing', "SNAPSHOT_INVALID_JSON"),
    (b'', "SNAPSHOT_INVALID_JSON"),
    (b'\xef\xbb\xbf{"a": 1}', "SNAPSHOT_ENCODING"),
    (b'{"a": "\xff"}', "SNAPSHOT_ENCODING"),
    (b'{"a": {"b": {"c": {"d": {}}}}}', "SNAPSHOT_TOO_DEEP"),
    (b'{"a": ' + b'[' * 100000 + b']' * 100000 + b'}', "SNAPSHOT_TOO_LARGE"),
])
def test_malformed_snapshots_are_refused(tmp_path, data, code):
    write(tmp_path, "observation.json", data)
    refused(code, tmp_path, max_bytes=snap.MAX_SNAPSHOT_BYTES if code == "SNAPSHOT_TOO_DEEP" else 4096)


def test_deep_nesting_within_the_byte_budget_cannot_exhaust_the_parser(tmp_path):
    write(tmp_path, "observation.json", b'{"a": ' + b'[' * 200000 + b']' * 200000 + b'}')
    refused("SNAPSHOT_TOO_DEEP", tmp_path, max_bytes=snap.MAX_SNAPSHOT_BYTES)


def test_size_is_bounded_exactly(tmp_path):
    body = b'{"a": "' + b"x" * 100 + b'"}'
    write(tmp_path, "observation.json", body)
    assert read(tmp_path, max_bytes=len(body)) == {"a": "x" * 100}
    refused("SNAPSHOT_TOO_LARGE", tmp_path, max_bytes=len(body) - 1)
    for budget in (0, True, snap.MAX_SNAPSHOT_BYTES + 1, 1.5):
        refused("SNAPSHOT_BUDGET", tmp_path, max_bytes=budget)


def test_links_special_files_and_shared_permissions_are_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    write(real, "observation.json", observation())
    (tmp_path / "link.json").symlink_to(real / "observation.json")
    refused("SNAPSHOT_UNAVAILABLE", tmp_path, "link.json")
    (tmp_path / "linked-dir").symlink_to(real, target_is_directory=True)
    refused("SNAPSHOT_PATH", tmp_path / "linked-dir")
    os.link(real / "observation.json", tmp_path / "hard.json")
    refused("SNAPSHOT_NOT_REGULAR", tmp_path, "hard.json")
    os.mkfifo(tmp_path / "fifo.json")                      # no writer: a blocking open would hang here
    refused("SNAPSHOT_NOT_REGULAR", tmp_path, "fifo.json")
    write(tmp_path, "shared.json", observation(), mode=0o622)
    refused("SNAPSHOT_WRITABLE_BY_OTHERS", tmp_path, "shared.json")
    refused("SNAPSHOT_UNAVAILABLE", tmp_path, "missing.json")
    for name in ("../observation.json", ".hidden.json", "observation.txt", "a/b.json", "x\0.json"):
        refused("SNAPSHOT_PATH", tmp_path, name)
    with pytest.raises(snap.SnapshotRefused):
        snap.read_json_snapshot("relative/dir", "observation.json", max_bytes=10)


@pytest.mark.parametrize("change", ["replace", "rewrite", "append", "remove"])
def test_a_snapshot_changed_or_replaced_during_the_read_is_refused(tmp_path, monkeypatch, change):
    target = write(tmp_path, "observation.json", observation())
    other = write(tmp_path, "next.json", observation(at="2026-10-15T03:00:01+00:00"))

    def hook():
        if change == "replace":
            os.replace(other, target)                      # atomic rename by the host, new inode
        elif change == "rewrite":
            target.write_bytes(json.dumps(observation(at="2026-10-15T03:00:09+00:00")).encode())
        elif change == "append":
            with open(target, "ab") as handle:
                handle.write(b" ")
        else:
            target.unlink()
    monkeypatch.setattr(snap, "_after_read", hook)
    refused("SNAPSHOT_CHANGED", tmp_path)


def test_a_writer_racing_the_reader_never_yields_a_mixed_snapshot(tmp_path):
    # The host replaces the file atomically in a loop; every successful read is one complete version.
    versions = [observation(at=f"2026-10-15T03:00:{n:02d}+00:00") for n in range(10)]
    write(tmp_path, "observation.json", versions[0])
    stop = threading.Event()

    def writer():
        n = 0
        while not stop.is_set():
            staged = write(tmp_path, f"stage-{n % 2}.json", versions[n % 10])
            os.replace(staged, tmp_path / "observation.json")
            n += 1
    thread = threading.Thread(target=writer)
    thread.start()
    seen = []
    try:
        for _ in range(300):
            try:
                seen.append(read(tmp_path))
            except snap.SnapshotRefused as exc:
                assert exc.code in ("SNAPSHOT_CHANGED", "SNAPSHOT_UNAVAILABLE")
    finally:
        stop.set()
        thread.join(5)
    assert seen and all(value in versions for value in seen)


# --- G256-10: the runbook's dry-run command ------------------------------------------------------

def cli(tmp_path, policy, snapshot, now=AT, mode=0o600):
    import subprocess
    write(tmp_path, "policy.json", policy)
    write(tmp_path, "observation.json", snapshot, mode=mode)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    r = subprocess.run([sys.executable, str(TOOLS / "claude_host_policy.py"), "--policy", str(tmp_path / "policy.json"),
                        "--snapshot", str(tmp_path / "observation.json"), "--now", now, "--check-only"],
                       capture_output=True, text=True, env=env, timeout=30)
    return r.returncode, json.loads(r.stdout)


def test_runbook_dry_run_reports_one_stub_call(tmp_path):
    code, report = cli(tmp_path, policy_raw(), observation())
    assert code == 0 and report["decision"] == "WOULD_TICK" and report["engine_calls"] == 1
    assert report["load_ok"] is True and report["notes"] == []


@pytest.mark.parametrize("snapshot, now, code, stage", [
    (observation(), "2026-10-15T03:01:01+00:00", 1, "observation"),             # stale capture
    (observation(at="2026-10-15T03:00:30+00:00"), AT, 1, "observation"),        # capture in the future
    (observation(source="host.other"), AT, 1, "observation"),
    (observation(load={"observed_at": AT, "ratio": 0.2, "unit": "load5_per_cpu"}), AT, 1, "observation"),
    (observation(), "2026-10-15T03:00:00", 1, "observation"),                    # --now without time zone
])
def test_runbook_dry_run_refusals(tmp_path, snapshot, now, code, stage):
    got, report = cli(tmp_path, policy_raw(), snapshot, now=now)
    assert (got, report["decision"], report["stage"]) == (code, "REFUSED", stage)


def test_runbook_dry_run_unknown_values_and_permissions(tmp_path):
    code, report = cli(tmp_path, policy_raw(), observation(load=None, boot_at=None))
    assert code == 0 and report["load_ok"] is False and report["notes"] == ["BOOT_AT_UNKNOWN", "LOAD_UNKNOWN"]
    assert report["boot_at"] == report["at"]  # unknown boot = just now: the controller will defer
    code, report = cli(tmp_path, policy_raw(), observation(), mode=0o666)
    assert (code, report["code"]) == (2, "SNAPSHOT_WRITABLE_BY_OTHERS")
    if os.geteuid() != 0:  # root reads a 000 file anyway; the refusal is the kernel's, not ours
        try:
            code, report = cli(tmp_path, policy_raw(), observation(), mode=0o000)
            assert (code, report["code"]) == (2, "SNAPSHOT_UNAVAILABLE")
        finally:
            # Restore only this synthetic fixture before the next CLI scenario.
            (tmp_path / "observation.json").chmod(0o600)
    code, report = cli(tmp_path, {k: v for k, v in policy_raw().items() if k != "load_limit"}, observation())
    assert (code, report["stage"]) == (2, "policy")
