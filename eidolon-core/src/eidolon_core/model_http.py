# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : model_http.py
# Description : Lecture bornée et cadrage HTTP des réponses de planificateur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Shared response framing policy for the two optional stdlib transports.

No redirects/retries/requests here. Supports a single Content-Length, a single
chunked Transfer-Encoding, or connection-close framing. Byte bounds are not a
wall-clock deadline; the runtime's worker budget provides the outer call limit.
"""
from http.client import HTTPConnection, HTTPException, HTTPResponse
from urllib.request import HTTPHandler


class IncompleteHeaders(HTTPException):
    """EOF after response bytes, before the header block's terminating line."""


class _HeaderLines:
    def __init__(self, stream):
        self.stream = stream
        self.seen = False

    def close(self):
        self.stream.close()

    def readline(self, limit=-1):
        line = self.stream.readline(limit)
        if not line and self.seen:
            raise IncompleteHeaders("response ended inside HTTP headers")
        # A full bounded read is left to http.client's existing line-size check.
        if line and not line.endswith(b"\n") and (limit < 0 or len(line) < limit):
            raise IncompleteHeaders("response ended inside HTTP headers")
        self.seen = self.seen or bool(line)
        return line


class _CompleteHeaderResponse(HTTPResponse):
    def begin(self):
        if self.headers is not None:
            return
        stream = self.fp
        self.fp = _HeaderLines(stream)
        try:
            # Keep stdlib status parsing, interim responses and header bounds.
            # Only header EOF detection differs; body reads use the original fp.
            super().begin()
        finally:
            if self.fp is not None:  # A bad status line may already have closed it.
                self.fp = stream


class _CompleteHeaderConnection(HTTPConnection):
    response_class = _CompleteHeaderResponse


class CompleteHeaderHandler(HTTPHandler):
    """Per-opener HTTP handler; no monkey-patching or process-global state."""
    def http_open(self, request):
        return self.do_open(_CompleteHeaderConnection, request)


def read_body(stream, max_bytes, error_type):
    headers = stream.headers
    lengths = headers.get_all("Content-Length", []) if headers is not None else []
    encodings = headers.get_all("Transfer-Encoding", []) if headers is not None else []
    if len(lengths) > 1 or len(encodings) > 1 or lengths and encodings:
        raise error_type("BAD_HTTP_FRAMING", "ambiguous response framing")
    if encodings and encodings[0].strip().lower() != "chunked":
        raise error_type("BAD_HTTP_FRAMING", "unsupported transfer encoding")
    expected = None
    if lengths:
        length = lengths[0].strip()
        if not length or not length.isascii() or not length.isdigit():
            raise error_type("BAD_HTTP_FRAMING", "invalid content length")
        # Bound decimal conversion too; large positive lengths exceed our budget.
        if len(length) > 20 or int(length) > max_bytes:
            raise error_type("RESPONSE_TOO_LARGE", "declared response exceeds configured budget")
        expected = int(length)
    body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise error_type("RESPONSE_TOO_LARGE", f"more than {max_bytes} bytes")
    if expected is not None and len(body) != expected:
        raise error_type("INCOMPLETE_HTTP", "response ended before its declared content length")
    return body
