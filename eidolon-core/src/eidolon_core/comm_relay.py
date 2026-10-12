# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_relay.py
# Description : Relais de même origine /v1/comm/* vers le service local eidolon-comm (CSP connect-src 'self' conservée)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Same-origin relay for the communication service (C147).

The page served by Core may only connect to its own origin (CSP connect-src 'self'); the voice/vision
service runs in its OWN process on 127.0.0.1:<comm port>. With http_api --comm-port, Core forwards
/v1/comm/* there, unchanged: method, path, body (bounded) and the Authorization header. Core adds and
reads nothing else: the communication service checks the paired key and refuses the read token itself.
Nothing is logged or kept; an absent service answers COMM_UNAVAILABLE.
"""
import http.client
import json
import socket

PREFIX = "/v1/comm/"
MAX_BODY = 2 * 1024 * 1024 + 64 * 1024        # = comm_service.MAX_BODY
MAX_RESPONSE = 4 * 1024 * 1024
METHODS = ("GET", "POST", "DELETE")
TIMEOUT = 90.0


def error(code):
    return {"protocol": "eidolon-comm/1", "error": code, "authorizes_execution": False}


def relay(port, method, path, authorization, content_type, body, *, timeout=TIMEOUT):
    """(status, JSON value) from the local communication service, or a Core-side refusal."""
    if not path.startswith(PREFIX) or ".." in path or "\\" in path:
        return 404, error("NOT_FOUND")
    if method not in METHODS:
        return 405, error("METHOD_NOT_ALLOWED")
    headers = {"Host": f"127.0.0.1:{port}", "Content-Length": str(len(body))}
    if authorization is not None:
        headers["Authorization"] = authorization
    if content_type is not None:
        headers["Content-Type"] = content_type
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(method, path, body=body if method == "POST" else None, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        status = response.status
    except (ConnectionError, socket.timeout, OSError, http.client.HTTPException):
        return 503, error("COMM_UNAVAILABLE")
    finally:
        connection.close()
    if len(raw) > MAX_RESPONSE:
        return 502, error("COMM_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, UnicodeError):
        return 502, error("COMM_RESPONSE_INVALID")
    if not isinstance(value, dict):
        return 502, error("COMM_RESPONSE_INVALID")
    return status, value
