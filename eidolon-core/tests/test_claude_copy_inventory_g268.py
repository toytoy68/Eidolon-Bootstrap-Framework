# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_copy_inventory_g268.py
# Description : Contre-revue du contrôle final G268 : descripteurs, substitutions en profondeur, limites (Claude)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic trees under tmp_path only. Descriptor limits are lowered inside a CHILD process, never here."""
import os
import stat
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.test_claude_copy_inventory_g262 import TOOL, inv

pytestmark = pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc/self/fd")


def refused(call):
    with pytest.raises(inv.InventoryRefused) as caught:
        call()
    return caught.value.code


def open_fds():
    return sorted(os.listdir("/proc/self/fd"))


def wide(tmp_path, n=120):
    root = tmp_path / "wide"
    for i in range(n):
        (root / f"d{i:03}").mkdir(parents=True)
        (root / f"d{i:03}/f").write_text("x")
    return root


def deep(tmp_path, depth):
    root = tmp_path / "deep"
    leaf = root.joinpath(*[f"l{i}" for i in range(depth)])
    leaf.mkdir(parents=True)
    (leaf / "f").write_text("x")
    return root


def child(tree, limit, *, final_limit=None):
    """Inventory of `tree` in a child process with RLIMIT_NOFILE=limit (lowered to final_limit just before
    the final check). Prints 'OK <n>' or the refusal code."""
    script = textwrap.dedent(f"""
        import importlib.util, resource
        spec = importlib.util.spec_from_file_location("inv", {str(TOOL)!r})
        inv = importlib.util.module_from_spec(spec); spec.loader.exec_module(inv)
        resource.setrlimit(resource.RLIMIT_NOFILE, ({limit}, {limit}))
        if {final_limit!r} is not None:
            inv._before_final = lambda: resource.setrlimit(resource.RLIMIT_NOFILE, ({final_limit!r},) * 2)
        try:
            print("OK", len(inv.inventory({str(tree)!r}, max_entries=10000, max_bytes=10**6)))
        except inv.InventoryRefused as exc:
            print(exc.code)
    """)
    r = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip()


# --- 1. descriptors: a WIDE unchanged tree is never "changed" nor "unreadable" -----------------------

def test_a_wide_tree_needs_descriptors_for_its_depth_not_its_width(tmp_path):
    """120 sibling directories under a 64-descriptor limit: an unchanged, readable tree."""
    assert child(wide(tmp_path), 64) == "OK 240"


def test_the_final_check_never_reports_an_unchanged_wide_tree_as_changed(tmp_path):
    assert child(wide(tmp_path), 400, final_limit=64) == "OK 240"


@pytest.mark.parametrize("final", [False, True])
def test_descriptor_exhaustion_has_its_own_code(tmp_path, final):
    """Depth beyond the limit: a resource refusal, never INVENTORY_CHANGED or INVENTORY_UNREADABLE."""
    tree = deep(tmp_path, 60)
    outcome = child(tree, 400, final_limit=40) if final else child(tree, 40)
    assert outcome == "INVENTORY_RESOURCE"


@pytest.mark.parametrize("where", ["root", "dir", "file", "final-dir"])
def test_exhaustion_at_any_open_is_a_resource_refusal_and_closes_everything(tmp_path, monkeypatch, where):
    root = nested(tmp_path)
    real_open, active = os.open, []
    target = {"root": "src", "dir": "b", "file": "two", "final-dir": "b"}[where]
    if where == "final-dir":
        monkeypatch.setattr(inv, "_before_final", lambda: active.append(True))
    else:
        active.append(True)

    def exhausted(path, flags, *args, **kwargs):
        if active and path == target:
            raise OSError(24, "Too many open files")
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(inv.os, "open", exhausted)
    before = open_fds()
    assert refused(lambda: inv.inventory(root, max_entries=100, max_bytes=10**6)) == "INVENTORY_RESOURCE"
    assert open_fds() == before


def test_the_cli_reports_exhaustion_as_unknown_not_as_a_refused_tree(tmp_path):
    import json
    tree = deep(tmp_path, 60)
    script = (f"import resource, runpy, sys; resource.setrlimit(resource.RLIMIT_NOFILE, (40, 40)); "
              f"sys.argv = ['inv', '--source', {str(tree)!r}, '--copy', {str(tree)!r}, '--max-entries', '1000', "
              f"'--max-bytes', '1000000']; runpy.run_path({str(TOOL)!r}, run_name='__main__')")
    r = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=60)
    report = json.loads(r.stdout)
    assert r.returncode == 2 and report["verdict"] == "UNKNOWN" and report["code"] == "INVENTORY_RESOURCE"


# --- 2. every refusal closes what it opened -------------------------------------------------------

def nested(tmp_path):
    root = tmp_path / "src"
    (root / "a/b/c").mkdir(parents=True)
    for rel in ("top", "a/one", "a/b/two", "a/b/c/three"):
        (root / rel).write_text(rel)
    (tmp_path / "outside/b/c").mkdir(parents=True)
    (tmp_path / "outside/b/c/private").write_text("private")
    return root


CHANGES = {
    "added": lambda r, t: (r / "a/b/new").write_text("n"),
    "removed": lambda r, t: (r / "a/b/two").unlink(),
    "modified": lambda r, t: (r / "a/b/c/three").write_text("changed!"),
    "dir-by-link": lambda r, t: ((r / "a").rename(t / "old-a"), (r / "a").symlink_to(t / "outside")),
    "dir-by-dir": lambda r, t: ((r / "a").rename(t / "old-a"), (t / "outside").rename(r / "a")),
    "file-by-link": lambda r, t: ((r / "a/one").unlink(), (r / "a/one").symlink_to(t / "outside/b/c/private")),
}


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_every_final_refusal_closes_its_descriptors(tmp_path, monkeypatch, change):
    root = nested(tmp_path)
    monkeypatch.setattr(inv, "_before_final", lambda: CHANGES[change](root, tmp_path))
    before = open_fds()
    assert refused(lambda: inv.inventory(root, max_entries=100, max_bytes=10**6)) == "INVENTORY_CHANGED"
    assert open_fds() == before


def test_success_closes_its_descriptors(tmp_path):
    root = nested(tmp_path)
    before = open_fds()
    assert len(inv.inventory(root, max_entries=100, max_bytes=10**6)) == 7
    assert open_fds() == before


# --- 3. substitution at any depth during the final pass: nothing outside is listed or opened ---------

@pytest.mark.parametrize("moment", ["stat", "open"])                   # before its stat, or between stat and open
@pytest.mark.parametrize("replacement", ["symlink", "directory"])
@pytest.mark.parametrize("level", ["a", "a/b", "a/b/c"])
def test_a_substitution_at_any_depth_during_the_final_pass_is_never_traversed(tmp_path, monkeypatch,
                                                                              level, replacement, moment):
    root = nested(tmp_path)
    outside = tmp_path / "outside"
    foreign = {p.stat().st_ino for p in [outside, *outside.rglob("*")]}
    inside = foreign - {outside.stat().st_ino}            # opening the substitute itself only reads its identity
    real_stat, real_listdir, real_open = os.stat, os.listdir, os.open
    active, done, touched = [], [], []
    monkeypatch.setattr(inv, "_before_final", lambda: active.append(True))

    def swap(path, when):
        if active and not done and when == moment and path == Path(level).name:   # final pass reaches `level`
            done.append(True)
            target = root / level
            target.rename(tmp_path / "moved")
            if replacement == "symlink":
                target.symlink_to(outside, target_is_directory=True)
            else:
                outside.rename(target)

    def stat_then_swap(path, *args, **kwargs):
        swap(path, "stat")
        return real_stat(path, *args, **kwargs)

    def watch_list(fd):
        if active and isinstance(fd, int) and os.fstat(fd).st_ino in foreign:
            touched.append("listdir")
        return real_listdir(fd)

    def watch_open(path, flags, *args, **kwargs):
        swap(path, "open")
        fd = real_open(path, flags, *args, **kwargs)
        if active and os.fstat(fd).st_ino in inside:
            touched.append("open")
        return fd
    monkeypatch.setattr(inv.os, "stat", stat_then_swap)
    monkeypatch.setattr(inv.os, "listdir", watch_list)
    monkeypatch.setattr(inv.os, "open", watch_open)
    assert refused(lambda: inv.inventory(root, max_entries=100, max_bytes=10**6)) == "INVENTORY_CHANGED"
    assert done and touched == []


# --- 4. the non-atomic limit is still real, and still stated ---------------------------------------

def test_change_after_final_metadata_is_caught_by_content_check(tmp_path, monkeypatch):
    """G277 now re-reads content after the final metadata check."""
    assert "not an atomic snapshot" in inv.inventory.__doc__
    root = nested(tmp_path)
    real_stat, active, done = os.stat, [], []
    monkeypatch.setattr(inv, "_before_final", lambda: active.append(True))

    def stat_then_change(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if active and path == "top" and not done:                    # already re-checked: change it now
            done.append(True)
            (root / "top").write_text("changed behind the check")
        return result
    monkeypatch.setattr(inv.os, "stat", stat_then_change)
    assert refused(lambda: inv.inventory(root, max_entries=100, max_bytes=10**6)) == "INVENTORY_CHANGED"
    assert done


@pytest.mark.parametrize("coarse_timestamps", [False, True])
def test_a_directory_changed_while_its_subtree_is_rechecked_is_caught_after_the_visit(tmp_path, monkeypatch, coarse_timestamps):
    """`a/b` is listed (same names), then gains an entry while `a/b/c` is visited: only the version check
    AFTER the subtree sees it."""
    root = nested(tmp_path)
    if coarse_timestamps:
        real_version = inv._version
        monkeypatch.setattr(inv, "_version", lambda value: (
            (*real_version(value)[:3], 0, 0, 0) if stat.S_ISDIR(value.st_mode) else real_version(value)))
    real_stat, active, done = os.stat, [], []
    monkeypatch.setattr(inv, "_before_final", lambda: active.append(True))

    def stat_then_add(path, *args, **kwargs):
        if active and path == "three" and not done:
            done.append(True)
            (root / "a/b/late").write_text("late")
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(inv.os, "stat", stat_then_add)
    assert refused(lambda: inv.inventory(root, max_entries=100, max_bytes=10**6)) == "INVENTORY_CHANGED"
    assert done


def test_change_after_completed_final_pass_still_requires_stopped_tree(tmp_path, monkeypatch):
    root = nested(tmp_path)
    final = inv._final_check
    def changed_after_completion(*args):
        final(*args)
        (root/'top').write_text('changed after completed checks')
    monkeypatch.setattr(inv, '_final_check', changed_after_completion)
    result = inv.inventory(root, max_entries=100, max_bytes=10**6)
    assert result['top']['size'] == 3
    assert 'not an atomic snapshot' in inv.inventory.__doc__
