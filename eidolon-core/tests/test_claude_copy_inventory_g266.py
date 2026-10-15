# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_copy_inventory_g266.py
# Description : Inventaire de copie : ancêtres liés, dossiers substitués, cohérence d'ensemble, budgets (G266-1/2/3)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic trees only. Every case here was a silent acceptance, a raw error or an unchecked mix on the
G262 tool; the reproductions of G266-1 come first."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.test_claude_copy_inventory_g262 import TOOL, SECRET, inv, tree

BUDGET = dict(max_entries=100, max_bytes=1 << 20)


def code_of(call):
    with pytest.raises(inv.InventoryRefused) as caught:
        call()
    return caught.value.code


# --- G266-1: ancestors and substituted directories --------------------------------------------------

@pytest.mark.parametrize("where", ["root", "middle"])
def test_a_linked_ancestor_is_refused_never_resolved(tmp_path, where):
    real = tree(tmp_path / "real")
    if where == "root":
        (tmp_path / "alias").symlink_to(real)
        target = tmp_path / "alias"
    else:
        (tmp_path / "alias").symlink_to(real / "memory")
        target = tmp_path / "alias" / "persistent"
    assert code_of(lambda: inv.inventory(str(target), **BUDGET)) == "INVENTORY_PATH"


def test_a_directory_replaced_by_a_link_after_listing_is_never_followed(tmp_path, monkeypatch):
    source = tree(tmp_path / "source")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.md").write_text("OUTSIDE-SECRET")
    real_listdir = os.listdir
    swapped = []

    def listdir_then_swap(fd):
        names = real_listdir(fd)
        if "threads" in names and not swapped:           # just listed persistent/: swap threads/ for a link
            swapped.append(1)
            shutil.rmtree(source / "memory/persistent/threads")
            (source / "memory/persistent/threads").symlink_to(outside)
        return names
    monkeypatch.setattr(inv.os, "listdir", listdir_then_swap)
    hashed = []
    monkeypatch.setattr(inv, "_after_hash", hashed.append)
    assert code_of(lambda: inv.inventory(str(source), **BUDGET)) in ("INVENTORY_RACE", "INVENTORY_LINK_OR_SPECIAL")
    assert swapped and not any("private" in h for h in hashed)    # the outside file was never read


def test_a_directory_swapped_for_another_directory_between_stat_and_open_is_a_race(tmp_path, monkeypatch):
    source = tree(tmp_path / "source")
    real_open = os.open
    done = []

    def open_then(path, flags, *a, **k):
        if path == "threads" and not done and flags & os.O_DIRECTORY:
            done.append(1)
            os.rename(source / "memory/persistent/threads", tmp_path / "moved")
            (source / "memory/persistent/threads").mkdir()
        return real_open(path, flags, *a, **k)
    monkeypatch.setattr(inv.os, "open", open_then)
    assert code_of(lambda: inv.inventory(str(source), **BUDGET)) == "INVENTORY_RACE"


# --- G266-2: coherence of the whole tree ------------------------------------------------------------

@pytest.mark.parametrize("change", ["modify-hashed", "delete-hashed", "add-entry", "add-dir", "touch-dir"])
def test_a_change_after_an_entry_was_hashed_is_caught_by_the_final_check(tmp_path, monkeypatch, change):
    source = tree(tmp_path / "source")

    def mutate():
        a = source / "memory/persistent/a.md"
        if change == "modify-hashed":
            a.write_text(SECRET.upper())
        elif change == "delete-hashed":
            a.unlink()
        elif change == "add-entry":
            (source / "memory/persistent/new.md").write_text("x")
        elif change == "add-dir":
            (source / "memory/history/late").mkdir()
        else:
            os.utime(source / "memory/persistent/a.md", ns=(1, 1))     # metadata only
    monkeypatch.setattr(inv, "_before_final", mutate)
    assert code_of(lambda: inv.inventory(str(source), **BUDGET)) == "INVENTORY_CHANGED"


def test_without_the_final_check_the_guarantee_is_explicitly_weaker(tmp_path, monkeypatch):
    source = tree(tmp_path / "source")
    monkeypatch.setattr(inv, "_before_final", lambda: (source / "memory/persistent/new.md").write_text("x"))
    result = inv.inventory(str(source), final_check=False, **BUDGET)   # documented: per-entry checks only
    assert "memory/persistent/new.md" not in result


# --- G266-3: budgets and errors -----------------------------------------------------------------------

@pytest.mark.parametrize("chunk", [0, -1, True, 1.0, 64 * 1024 * 1024 + 1, 10 ** 30])
def test_invalid_chunk_sizes_are_refused(tmp_path, chunk):
    source = tree(tmp_path / "source")
    assert code_of(lambda: inv.inventory(str(source), chunk=chunk, **BUDGET)) == "INVENTORY_BUDGET"


def test_a_tiny_chunk_still_gives_the_same_digests(tmp_path):
    source = tree(tmp_path / "source")
    assert inv.inventory(str(source), chunk=1, **BUDGET) == inv.inventory(str(source), **BUDGET)


def test_growth_while_reading_is_caught_and_the_byte_budget_counts_real_reads(tmp_path, monkeypatch):
    source = tree(tmp_path / "source")
    real_read = os.read
    grown = []

    def read_then_grow(fd, n):
        data = real_read(fd, n)
        if not grown and data:
            grown.append(1)
            with open(source / "memory/persistent/a.md", "a") as handle:
                handle.write("!" * 1000)
        return data
    monkeypatch.setattr(inv.os, "read", read_then_grow)
    assert code_of(lambda: inv.inventory(str(source), **BUDGET)) == "INVENTORY_RACE"
    monkeypatch.undo()
    exact = sum(len(p.read_bytes()) for p in source.rglob("*") if p.is_file())
    assert inv.inventory(str(source), max_entries=100, max_bytes=exact)
    assert code_of(lambda: inv.inventory(str(source), max_entries=100, max_bytes=exact - 1)) \
        == "INVENTORY_BYTE_BUDGET"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode bits; run under an ordinary UID")
def test_unreadable_entries_give_a_stable_code_in_api_and_cli(tmp_path):
    source = tree(tmp_path / "source")
    for target in (source / "memory/persistent/a.md", source / "memory/history"):
        target.chmod(0)
        try:
            assert code_of(lambda: inv.inventory(str(source), **BUDGET)) == "INVENTORY_UNREADABLE"
            r = subprocess.run([sys.executable, str(TOOL), "--source", str(source), "--copy", str(source),
                                "--max-entries", "100", "--max-bytes", "1000000"], capture_output=True, text=True)
            report = json.loads(r.stdout)
            assert r.returncode == 2 and report["code"] == "INVENTORY_UNREADABLE" and SECRET not in r.stdout
        finally:
            target.chmod(0o755 if target.is_dir() else 0o644)


def test_cli_refusals_never_print_content(tmp_path):
    source = tree(tmp_path / "source")
    (tmp_path / "alias").symlink_to(source)
    for args in (["--source", str(tmp_path / "alias"), "--copy", str(source)],
                 ["--source", str(source), "--copy", str(source), "--max-entries", "1"]):
        full = args + (["--max-entries", "100"] if "--max-entries" not in args else []) + ["--max-bytes", "1000000"]
        r = subprocess.run([sys.executable, str(TOOL), *full], capture_output=True, text=True)
        report = json.loads(r.stdout)
        assert r.returncode == 2 and report["verdict"] == "REFUSED" and SECRET not in r.stdout + r.stderr
