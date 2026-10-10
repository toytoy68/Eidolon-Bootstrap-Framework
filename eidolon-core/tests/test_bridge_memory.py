"""BridgeMemory contract: compatible with Dialogue and fails closed on credentials."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.memory import BridgeMemory
from eidolon_core.contracts import validate_context


class BridgeMemoryTests(unittest.TestCase):
    def test_preserves_context_for_dialogue(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "token"
            path.write_text("x" * 64)
            path.chmod(0o600)
            result = {"items": [{"information_id": "note", "revision": 1,
                                  "content": "Untrusted memory", "needs_review": True,
                                  "truncated": False, "excerpt_reference": None,
                                  "epistemic_status": "UNVERIFIED",
                                  "operational_state": None, "confidence": None,
                                  "provenance": {}, "verification": {}, "temporal": {}}]}
            with patch("eidolon_core.memory_bridge_client.recall", return_value=result) as client:
                actual = BridgeMemory(str(path)).recall("test")
                self.assertEqual(validate_context(actual), result)
                client.assert_called_once()

    def test_refuses_world_readable_token_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "token"
            path.write_text("x" * 64)
            path.chmod(0o644)
            with patch("eidolon_core.memory_bridge_client.recall") as client:
                with self.assertRaises(ValueError):
                    BridgeMemory(str(path)).recall("test")
                client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
