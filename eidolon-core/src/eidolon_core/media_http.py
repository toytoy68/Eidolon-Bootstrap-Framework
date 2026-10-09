# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_http.py
# Description : HTTP média local avec échéance murale sur envoi et réception
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""One local HTTP exchange, no proxy, redirect, retry, thread or detached request.

A single monotonic deadline covers connection, request send, status, headers,
chunk framing and response body. Every socket read resets its timeout to the
remaining budget; trickled bytes cannot extend it. The caller still treats a
timeout after POST as an unknown engine effect, never as permission to resubmit.
Only literal loopback addresses, plain HTTP. This does not cancel a remote job.
"""
from functools import partial
from http.client import HTTPConnection, HTTPException
import io
import math
import time
from urllib.parse import urlsplit

from .media_agents import MediaError
from .model_http import _CompleteHeaderResponse, IncompleteHeaders, read_body

DEFAULT_SECONDS = 90.0


class _DeadlineExpired(TimeoutError):
    pass


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise _DeadlineExpired()
    return value


class _DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline):
        super().__init__()
        self.sock, self.deadline = sock, deadline
        # SocketIO keeps the descriptor alive until the response has closed.
        self.raw = sock.makefile("rb", buffering=0)

    def readable(self):
        return True

    def readinto(self, target):
        self.sock.settimeout(_remaining(self.deadline))
        return self.raw.readinto(target)

    def close(self):
        if not self.closed:
            self.raw.close()
        super().close()


class _Response(_CompleteHeaderResponse):
    def __init__(self, sock, *, deadline, **kwargs):
        super().__init__(sock, **kwargs)
        self.fp.close()  # no bytes have been read by HTTPResponse.__init__
        self.fp = io.BufferedReader(_DeadlineReader(sock, deadline))


class _Connection(HTTPConnection):
    def __init__(self, host, port, *, deadline):
        self.deadline = deadline
        super().__init__(host, port, timeout=_remaining(deadline))
        self.response_class = partial(_Response, deadline=deadline)

    def send(self, data):
        if self.sock is None:
            self.timeout = _remaining(self.deadline)
            self.connect()
        self.sock.settimeout(_remaining(self.deadline))
        # HTTPConnection uses sendall for our bytes-only bodies; its socket
        # timeout bounds the whole sendall, rather than each partial write.
        return super().send(data)


def exchange(method, url, body, headers, max_response, *, timeout=DEFAULT_SECONDS,
             status_error="INVALID_BACKEND_RESPONSE"):
    """Return content type + bounded body; Content-Length/chunk framing remains strict."""
    from .media_backends import endpoint
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise MediaError("INVALID_MEDIA_HTTP_TIMEOUT")
    if method not in {"GET", "POST"} or body is not None and type(body) is not bytes:
        raise MediaError("INVALID_MEDIA_HTTP_REQUEST")
    if type(max_response) is not int or not 0 < max_response <= 256 * 1024 * 1024:
        raise MediaError("INVALID_MEDIA_HTTP_LIMIT")
    try:
        parts = urlsplit(url)
        endpoint(parts.scheme + "://" + parts.netloc)
        if parts.fragment or any(ord(c) < 33 or ord(c) == 127 for c in url):
            raise MediaError("INVALID_ENDPOINT")
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
    except (ValueError, TypeError):
        raise MediaError("INVALID_ENDPOINT") from None
    deadline = time.monotonic() + timeout
    connection = _Connection(parts.hostname, parts.port, deadline=deadline)
    try:
        connection.request(method, path, body=body, headers=headers)
        with connection.getresponse() as response:
            if response.status != 200:
                raise MediaError(status_error)
            content_type = response.headers.get_content_type()
            result = read_body(response, max_response, MediaError)
            _remaining(deadline)
            return content_type, result
    except IncompleteHeaders:
        raise MediaError("INCOMPLETE_HTTP") from None
    except TimeoutError:
        raise MediaError("MEDIA_HTTP_DEADLINE") from None
    except (OSError, HTTPException):
        raise MediaError("MEDIA_HTTP_UNAVAILABLE") from None
    finally:
        connection.close()
