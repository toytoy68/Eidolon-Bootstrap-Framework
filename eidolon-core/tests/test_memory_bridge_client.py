import unittest
from unittest.mock import patch
from eidolon_core.memory_bridge_client import recall, MemoryBridgeError


class MemoryBridgeClientTests(unittest.TestCase):
    def test_invalid_configuration(self):
        for kwargs in ({"port": 80}, {"token": "short"}, {"max_items": 10}, {"timeout": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                recall("hello", **{**{"token": "x" * 40}, **kwargs})

    def test_no_network_for_invalid_query(self):
        with patch("eidolon_core.memory_bridge_client.http.client.HTTPConnection") as request:
            with self.assertRaises(ValueError):
                recall("", token="x" * 40)
            request.assert_not_called()

    def test_rejects_control_characters_before_network(self):
        with patch("eidolon_core.memory_bridge_client.http.client.HTTPConnection") as request:
            for query in ("hello" + chr(10) + "world", "hello" + chr(127)):
                with self.subTest(query=query), self.assertRaises(ValueError):
                    recall(query, token="x" * 40)
            request.assert_not_called()

    def test_rejects_invalid_bridge_payload(self):
        import io
        import json
        class Response:
            status = 200
            headers = {}
            def __init__(self, data):
                self.data = io.BytesIO(json.dumps(data).encode())
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, n):
                return self.data.read(n)
        with patch("eidolon_core.memory_bridge_client.http.client.HTTPConnection") as connection:
            connection.return_value.getresponse.return_value = Response(
                {"schema": "eidolon-memory-recall/1", "result": None})
            with self.assertRaises(MemoryBridgeError):
                recall("hello", token="x" * 40)
            connection.assert_called_once_with("127.0.0.1", 18765, timeout=10)
            connection.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
