# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_bridge_credentials_g235.py
# Description : Lecture bornée et ancrée du secret BridgeMemory, sans réseau.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from eidolon_core.memory import BridgeMemory


@pytest.fixture
def credential(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    path = parent / "token"
    path.write_text("x" * 64 + "\n")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize("kind", ["oversized", "short", "control", "hardlink", "parent_public", "parent_link"])
def test_unsafe_secret_refused_before_network(credential, tmp_path, kind):
    path = credential
    if kind == "oversized":
        path.write_text("x" * 4097)
    elif kind == "short":
        path.write_text("x" * 31)
    elif kind == "control":
        path.write_text("x" * 40 + "\x00")
    elif kind == "hardlink":
        os.link(path, path.parent / "other")
    elif kind == "parent_public":
        path.parent.chmod(0o755)
    else:
        (tmp_path / "link").symlink_to(path.parent, target_is_directory=True)
        path = tmp_path / "link/token"
    with patch("eidolon_core.memory_bridge_client.recall") as remote:
        with pytest.raises(ValueError):
            BridgeMemory(str(path)).recall("question")
        remote.assert_not_called()


def test_descriptor_reader_does_not_reopen_a_checked_path(credential):
    with patch.object(Path, "read_text", side_effect=AssertionError("path reopened")), \
         patch("eidolon_core.memory_bridge_client.recall", return_value={"items": []}) as remote:
        BridgeMemory(str(credential)).recall("question")
        assert remote.call_args.kwargs["token"] == "x" * 64


@pytest.mark.parametrize("change", ["leaf", "parent", "permissions"])
def test_substitution_during_read_refuses_network(credential, change):
    original = os.read
    done = []
    def read(fd, size):
        data = original(fd, size)
        if not done:
            done.append(True)
            if change == "leaf":
                credential.unlink()
                credential.write_text("y" * 64)
                credential.chmod(0o600)
            elif change == "parent":
                credential.parent.rename(credential.parent.with_name("old"))
                credential.parent.mkdir(mode=0o700)
            else:
                credential.chmod(0o644)
        return data
    with patch("os.read", side_effect=read), patch("eidolon_core.memory_bridge_client.recall") as remote:
        with pytest.raises(ValueError):
            BridgeMemory(str(credential)).recall("question")
        remote.assert_not_called()
