# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : memory_bridge_client.py
# Description : Client du bridge memoire via tunnel local
# ==========================================================
"""Explicit opt-in client for Memory Bridge. Connect to loopback SSH forward only."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MemoryBridgeError(Exception):
    pass


def recall(query, *, token, port=18765, timeout=10, max_items=5,
           max_chars=4000, max_item_chars=800):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid local port")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("invalid token")
    if not isinstance(query, str) or not 1 <= len(query) <= 500:
        raise ValueError("invalid query")
    if type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ValueError("invalid timeout")
    for value, upper in ((max_items, 5), (max_chars, 4000), (max_item_chars, 800)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError("invalid recall limit")
    payload = json.dumps({
        "query": query, "mode": "operational", "max_items": max_items,
        "max_chars": max_chars, "max_item_chars": max_item_chars
    }).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}/v1/recall", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise MemoryBridgeError("unexpected response")
            if response.headers.get("Content-Length") and int(response.headers["Content-Length"]) > 131072:
                raise MemoryBridgeError("response too large")
            raw = response.read(131073)
            if len(raw) > 131072:
                raise MemoryBridgeError("response too large")
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("schema") != "eidolon-memory-recall/1":
                raise MemoryBridgeError("invalid response schema")
            return result["result"]
    except (HTTPError, URLError, ValueError, KeyError) as exc:
        raise MemoryBridgeError("memory bridge unavailable or invalid response") from exc
