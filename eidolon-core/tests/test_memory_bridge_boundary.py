"""BridgeMemory integration boundary tests: no network, no real memory."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eidolon_core.memory import BridgeMemory
from eidolon_core.contracts import ContractError


class BridgeMemoryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = Path(self.tmp.name) / "bridge-token"
        self.token.write_text("t" * 40, encoding="ascii")
        self.token.chmod(0o600)
        self.bridge = BridgeMemory(str(self.token))

    def test_valid_empty_context_passes_without_network(self):
        with patch("eidolon_core.memory_bridge_client.recall", return_value={"items": []}) as remote:
            result = self.bridge.recall("Quelle est la décision ?")
        self.assertEqual(result["items"], [])
        remote.assert_called_once()

    def test_malformed_context_rejected_before_dialogue(self):
        with patch("eidolon_core.memory_bridge_client.recall", return_value={"items": [{"content": "no identity"}]}):
            with self.assertRaises(ContractError):
                self.bridge.recall("question")

    def test_rejects_public_token_permissions(self):
        self.token.chmod(0o644)
        with patch("eidolon_core.memory_bridge_client.recall") as remote:
            with self.assertRaises(ValueError):
                self.bridge.recall("question")
            remote.assert_not_called()

    def test_rejects_token_symlink(self):
        link = Path(self.tmp.name) / "linked-token"
        link.symlink_to(self.token)
        with patch("eidolon_core.memory_bridge_client.recall") as remote:
            with self.assertRaises(ValueError):
                BridgeMemory(str(link)).recall("question")
            remote.assert_not_called()
