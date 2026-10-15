# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_copy_inventory_final_g268.py
# Description : Ne pas parcourir un ancêtre substitué pendant le contrôle final
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Independent regression for a nested ancestor changed after final root validation."""
import os

import pytest
from tests.test_claude_copy_inventory_g262 import inv


@pytest.mark.parametrize('replacement', ['symlink', 'directory'])
def test_final_check_does_not_list_a_substituted_tree(tmp_path, monkeypatch, replacement):
    root = tmp_path / 'source'
    (root / 'a/b').mkdir(parents=True)
    (root / 'a/b/data').write_text('canonical')
    outside = tmp_path / 'outside'
    (outside / 'b').mkdir(parents=True)
    (outside / 'b/private').write_text('private')
    external = (outside / 'b').stat().st_ino
    real_stat, real_listdir = os.stat, os.listdir
    active, swapped, visited = [], [], []
    monkeypatch.setattr(inv, '_before_final', lambda: active.append(True))
    def replace_before_nested_stat(path, *args, **kwargs):
        # G266 uses a/b; the safe implementation uses b relative to an already-open a.
        if active and path in ('a/b', 'b') and not swapped:
            swapped.append(True)
            (root / 'a').rename(tmp_path / 'original-a')
            if replacement == 'symlink':
                (root / 'a').symlink_to(outside, target_is_directory=True)
            else:
                outside.rename(root / 'a')
        return real_stat(path, *args, **kwargs)
    def observe_list(fd):
        if active and isinstance(fd, int) and os.fstat(fd).st_ino == external:
            visited.append(True)
        return real_listdir(fd)
    monkeypatch.setattr(inv.os, 'stat', replace_before_nested_stat)
    monkeypatch.setattr(inv.os, 'listdir', observe_list)
    with pytest.raises(inv.InventoryRefused) as caught:
        inv.inventory(root, max_entries=10, max_bytes=100)
    assert caught.value.code == 'INVENTORY_CHANGED'
    assert swapped
    assert not visited, 'final check listed a substituted tree outside its opened descriptors'
