# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_reranker_cache_g262.py
# Description : Préflight du cache reranker hors ligne : complet, préparé, liens contenus (Claude, G262-6)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic cache layout only: no model, no download, no torch."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "claude_offline_preflight_rr", Path(__file__).resolve().parents[1] / "tools" / "claude_offline_preflight.py")
pre = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pre)

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def cache(tmp_path, *, files=("config.json", "tokenizer_config.json", "model.safetensors"), prepared=True):
    base = tmp_path / "cache"
    model = base / "models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1"
    (model / "refs").mkdir(parents=True)
    (model / "blobs").mkdir()
    (model / "snapshots" / COMMIT).mkdir(parents=True)
    (model / "refs/main").write_text(COMMIT)
    for n, name in enumerate(files):
        (model / "blobs" / f"b{n}").write_text("{}")
        (model / "snapshots" / COMMIT / name).symlink_to(f"../../blobs/b{n}")
    if prepared:
        (base / "version.txt").write_text("1")
    return base, model


def result(base):
    return pre.check_reranker_cache(str(base))


def test_a_complete_prepared_cache_passes(tmp_path):
    base, _ = cache(tmp_path)
    assert result(base)["result"] == "PASS"


def test_an_unprepared_cache_fails_with_the_real_cause(tmp_path):
    base, _ = cache(tmp_path, prepared=False)
    assert result(base) == {"check": "reranker.cache", "result": "FAIL",
                            "detail": "cache not prepared: version.txt missing, transformers would try to write it"}


@pytest.mark.parametrize("files, missing", [(("config.json", "tokenizer_config.json"), "model.safetensors"),
                                            (("tokenizer_config.json", "pytorch_model.bin"), "config.json")])
def test_an_incomplete_cache_names_what_is_missing(tmp_path, files, missing):
    base, _ = cache(tmp_path, files=files)
    assert missing in result(base)["detail"] and result(base)["result"] == "FAIL"


def test_either_weight_format_is_accepted(tmp_path):
    base, _ = cache(tmp_path, files=("config.json", "tokenizer_config.json", "pytorch_model.bin"))
    assert result(base)["result"] == "PASS"


def test_links_escaping_the_model_or_absolute_are_refused(tmp_path):
    base, model = cache(tmp_path)
    link = model / "snapshots" / COMMIT / "config.json"
    (tmp_path / "outside").write_text("{}")
    link.unlink()
    link.symlink_to("../../../../outside")
    assert result(base)["result"] == "FAIL"
    link.unlink()
    link.symlink_to(str(model / "blobs/b0"))                          # absolute, even if inside
    assert result(base)["result"] == "FAIL"


def test_malformed_ref_and_unusable_paths(tmp_path):
    base, model = cache(tmp_path)
    (model / "refs/main").write_text("main")
    assert result(base)["detail"] == "refs/main missing or malformed"
    (model / "refs/main").write_text("Z" * 40)
    assert result(base)["result"] == "FAIL"
    assert pre.check_reranker_cache(None)["result"] == "UNKNOWN"
    assert pre.check_reranker_cache("relative")["result"] == "UNKNOWN"
    assert pre.check_reranker_cache(str(tmp_path / "absent"))["result"] == "FAIL"
