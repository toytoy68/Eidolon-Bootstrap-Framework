# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_reranker_cache_g266.py
# Description : Préflight du cache reranker : ancêtres liés, refs/main substitué ou gonflé, sorties de racine (G266-4)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic cache layouts only; nothing is loaded or downloaded."""
import os
import shutil

import pytest

from tests.test_claude_reranker_cache_g262 import COMMIT, cache, pre


def result(base):
    return pre.check_reranker_cache(str(base))


def relink(path, target, *, directory=True):
    moved = path.with_name(path.name + ".real")
    shutil.move(str(path), str(moved))
    path.symlink_to(target if target is not None else moved, target_is_directory=directory)


@pytest.mark.parametrize("part", ["model", "refs", "snapshots", "commit", "blobs"])
def test_a_link_at_any_level_of_the_model_is_refused(tmp_path, part):
    base, model = cache(tmp_path)
    path = {"model": model, "refs": model / "refs", "snapshots": model / "snapshots",
            "commit": model / "snapshots" / COMMIT, "blobs": model / "blobs"}[part]
    relink(path, None)                                   # same content, reached through a link
    assert result(base)["result"] == "FAIL", part


def test_a_linked_ancestor_of_the_cache_is_refused(tmp_path):
    base, _ = cache(tmp_path / "real")
    (tmp_path / "alias").symlink_to(tmp_path / "real")
    assert result(tmp_path / "alias" / "cache")["result"] == "FAIL"


@pytest.mark.parametrize("content", [COMMIT + "\n", COMMIT + "0" * 5000, COMMIT[:-1]])
def test_refs_main_is_read_with_a_hard_bound(tmp_path, content):
    base, model = cache(tmp_path)
    (model / "refs/main").write_text(content)
    assert result(base)["detail"] == "refs/main missing or malformed"


def test_refs_main_substituted_by_a_fifo_or_link_never_blocks_nor_passes(tmp_path):
    base, model = cache(tmp_path)
    (model / "refs/main").unlink()
    os.mkfifo(model / "refs/main")                       # an open without O_NONBLOCK would hang here
    assert result(base)["result"] == "FAIL"
    (model / "refs/main").unlink()
    (tmp_path / "ref").write_text(COMMIT)
    (model / "refs/main").symlink_to(tmp_path / "ref")
    assert result(base)["result"] == "FAIL"


@pytest.mark.parametrize("target", ["../../blobs/../../../outside", "../../../escape/b0", "/abs/b0",
                                    "../../blobs/sub/b0", "../blobs/b0"])
def test_snapshot_links_must_stay_inside_this_model(tmp_path, target):
    base, model = cache(tmp_path)
    link = model / "snapshots" / COMMIT / "config.json"
    link.unlink()
    link.symlink_to(target)
    assert result(base)["result"] == "FAIL"


def test_a_blob_that_is_itself_a_link_is_refused(tmp_path):
    base, model = cache(tmp_path)
    (tmp_path / "outside").write_text("{}")
    (model / "blobs/b0").unlink()
    (model / "blobs/b0").symlink_to(tmp_path / "outside")
    assert result(base)["result"] == "FAIL"


def test_pass_states_metadata_only_and_never_a_load(tmp_path):
    base, _ = cache(tmp_path)
    detail = result(base)["detail"]
    assert result(base)["result"] == "PASS" and "metadata only" in detail and "NOT loaded" in detail
