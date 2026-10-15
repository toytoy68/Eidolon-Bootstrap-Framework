# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_copy_inventory_g262.py
# Description : Inventaire de migration par copie : identique, manquants, ajouts, courses, liens, budgets (G262-4)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic trees only; the tool is read-only and never prints content."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "claude_copy_inventory.py"
SPEC = importlib.util.spec_from_file_location("claude_copy_inventory", TOOL)
inv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inv)

SECRET = "contenu-privé-à-ne-jamais-afficher"


def tree(base):
    for rel, text in {"memory/persistent/a.md": SECRET, "memory/persistent/threads/t.md": "fil",
                      "memory/history/pending-delete/.keep": "", "memory/persistent/.write.lock": ""}.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return base


def pair(tmp_path):
    source = tree(tmp_path / "source")
    copy = tmp_path / "copy"
    shutil.copytree(source, copy)
    return source, copy


def run(source, copy, **budget):
    budget = {"max_entries": 100, "max_bytes": 1 << 20, **budget}
    return inv.compare(inv.inventory(source, **budget), inv.inventory(copy, **budget))


def test_an_exact_copy_is_identical_even_with_other_owner_or_mode(tmp_path):
    source, copy = pair(tmp_path)
    (copy / "memory/persistent/a.md").chmod(0o600)
    report = run(source, copy)
    assert report["identical"] and report["entries"] == {"source": 9, "copy": 9}
    assert [m["path"] for m in report["metadata"]] == ["memory/persistent/a.md"]   # reported, not a difference


def test_missing_added_and_changed_are_reported_separately(tmp_path):
    source, copy = pair(tmp_path)
    (copy / "memory/persistent/threads/t.md").unlink()
    (copy / "memory/persistent/new.md").write_text("x")
    (copy / "memory/persistent/a.md").write_text(SECRET.upper())          # same size, other bytes
    report = run(source, copy)
    assert not report["identical"]
    assert report["content"] == {"missing": ["memory/persistent/threads/t.md"],
                                 "added": ["memory/persistent/new.md"], "changed": ["memory/persistent/a.md"]}


def test_a_directory_replaced_by_a_file_is_a_change(tmp_path):
    source, copy = pair(tmp_path)
    shutil.rmtree(copy / "memory/history/pending-delete")
    (copy / "memory/history/pending-delete").write_text("")
    report = run(source, copy)
    assert "memory/history/pending-delete" in report["content"]["changed"]


@pytest.mark.parametrize("make", ["symlink", "fifo", "dir-symlink"])
def test_links_and_special_files_are_refused(tmp_path, make):
    source, copy = pair(tmp_path)
    target = copy / "memory/persistent/odd"
    if make == "symlink":
        target.symlink_to(copy / "memory/persistent/a.md")
    elif make == "fifo":
        os.mkfifo(target)
    else:
        target.symlink_to(copy / "memory/history", target_is_directory=True)
    with pytest.raises(inv.InventoryRefused) as caught:
        run(source, copy)
    assert caught.value.code == "INVENTORY_LINK_OR_SPECIAL"


@pytest.mark.parametrize("change", ["append", "rewrite", "replace", "remove"])
def test_a_file_changing_while_hashed_is_a_race(tmp_path, monkeypatch, change):
    source = tree(tmp_path / "source")
    victim = source / "memory/persistent/a.md"

    def hook(rel):
        if rel != "memory/persistent/a.md":
            return
        if change == "append":
            with open(victim, "a") as handle:
                handle.write("!")
        elif change == "rewrite":
            victim.write_text(SECRET.upper())
        elif change == "replace":
            (source / "tmp").write_text(SECRET)
            os.replace(source / "tmp", victim)
        else:
            victim.unlink()
    monkeypatch.setattr(inv, "_after_hash", hook)
    with pytest.raises(inv.InventoryRefused) as caught:
        inv.inventory(source, max_entries=100, max_bytes=1 << 20)
    assert caught.value.code == "INVENTORY_RACE"


def test_budgets_are_explicit_and_exceeding_one_is_not_a_pass(tmp_path):
    source, _ = pair(tmp_path)
    with pytest.raises(inv.InventoryRefused, match="INVENTORY_ENTRY_BUDGET"):
        inv.inventory(source, max_entries=3, max_bytes=1 << 20)
    with pytest.raises(inv.InventoryRefused, match="INVENTORY_BYTE_BUDGET"):
        inv.inventory(source, max_entries=100, max_bytes=len(SECRET.encode()) - 1)
    for bad in (0, -1, True, 1.5):
        with pytest.raises(inv.InventoryRefused, match="INVENTORY_BUDGET"):
            inv.inventory(source, max_entries=bad, max_bytes=10)
    for root in ("relative", str(tmp_path / "absent"), str(source / "memory/persistent/a.md")):
        with pytest.raises(inv.InventoryRefused, match="INVENTORY_PATH"):
            inv.inventory(root, max_entries=10, max_bytes=10)


def cli(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, json.loads(r.stdout)


def test_the_command_never_prints_content_and_never_writes(tmp_path):
    source, copy = pair(tmp_path)
    before = {p: (p.stat().st_mtime_ns, p.stat().st_mode) for p in tmp_path.rglob("*")}
    code, raw, report = cli("--source", str(source), "--copy", str(copy), "--max-entries", "100",
                            "--max-bytes", "1000000")
    assert (code, report["verdict"]) == (0, "IDENTICAL") and SECRET not in raw
    (copy / "memory/persistent/a.md").write_text("autre")
    code, raw, report = cli("--source", str(source), "--copy", str(copy), "--max-entries", "100",
                            "--max-bytes", "1000000")
    assert (code, report["verdict"]) == (1, "DIFFERENT") and SECRET not in raw and "autre" not in raw
    code, _, report = cli("--source", str(source), "--copy", str(copy), "--max-entries", "2",
                          "--max-bytes", "1000000")
    assert (code, report["code"]) == (2, "INVENTORY_ENTRY_BUDGET")
    after = {p: (p.stat().st_mtime_ns, p.stat().st_mode) for p in tmp_path.rglob("*")}
    assert {p: v for p, v in after.items() if p != copy / "memory/persistent/a.md"} == \
        {p: v for p, v in before.items() if p != copy / "memory/persistent/a.md"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file; run under an ordinary UID")
def test_an_unreadable_file_is_unknown_not_identical(tmp_path):
    source, copy = pair(tmp_path)
    (copy / "memory/persistent/a.md").chmod(0)
    try:
        code, _, report = cli("--source", str(source), "--copy", str(copy), "--max-entries", "100",
                              "--max-bytes", "1000000")
        assert (code, report["verdict"]) == (2, "UNKNOWN")
    finally:
        (copy / "memory/persistent/a.md").chmod(0o644)
