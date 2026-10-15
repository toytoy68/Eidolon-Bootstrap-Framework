# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_host_policy_g258.py
# Description : Politique construite sans validateur, durées arrondies à zéro, JSON extrêmes, chemins (Claude, G258-4/5/6/7)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic only: temporary directories, no sensor, no launcher, no system change."""
from datetime import datetime, timedelta
import errno
import json
import os
from pathlib import Path

import pytest

from tests.test_claude_host_policy_g256 import hp, snap, observation, policy_raw, spy, write, AT

NOW = datetime.fromisoformat(AT)
GOOD = dict(expected_source="host.proc", max_observation_age=timedelta(seconds=60),
            max_load_age=timedelta(seconds=60), load_unit="load1_per_cpu", load_limit=0.7)


# --- G258-4: every construction path is validated, before the factory -----------------------------

@pytest.mark.parametrize("change", [
    dict(expected_source=""), dict(expected_source="Host"), dict(expected_source=None),
    dict(load_unit=""), dict(load_unit="per cpu"), dict(load_unit=None),
    dict(max_observation_age=timedelta(0)), dict(max_observation_age=timedelta(seconds=-1)),
    dict(max_observation_age=60), dict(max_load_age=timedelta(0)), dict(max_load_age="60"),
    dict(load_limit=-1.0), dict(load_limit=0.0), dict(load_limit=float("nan")), dict(load_limit=float("inf")),
    dict(load_limit="0.7"), dict(load_limit=True),
])
def test_a_policy_built_without_the_validator_is_refused_as_a_policy(change):
    with pytest.raises(hp.PolicyRefused):
        hp.HostPolicy(**{**GOOD, **change})


def test_a_direct_policy_is_identical_to_a_validated_one():
    assert hp.HostPolicy(**GOOD) == hp.validate_host_policy(policy_raw())
    factory, calls = spy()
    hp.run_with_policy(observation(), hp.HostPolicy(**GOOD), now=NOW, make_maintenance=factory)
    assert len(calls) == 2


@pytest.mark.parametrize("seconds", [1e-7, 4e-7, 5e-7, 1e-300, 5e-324])
def test_a_duration_that_rounds_to_zero_is_refused_by_the_validator(seconds):
    for key in ("max_observation_age_seconds", "max_load_age_seconds"):
        with pytest.raises(hp.PolicyRefused, match="rounds to zero"):
            hp.validate_host_policy(policy_raw(**{key: seconds}))


def test_the_smallest_representable_duration_is_kept_exactly():
    policy = hp.validate_host_policy(policy_raw(max_observation_age_seconds=1e-6))
    assert policy.max_observation_age == timedelta(microseconds=1)


def test_a_mutated_frozen_policy_is_checked_again_before_the_factory():
    policy = hp.HostPolicy(**GOOD)
    object.__setattr__(policy, "load_limit", float("nan"))   # deliberate bypass of frozen
    factory, calls = spy()
    with pytest.raises(hp.PolicyRefused):
        hp.run_with_policy(observation(), policy, now=NOW, make_maintenance=factory)
    assert calls == []


# --- G258-5: extreme numbers and strings in the snapshot -------------------------------------------

def read_bytes(tmp_path, data, **options):
    write(tmp_path, "observation.json", data)
    options.setdefault("max_bytes", snap.MAX_SNAPSHOT_BYTES)
    return snap.read_json_snapshot(str(tmp_path), "observation.json", **options)


def refused(code, tmp_path, data, **options):
    with pytest.raises(snap.SnapshotRefused) as caught:
        read_bytes(tmp_path, data, **options)
    assert caught.value.code == code, caught.value.code


@pytest.mark.parametrize("number", [b"1e999", b"-1e999", b"1E400", b"123456789e999"])
def test_numbers_that_overflow_to_infinity_are_refused(tmp_path, number):
    refused("SNAPSHOT_INVALID_JSON", tmp_path, b'{"load": {"ratio": ' + number + b'}}')


def test_very_long_integers_get_a_stable_refusal(tmp_path):
    refused("SNAPSHOT_INVALID_JSON", tmp_path, b'{"a": ' + b"9" * 5000 + b"}")   # beyond int parsing limit
    refused("SNAPSHOT_INVALID_JSON", tmp_path, b'{"a": ' + b"9" * 40 + b"}")     # beyond the reader's bound
    assert read_bytes(tmp_path, b'{"a": ' + b"9" * 18 + b"}") == {"a": int("9" * 18)}


def test_tiny_and_negative_zero_numbers_stay_finite(tmp_path):
    assert read_bytes(tmp_path, b'{"a": 1e-400, "b": -0.0}') == {"a": 0.0, "b": -0.0}


@pytest.mark.parametrize("data", [b'{"a": "\\ud800"}', b'{"\\udfff": 1}', b'{"a": ["\\ud83d"]}'])
def test_lone_surrogates_from_escapes_are_refused(tmp_path, data):
    refused("SNAPSHOT_ENCODING", tmp_path, data)


def test_escapes_cannot_hide_a_duplicate_key(tmp_path):
    refused("SNAPSHOT_DUPLICATE_KEY", tmp_path, b'{"source": "a", "sour\\u0063e": "b"}')
    assert read_bytes(tmp_path, b'{"a": "\\ud83d\\ude00", "b": "\\u00e9"}') == {"a": "\U0001F600", "b": "é"}


def test_depth_is_exact(tmp_path):
    four = b'{"a": {"b": {"c": {"d": 1}}}}'
    assert read_bytes(tmp_path, four, max_depth=4)["a"]["b"]["c"] == {"d": 1}
    refused("SNAPSHOT_TOO_DEEP", tmp_path, four, max_depth=3)
    assert read_bytes(tmp_path, b'{"a": [[[1]]]}', max_depth=4) == {"a": [[[1]]]}
    refused("SNAPSHOT_TOO_DEEP", tmp_path, b'{"a": [[[[1]]]]}', max_depth=4)


# --- G258-6: identity of the file AND of the path ---------------------------------------------------

def nested(tmp_path):
    leaf = tmp_path / "host" / "obs"
    leaf.mkdir(parents=True)
    write(leaf, "observation.json", observation())
    return leaf


@pytest.mark.parametrize("change", ["rename-ancestor", "replace-ancestor", "ancestor-becomes-link"])
def test_a_path_whose_ancestors_change_during_the_read_is_refused(tmp_path, monkeypatch, change):
    leaf = nested(tmp_path)
    host = tmp_path / "host"

    def hook():
        os.rename(host, tmp_path / "moved")
        if change == "replace-ancestor":
            (host / "obs").mkdir(parents=True)               # same path, other directories
            write(host / "obs", "observation.json", observation(at="2026-10-15T03:00:05+00:00"))
        elif change == "ancestor-becomes-link":
            host.symlink_to(tmp_path / "moved", target_is_directory=True)  # same bytes behind a link
    monkeypatch.setattr(snap, "_after_read", hook)
    with pytest.raises(snap.SnapshotRefused) as caught:
        snap.read_json_snapshot(str(leaf), "observation.json", max_bytes=4096)
    assert caught.value.code == "SNAPSHOT_PATH_CHANGED"


def test_an_ancestor_that_is_already_a_link_or_unreadable_is_refused_before_reading(tmp_path, monkeypatch):
    leaf = nested(tmp_path)
    (tmp_path / "alias").symlink_to(tmp_path / "host", target_is_directory=True)
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_PATH"):
        snap.read_json_snapshot(str(tmp_path / "alias" / "obs"), "observation.json", max_bytes=4096)
    real_open = os.open

    def denied(path, flags, *args, **kwargs):          # simulated EACCES on one ancestor, no chmod
        if path == "host":
            raise PermissionError(errno.EACCES, "denied")
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(snap.os, "supports_dir_fd", os.supports_dir_fd | {denied})
    monkeypatch.setattr(snap.os, "open", denied)
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_PATH"):
        snap.read_json_snapshot(str(leaf), "observation.json", max_bytes=4096)


def test_a_vanished_file_or_directory_is_refused(tmp_path, monkeypatch):
    leaf = nested(tmp_path)
    monkeypatch.setattr(snap, "_after_read", lambda: os.unlink(leaf / "observation.json"))
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_CHANGED"):
        snap.read_json_snapshot(str(leaf), "observation.json", max_bytes=4096)
    monkeypatch.setattr(snap, "_after_read", None)
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_PATH"):
        snap.read_json_snapshot(str(tmp_path / "gone"), "observation.json", max_bytes=4096)


# --- G258-7: portability: required primitives are checked, never assumed --------------------------

def test_the_inventory_is_complete_on_this_linux_host():
    assert snap.missing_primitives() == ()


@pytest.mark.parametrize("remove", ["O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "O_CLOEXEC"])
def test_a_missing_open_flag_is_an_explicit_refusal(monkeypatch, tmp_path, remove):
    monkeypatch.delattr(snap.os, remove)
    assert remove in snap.missing_primitives()
    write(tmp_path, "observation.json", observation())
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_PLATFORM_UNSUPPORTED"):
        snap.read_json_snapshot(str(tmp_path), "observation.json", max_bytes=4096)


def test_windows_like_platforms_are_refused_before_any_open(monkeypatch, tmp_path):
    monkeypatch.setattr(snap.os, "supports_dir_fd", set())
    monkeypatch.setattr(snap.os, "supports_follow_symlinks", set())
    opened = []
    monkeypatch.setattr(snap.os, "open", lambda *a, **k: opened.append(a) or (_ for _ in ()).throw(OSError()))
    assert {"dir_fd:open", "dir_fd:stat", "follow_symlinks:stat"} <= set(snap.missing_primitives())
    with pytest.raises(snap.SnapshotRefused, match="SNAPSHOT_PLATFORM_UNSUPPORTED"):
        snap.read_json_snapshot(str(tmp_path), "observation.json", max_bytes=4096)
    assert opened == []


def test_offline_preflight_says_unknown_instead_of_crashing_without_posix_ownership(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "claude_offline_preflight_g258", Path(__file__).resolve().parents[1] / "tools" / "claude_offline_preflight.py")
    pre = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pre)
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir(mode=0o700)
    secret = secret_dir / "token"
    secret.write_text("x" * 40)
    secret.chmod(0o600)
    assert pre.check_credential(secret)["result"] == "PASS"
    monkeypatch.delattr(pre.os, "geteuid")                  # as on Windows
    assert pre.check_credential(secret)["result"] == "UNKNOWN"
