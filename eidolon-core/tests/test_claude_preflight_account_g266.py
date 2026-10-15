# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_preflight_account_g266.py
# Description : Préflight propriétaire : entrées invalides, UID du fournisseur, dossier substitué (Claude, G266-5)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic metadata: no chown, no useradd. The real-owner case runs only under an ordinary UID."""
import math
import os
import shutil

import pytest

from tests.test_claude_preflight_account_g262 import SERVICE, check, layout, owners, pre


@pytest.mark.parametrize("budget", [math.nan, None, True, False, 0, -1, 1.5, "10"])
def test_an_invalid_entry_budget_is_unknown_never_pass(tmp_path, budget):
    result = check(layout(tmp_path), tmp_path, max_entries=budget)
    assert result == {"check": "memory.canonical_owner", "result": "UNKNOWN", "detail": "invalid entry budget"}


@pytest.mark.parametrize("uid", [True, -5, "1000", 1.5, math.nan])
def test_an_invalid_uid_from_the_account_database_is_unknown(tmp_path, uid):
    result = check(layout(tmp_path), tmp_path, uid=uid)
    assert (result["result"], result["detail"]) == ("UNKNOWN", "invalid UID from the account database")


def test_a_directory_replaced_between_listing_and_visit_is_a_race(tmp_path, monkeypatch):
    root = layout(tmp_path)
    real_open = os.open
    swapped = []

    def open_then(path, flags, *a, **k):
        if path == "pending-delete" and not swapped:
            swapped.append(1)
            os.rename(root / "memory/history/pending-delete", tmp_path / "moved")
            (root / "memory/history/pending-delete").mkdir(mode=0o700)
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(pre.os, "open", open_then)
    result = check(root, tmp_path)
    assert swapped and (result["result"], result["detail"]) == ("UNKNOWN", "the tree changed during the check")


def test_a_directory_turned_into_a_link_after_listing_is_never_followed(tmp_path, monkeypatch):
    root = layout(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (outside / "x.md").write_text("x")
    real_listdir = os.listdir
    done = []

    def listdir_then_swap(fd):
        names = real_listdir(fd)
        if "pending-delete" in names and not done:
            done.append(1)
            shutil.rmtree(root / "memory/history/pending-delete")
            (root / "memory/history/pending-delete").symlink_to(outside)
        return names
    monkeypatch.setattr(pre.os, "listdir", listdir_then_swap)
    result = check(root, tmp_path)
    assert done and result["result"] in ("FAIL", "UNKNOWN") and result["result"] != "PASS"


@pytest.mark.skipif(os.geteuid() == 0, reason="needs an ordinary UID that really owns the files")
def test_running_as_the_service_account_itself_passes_with_real_metadata(tmp_path):
    root = layout(tmp_path)
    result = pre.check_canonical_owner(str(root), "svc", lookup=lambda name: (os.geteuid(), None))
    assert result["result"] == "PASS"


def test_simulated_owner_for_the_service_account_still_passes(tmp_path):
    assert check(layout(tmp_path), tmp_path, uid=SERVICE, lstat=owners(tmp_path))["result"] == "PASS"
