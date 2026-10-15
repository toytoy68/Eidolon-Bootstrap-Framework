# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : memory_bridge_client.py
# Description : Client du bridge memoire via tunnel local
# ==========================================================
"""Explicit opt-in client for Memory Bridge. Connect to loopback SSH forward only."""
import json
import http.client


class MemoryBridgeError(Exception):
    pass


def recall(query, *, token, port=18765, timeout=10, max_items=5,
           max_chars=4000, max_item_chars=800, expected_profile=None):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid local port")
    if type(token) is not str or len(token) < 32 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("invalid token")
    if type(query) is not str or not 1 <= len(query) <= 500 or any(ord(c) < 32 or ord(c) == 127 for c in query):
        raise ValueError("invalid query")
    if type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ValueError("invalid timeout")
    for value, upper in ((max_items, 5), (max_chars, 4000), (max_item_chars, 800)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError("invalid recall limit")
    payload = {"query": query, "mode": "operational", "max_items": max_items,
               "max_chars": max_chars, "max_item_chars": max_item_chars}
    return request("/v1/recall", payload, token=token, port=port, timeout=timeout,
                   schema="eidolon-memory-recall/1", expected_profile=expected_profile)


def request(path, payload, *, token, port, timeout=10, schema, expected_profile=None):
    """Pinned loopback, no environment proxy or redirect; bounded response."""
    if (path not in ("/v1/recall", "/v1/remember") or type(port) is not int or not 1024 <= port <= 65535
            or type(token) is not str or not 32 <= len(token) <= 4096
            or any(ord(c) < 33 or ord(c) > 126 for c in token)
            or type(timeout) not in (int, float) or not 0 < timeout <= 30):
        raise ValueError("invalid bridge request")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("POST", path, body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            raise MemoryBridgeError("bridge refused or unavailable")
        raw = response.read(131073)
        if len(raw) > 131072:
            raise MemoryBridgeError("response too large")
        result = json.loads(raw)
        if (type(result) is not dict or result.get("schema") != schema
                or type(result.get("result")) is not dict
                or expected_profile is not None and result.get("profile_id") != expected_profile):
            raise MemoryBridgeError("bridge response identity mismatch")
        return result["result"]
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise MemoryBridgeError("memory bridge unavailable or invalid response") from exc
    finally:
        conn.close()
