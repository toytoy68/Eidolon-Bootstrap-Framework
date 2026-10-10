import unittest
from unittest.mock import patch
from eidolon_core.memory_bridge_client import recall, MemoryBridgeError


class MemoryBridgeClientTests(unittest.TestCase):
    def test_invalid_configuration(self):
        for kwargs in ({"port": 80}, {"token": "short"}, {"max_items": 10}, {"timeout": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                recall("hello", **{**{"token": "x" * 40}, **kwargs})

    def test_no_network_for_invalid_query(self):
        with patch("eidolon_core.memory_bridge_client.urlopen") as request:
            with self.assertRaises(ValueError):
                recall("", token="x" * 40)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
