# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_preflight_account_g262.py
# Description : Préflight opt-in du propriétaire de la mémoire, métadonnées simulées (Claude, G262-1)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""No chown, no useradd: owners are rewritten in a stat wrapper; the files are synthetic."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "claude_offline_preflight_g262", Path(__file__).resolve().parents[1] / "tools" / "claude_offline_preflight.py")
pre = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pre)

SERVICE = 4242


def layout(tmp_path):
    root = tmp_path / "bridge-root"
    for part in ("memory/persistent", "memory/history/pending-delete"):
        (root / part).mkdir(parents=True)
    for d in [root / "memory", root / "memory/persistent", root / "memory/history",
              root / "memory/history/pending-delete"]:
        d.chmod(0o700)
    for name in ("a.md", ".write.lock"):
        f = root / "memory/persistent" / name
        f.write_text("x")
        f.chmod(0o600)
    return root


def owners(tmp_path, foreign=(), mode=None):
    """lstat that reports SERVICE as owner of everything under tmp_path, except the `foreign` paths."""
    def fake(path):
        st = os.lstat(path)
        p = Path(path)
        if tmp_path not in p.parents and p != tmp_path:
            return st
        uid = 1000 if p in foreign else SERVICE
        m = mode(p, st.st_mode) if mode else st.st_mode
        return SimpleNamespace(st_mode=m, st_uid=uid)
    return fake


def check(root, tmp_path, account="eidolon-memory", uid=SERVICE, **options):
    lookup = lambda name: (uid, None) if uid is not None else (None, "service account not found")
    options.setdefault("lstat", owners(tmp_path))
    return pre.check_canonical_owner(str(root), account, lookup=lookup, **options)


def test_owned_private_layout_passes_and_counts_entries(tmp_path):
    root = layout(tmp_path)
    result = check(root, tmp_path)
    assert result["result"] == "PASS" and result["detail"].startswith("3 entries")


def test_a_recipe_run_under_the_service_account_itself_is_allowed(tmp_path):
    root = layout(tmp_path)
    assert check(root, tmp_path, uid=SERVICE)["result"] == "PASS"   # no "must differ from euid" rule


@pytest.mark.parametrize("uid, expected", [(None, "UNKNOWN"), (0, "FAIL")])
def test_absent_or_root_account(tmp_path, uid, expected):
    assert check(layout(tmp_path), tmp_path, uid=uid)["result"] == expected


def test_no_posix_account_database_is_unknown(tmp_path, monkeypatch):
    import builtins
    real = builtins.__import__
    monkeypatch.setattr(builtins, "__import__",
                        lambda name, *a, **k: (_ for _ in ()).throw(ImportError()) if name == "pwd" else real(name, *a, **k))
    assert pre._lookup_account("eidolon-memory") == (None, "no POSIX account database on this platform")


@pytest.mark.parametrize("target", ["memory", "memory/persistent/a.md", "memory/persistent", "memory/history/pending-delete"])
def test_another_owner_anywhere_fails(tmp_path, target):
    root = layout(tmp_path)
    result = check(root, tmp_path, lstat=owners(tmp_path, foreign={root / target}))
    assert result["result"] == "FAIL"


def test_shared_modes_links_and_special_files_fail(tmp_path):
    root = layout(tmp_path)
    shared = owners(tmp_path, mode=lambda p, m: m | 0o040 if p.name == "a.md" else m)
    assert check(root, tmp_path, lstat=shared)["result"] == "FAIL"
    (root / "memory/persistent/link.md").symlink_to(root / "memory/persistent/a.md")
    assert "link" in check(root, tmp_path)["detail"]
    (root / "memory/persistent/link.md").unlink()
    os.mkfifo(root / "memory/history/fifo")
    assert check(root, tmp_path)["result"] == "FAIL"


def test_layout_and_root_errors(tmp_path):
    root = layout(tmp_path)
    assert check(tmp_path / "missing", tmp_path)["result"] == "FAIL"
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert check(alias, tmp_path)["result"] == "FAIL"                      # root reached through a link
    assert check("relative/root", tmp_path)["result"] == "UNKNOWN"
    flat = tmp_path / "flat"
    (flat / "memory/persistent").mkdir(parents=True)                         # history missing
    assert check(flat, tmp_path)["result"] == "FAIL"
    for bad in ("", "a b", "x" * 33, None):
        assert check(root, tmp_path, account=bad)["result"] in ("FAIL", "UNKNOWN")


def test_entry_budget_is_unknown_not_pass(tmp_path):
    root = layout(tmp_path)
    assert check(root, tmp_path, max_entries=2)["result"] == "UNKNOWN"


def test_opt_in_only_and_wired_into_run(tmp_path, monkeypatch):
    base = dict(core=None, memory=None, expect_core=None, expect_memory=None, data_dir=None,
                min_free_bytes=None, credential=None)
    names = [c["check"] for c in pre.run(SimpleNamespace(**base))["checks"]]
    assert "memory.canonical_owner" not in names
    monkeypatch.setattr(pre, "_lookup_account", lambda name: (None, "service account not found"))
    report = pre.run(SimpleNamespace(**base, memory_root=str(layout(tmp_path)), service_account="eidolon-memory"))
    assert report["checks"][-1] == {"check": "memory.canonical_owner", "result": "UNKNOWN",
                                    "detail": "service account not found"}


def test_nothing_is_opened_or_changed(tmp_path, monkeypatch):
    root = layout(tmp_path)
    before = {p: (p.stat().st_mtime_ns, p.stat().st_mode) for p in root.rglob("*")}
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("opened")))
    assert check(root, tmp_path)["result"] == "PASS"
    monkeypatch.undo()
    assert before == {p: (p.stat().st_mtime_ns, p.stat().st_mode) for p in root.rglob("*")}
