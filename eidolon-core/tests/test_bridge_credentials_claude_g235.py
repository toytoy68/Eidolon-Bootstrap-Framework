# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_bridge_credentials_claude_g235.py
# Description : Contre-vérification Claude de A08 (G235) : propriétaire, bornes, liens d'ancêtres
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Cases not pinned by test_bridge_credentials_g235.py. The owner case kills a mutant (owner check removed) that
survives GPT's suite. No network: the transport is replaced and must never be reached on refusal."""
import os
from unittest.mock import patch

import pytest

from eidolon_core.bridge_credentials import MAX_TOKEN_BYTES, read_bridge_token
from eidolon_core.memory import BridgeMemory

OTHER_UID = 54321


@pytest.fixture
def credential(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    path = parent / "token"
    path.write_text("t" * 64 + "\n")
    path.chmod(0o600)
    return path


def _refused_without_network(path):
    with patch("eidolon_core.memory_bridge_client.recall") as transport:
        with pytest.raises(ValueError) as caught:
            BridgeMemory(str(path)).recall("question")
        transport.assert_not_called()
    assert str(path) not in str(caught.value) and "t" * 32 not in str(caught.value)


@pytest.mark.skipif(os.geteuid() != 0, reason="changing a file owner needs root")
def test_a_token_owned_by_another_user_is_refused(credential):
    os.chown(credential, OTHER_UID, -1)
    _refused_without_network(credential)


@pytest.mark.skipif(os.geteuid() != 0, reason="changing a directory owner needs root")
def test_a_parent_owned_by_another_user_is_refused(credential):
    os.chown(credential.parent, OTHER_UID, -1)
    _refused_without_network(credential)


def test_size_boundaries(credential):
    credential.write_text("a" * MAX_TOKEN_BYTES)
    assert read_bridge_token(str(credential)) == "a" * MAX_TOKEN_BYTES
    credential.write_text("a" * (MAX_TOKEN_BYTES + 1))
    _refused_without_network(credential)
    credential.write_text("a" * 31)
    _refused_without_network(credential)


def test_a_link_anywhere_above_the_secret_is_refused(credential, tmp_path):
    """Pinned strictness: every ancestor is opened with O_NOFOLLOW, so a symlinked home directory is refused
    (operational note: the credential must live under a link-free path)."""
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    _refused_without_network(alias / "private" / "token")


def test_a_symlinked_leaf_is_refused(credential, tmp_path):
    other = credential.parent / "other"
    other.write_text("u" * 64)
    other.chmod(0o600)
    link = credential.parent / "link"
    link.symlink_to(other)
    _refused_without_network(link)
