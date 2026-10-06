# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : http_api.py
# Description : Consultation HTTP locale authentifiée, sans exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Development reader for a same-origin client over an SSH tunnel.

No Runtime, commands, model, migration, or remote bind. The bearer grants read
access only; it is not a human identity. See docs/HTTP-READ-API.md.
"""
import argparse
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

from .client_sync import ClientSync, SyncError
from .contracts import ContractError
from .mission_list import MissionList
from .presentation import header, message
from .store import Store

PROTOCOL = "eidolon-http-read/1"
MAX_REQUEST = 8192
MAX_RESPONSE = 262144
MAX_ASSET = 524288
TOKEN_PATTERN = r"[A-Za-z0-9_-]{32,128}"
MISSION_PATH = re.compile(r"/v1/missions/(m-[0-9a-f]{32})(/poll)?")
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class APIError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def read_token(path):
    """Open one private regular file, without following a final symlink."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise ValueError("TOKEN_FILE_NOT_PRIVATE")
        raw = handle.read(130)
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    token = raw.decode("ascii")
    if not re.fullmatch(TOKEN_PATTERN, token):
        raise ValueError("INVALID_TOKEN")
    return token


class ReadOnlyStore:
    """Use existing protocols with SQLite mode=ro, never Store.__init__."""
    check_id = staticmethod(Store.check_id)

    def __init__(self, directory):
        self.directory = Path(directory).resolve(strict=True)
        self.path = self.directory / "missions.sqlite3"
        if not self.path.is_file():
            raise ValueError("STATE_NOT_FOUND")
        with self.connection():
            pass

    @contextmanager
    def connection(self):
        if any((self.directory / name).exists() for name in
               ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3")):
            raise ContractError("RECOVERY_REVIEW_ONLY")
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ContractError("UNSUPPORTED_READ_SCHEMA")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"missions", "events", "sync_metadata", "command_receipts"} <= tables:
                raise ContractError("UNSUPPORTED_READ_SCHEMA")
            if db.execute("SELECT 1 FROM sync_metadata WHERE key='recovery_mode'").fetchone():
                raise ContractError("RECOVERY_REVIEW_ONLY")
            row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
            if not row or type(row[0]) is not str or not re.fullmatch(r"s-[0-9a-f]{32}", row[0]):
                raise ContractError("INVALID_STORE_ID")
            yield db
        finally:
            db.close()

    def health(self):
        with self.connection() as db:
            identity = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()[0]
        return {"protocol": PROTOCOL, "mode": "read_only", "store_id": identity,
                "authorizes_execution": False}


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
        pending = [(result, 0)]
        while pending:
            value, depth = pending.pop()
            if depth > 16:
                raise ValueError("nesting limit")
            if type(value) is dict:
                pending.extend((child, depth + 1) for child in value.values())
            elif type(value) is list:
                pending.extend((child, depth + 1) for child in value)
        # Also reject escaped isolated surrogates and huge/non-finite floats.
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if type(result) is not dict:
            raise ValueError("object required")
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise APIError(400, "INVALID_JSON") from exc


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "EidolonReadAPI"
    sys_version = ""

    def setup(self):
        self.request.settimeout(3)
        super().setup()

    def log_message(self, *_):
        pass  # Request paths, tokens and exception text never go to access logs.

    def send_error(self, code, message=None, explain=None):
        self._error(405 if code == 501 else code,
                    "METHOD_NOT_ALLOWED" if code == 501 else "HTTP_REQUEST_REJECTED")

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                         "style-src 'self'; connect-src 'self'; img-src 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_RESPONSE:
            raise APIError(503, "RESPONSE_TOO_LARGE")
        self._send(status, body)

    def _error(self, status, code):
        self._json(status, {"protocol": PROTOCOL, "error": code, "authorizes_execution": False})

    def _one(self, name):
        values = self.headers.get_all(name, [])
        if len(values) > 1:
            raise APIError(400, "DUPLICATE_HEADER")
        return values[0] if values else None

    def _request(self):
        if sum(len(k) + len(v) for k, v in self.headers.items()) > 16384:
            raise APIError(431, "HEADERS_TOO_LARGE")
        host = self._one("Host")
        if host not in self.server.allowed_hosts:
            raise APIError(403, "HOST_REFUSED")
        origin = self._one("Origin")
        if origin is not None and origin != "http://" + host:
            raise APIError(403, "ORIGIN_REFUSED")
        if self.headers.get_all("Transfer-Encoding") or self.headers.get_all("Expect"):
            raise APIError(400, "UNSUPPORTED_TRANSFER")
        length = self._one("Content-Length")
        if length is not None and not re.fullmatch(r"[0-9]{1,9}", length):
            raise APIError(400, "INVALID_CONTENT_LENGTH")
        size = int(length) if length is not None else 0
        if size > MAX_REQUEST:
            raise APIError(413, "REQUEST_TOO_LARGE")
        asset = ASSETS.get(self.path)
        if not (asset and self.command == "GET"):
            values = self.headers.get_all("Authorization", [])
            if (len(values) != 1 or not hmac.compare_digest(
                    values[0].encode("utf-8"), self.server.authorization)):
                raise APIError(401, "UNAUTHORIZED")
        if self.command not in {"GET", "POST"}:
            raise APIError(405, "METHOD_NOT_ALLOWED")
        if self.command == "GET":
            if size:
                raise APIError(400, "UNEXPECTED_BODY")
            if asset:
                body = self.server.assets.get(self.path)
                if body is None:
                    raise APIError(404, "NOT_FOUND")
                self._send(200, body, asset[1])
                return
            if self.path == "/v1/health":
                self._json(200, self.server.store.health())
                return
        match = MISSION_PATH.fullmatch(self.path)
        if self.command == "GET" and match and not match[2]:
            # Distinguish missing identity from malformed data inside a mission.
            self._exists(match[1])
            self._json(200, ClientSync(self.server.store).snapshot(match[1]))
            return
        if self.command != "POST" or not (self.path == "/v1/missions" or match and match[2]):
            raise APIError(404, "NOT_FOUND")
        content_type = self._one("Content-Type")
        if content_type is None or content_type.lower() not in {
                "application/json", "application/json; charset=utf-8"}:
            raise APIError(415, "JSON_REQUIRED")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise APIError(400, "INCOMPLETE_BODY")
        data = _decode(raw)
        if set(data) - {"cursor", "limit"}:
            raise APIError(400, "UNKNOWN_FIELD")
        if self.path == "/v1/missions":
            response = MissionList(self.server.store).page(**data)
        else:
            if "cursor" not in data:
                raise APIError(400, "CURSOR_REQUIRED")
            self._exists(match[1])
            response = ClientSync(self.server.store).poll(match[1], **data)
        self._json(200, response)

    def _exists(self, identity):
        with self.server.store.connection() as db:
            if not db.execute("SELECT 1 FROM missions WHERE id=?", (identity,)).fetchone():
                raise APIError(404, "MISSION_NOT_FOUND")

    def _dispatch(self):
        try:
            self._request()
        except APIError as exc:
            self._error(exc.status, exc.code)
        except SyncError as exc:
            bad_request = {"INVALID_CURSOR", "CURSOR_MISSION_MISMATCH",
                           "INVALID_PAGE_LIMIT", "INVALID_LIST_CURSOR"}
            self._error(400 if exc.code in bad_request else 503,
                        exc.code if exc.code in bad_request else "STATE_UNAVAILABLE")
        except (sqlite3.Error, ContractError, ValueError, TypeError, KeyError,
                IndexError, RecursionError, UnicodeError):
            self._error(503, "STATE_UNAVAILABLE")
        except TimeoutError:
            self._error(408, "REQUEST_TIMEOUT")
        except OSError:
            self.close_connection = True

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _dispatch


class ReadServer(HTTPServer):
    """Single-request server, deliberately local; no unbounded worker pool."""
    def __init__(self, state, token, *, port=8765, web_root=None):
        if type(token) is not str or not re.fullmatch(TOKEN_PATTERN, token):
            raise ValueError("INVALID_TOKEN")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("INVALID_PORT")
        self.authorization = ("Bearer " + token).encode("ascii")
        self.store = ReadOnlyStore(state)
        self.assets = {}
        if web_root is not None:
            root = Path(web_root).resolve(strict=True)
            for url, (name, _) in ASSETS.items():
                path = root / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError("INVALID_WEB_ROOT")
                with path.open("rb") as handle:
                    body = handle.read(MAX_ASSET + 1)
                if len(body) > MAX_ASSET:
                    raise ValueError("ASSET_TOO_LARGE")
                self.assets[url] = body
        super().__init__(("127.0.0.1", port), _Handler)
        self.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}

    def handle_error(self, request, client_address):
        pass  # No request/exception dump; public server monitoring is out of scope.


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — consultation HTTP locale")
    parser.add_argument("--state", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--web-root")
    args = parser.parse_args(argv)
    try:
        token = read_token(args.token_file)
        with ReadServer(args.state, token, port=args.port, web_root=args.web_root) as server:
            print(header(title="API de consultation locale"), flush=True)
            print(message("INFO", f"Écoute sur http://127.0.0.1:{server.server_port} — lecture seule."), flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, sqlite3.Error, ContractError):
        print(message("ERREUR", "API_STARTUP_REFUSED : vérifier état existant, token privé et port."), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
