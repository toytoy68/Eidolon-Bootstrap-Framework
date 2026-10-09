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
import io
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import sys
import threading
import time

from .client_sync import ClientSync, SyncError
from .archive_page import ArchivePages, ArchivePageError
from .contracts import ContractError
from .mission_list import MissionList
from .presentation import header, message
from .receipt_lookup import ReceiptLookupError, lookup as lookup_receipt
from .research_archive import ArchiveError, read_catalog
from .store import Store

PROTOCOL = "eidolon-http-read/1"
MAX_REQUEST = 8192
MAX_RESPONSE = 262144
MAX_ASSET = 524288
MAX_CONNECTIONS = 4
IDLE_TIMEOUT_SECONDS = 3.0
READ_DEADLINE_SECONDS = 5.0
SQL_BUDGET_SECONDS = 2.0
BUSY_WRITE_TIMEOUT_SECONDS = 0.05
TOKEN_PATTERN = r"[A-Za-z0-9_-]{32,128}"
MISSION_PATH = re.compile(r"/v1/missions/(m-[0-9a-f]{32})(/poll)?")
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/eidolon-logo.png": ("eidolon-logo.png", "image/png")}
# Served when present; an older or minimal web root without it stays valid (404, client keeps its text name).
OPTIONAL_ASSETS = frozenset({"/eidolon-logo.png"})
SECURITY_HEADERS = (("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"),
                    ("Referrer-Policy", "no-referrer"),
                    ("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                     "style-src 'self'; connect-src 'self'; img-src 'self'; "
                     "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"))


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
        self.query_budget_seconds = SQL_BUDGET_SECONDS
        self.directory = Path(directory).resolve(strict=True)
        self.path = self.directory / "missions.sqlite3"
        if not self.path.is_file():
            raise ValueError("STATE_NOT_FOUND")
        with self.connection():
            pass

    @contextmanager
    def connection(self):
        from .readonly_sqlite import require_rollback_journal
        if (self.directory / "BETA-PREPARATION-INCOMPLETE").exists():
            raise ContractError("BETA_PREPARATION_INCOMPLETE")
        if any((self.directory / name).exists() for name in
               ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3")):
            raise ContractError("RECOVERY_REVIEW_ONLY")
        require_rollback_journal(self.path)
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            # Cooperative SQLite VM deadline, shared across this read connection.
            # This does not interrupt filesystem I/O or Python projection work.
            deadline = time.monotonic() + self.query_budget_seconds
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ContractError("UNSUPPORTED_READ_SCHEMA")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"missions", "events", "sync_metadata", "command_receipts"} <= tables:
                raise ContractError("UNSUPPORTED_READ_SCHEMA")
            if db.execute("SELECT 1 FROM sync_metadata WHERE key='recovery_mode'").fetchone():
                raise ContractError("RECOVERY_REVIEW_ONLY")
            row = db.execute("SELECT substr(value,1,35) FROM sync_metadata WHERE key='store_id'").fetchone()
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


class _DeadlineReader(io.RawIOBase):
    """Bound the entire socket read phase, including trickled header/body bytes."""
    def __init__(self, connection, deadline, idle_timeout):
        self.connection = connection
        self.deadline = deadline
        self.idle_timeout = idle_timeout

    def readable(self):
        return True

    def readinto(self, buffer):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("read deadline")
        self.connection.settimeout(min(self.idle_timeout, remaining))
        return self.connection.recv_into(buffer)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "EidolonReadAPI"
    sys_version = ""

    def setup(self):
        self.read_deadline = time.monotonic() + self.server.read_deadline_seconds
        self.request.settimeout(self.server.idle_timeout_seconds)
        super().setup()
        self.rfile.close()
        self.rfile = io.BufferedReader(_DeadlineReader(
            self.request, self.read_deadline, self.server.idle_timeout_seconds))

    def log_message(self, *_):
        pass  # Request paths, tokens and exception text never go to access logs.

    def send_error(self, code, message=None, explain=None):
        self._error(405 if code == 501 else code,
                    "METHOD_NOT_ALLOWED" if code == 501 else "HTTP_REQUEST_REJECTED")

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        # Reading may have consumed its deadline; writes get a separate bounded
        # socket timeout, including the final sanitized timeout response.
        self.request.settimeout(self.server.idle_timeout_seconds)
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
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
        if time.monotonic() >= self.read_deadline:
            raise APIError(408, "REQUEST_TIMEOUT")
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
        if self.command != "POST" or not (self.path in {"/v1/missions", "/v1/command-receipt", "/v1/research-archives"}
                                          or match and match[2]):
            raise APIError(404, "NOT_FOUND")
        content_type = self._one("Content-Type")
        if content_type is None or content_type.lower() not in {
                "application/json", "application/json; charset=utf-8"}:
            raise APIError(415, "JSON_REQUIRED")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise APIError(400, "INCOMPLETE_BODY")
        data = _decode(raw)
        if self.path == "/v1/command-receipt":
            self._json(200, lookup_receipt(self.server.store, data))
            return
        if set(data) - {"cursor", "limit"}:
            raise APIError(400, "UNKNOWN_FIELD")
        if self.path == "/v1/research-archives":
            if self.server.archive_pages is None:
                raise APIError(404, "ARCHIVES_NOT_CONFIGURED")
            self._json(200, self.server.archive_pages.page(**data))
            return
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
        except ReceiptLookupError as exc:
            self._error(exc.status, exc.code)
        except ArchivePageError as exc:
            self._error(exc.status, exc.code)
        except ArchiveError:
            self._error(503, "ARCHIVES_UNAVAILABLE")
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


def read_assets(web_root):
    """Load the same bounded, fixed asset set for startup and diagnostics."""
    assets = {}
    if web_root is not None:
        root = Path(web_root).resolve(strict=True)
        for url, (name, _) in ASSETS.items():
            path = root / name
            if url in OPTIONAL_ASSETS and not os.path.lexists(path):
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError("INVALID_WEB_ROOT")
            with path.open("rb") as handle:
                body = handle.read(MAX_ASSET + 1)
            if len(body) > MAX_ASSET:
                raise ValueError("ASSET_TOO_LARGE")
            assets[url] = body
    return assets


class ReadServer(HTTPServer):
    """Local server with four slots, no unbounded thread/connection queue."""
    def __init__(self, state, token, *, port=8765, web_root=None, research_archives=None):
        if type(token) is not str or not re.fullmatch(TOKEN_PATTERN, token):
            raise ValueError("INVALID_TOKEN")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("INVALID_PORT")
        self.authorization = ("Bearer " + token).encode("ascii")
        self.store = ReadOnlyStore(state)
        self.assets = read_assets(web_root)
        self.archive_pages = None
        if research_archives is not None:
            read_catalog(research_archives, time_budget_seconds=2.0)
            self.archive_pages = ArchivePages(self.store, research_archives)
        self.idle_timeout_seconds = IDLE_TIMEOUT_SECONDS
        self.read_deadline_seconds = READ_DEADLINE_SECONDS
        self._worker_lock = threading.Lock()
        self._workers = {}
        self._closing = False
        super().__init__(("127.0.0.1", port), _Handler)
        self.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}

    def process_request(self, request, client_address):
        with self._worker_lock:
            if not self._closing and len(self._workers) < MAX_CONNECTIONS:
                worker = threading.Thread(target=self._serve_connection,
                                          args=(request, client_address), name="eidolon-read-connection")
                self._workers[request] = worker
                try:
                    worker.start()
                except BaseException:
                    self._workers.pop(request, None)
                    self.shutdown_request(request)
                    raise
                return
        # Fixed pre-authentication response: no request, token or Store data.
        # One tiny bounded write, no parser, worker or waiting queue. It reports
        # unavailable capacity, never a result or permission to resend a command.
        body = b'{"protocol":"eidolon-http-read/1","error":"BUSY","authorizes_execution":false}'
        response = (b"HTTP/1.0 503 Service Unavailable\r\n"
                    b"Content-Type: application/json; charset=utf-8\r\n"
                    + b"".join((name + ": " + value + "\r\n").encode("ascii") for name, value in SECURITY_HEADERS)
                    + b"Connection: close\r\nContent-Length: " + str(len(body)).encode("ascii")
                    + b"\r\n\r\n" + body)
        try:
            request.settimeout(BUSY_WRITE_TIMEOUT_SECONDS)
            request.sendall(response)
        except OSError:
            pass  # Peer gone/unwritable: no delivery guarantee under overload.
        finally:
            self.shutdown_request(request)

    def _serve_connection(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            try:
                self.shutdown_request(request)
            finally:
                with self._worker_lock:
                    self._workers.pop(request, None)

    def server_close(self):
        with self._worker_lock:
            self._closing = True
            active = list(self._workers.items())
        super().server_close()
        for connection, _ in active:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for _, worker in active:
            if worker is not threading.current_thread():
                worker.join()

    def handle_error(self, request, client_address):
        pass  # No request/exception dump; public server monitoring is out of scope.


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — consultation HTTP locale")
    parser.add_argument("--state", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--web-root")
    parser.add_argument("--research-archives", help="Catalogue privé existant à consulter, sans export des contenus")
    parser.add_argument("--check", action="store_true", help="Diagnostic local, sans ouvrir de port")
    parser.add_argument("--format", choices=("json", "human"), help="Format du diagnostic --check")
    args = parser.parse_args(argv)
    if args.format and not args.check:
        parser.error("--format exige --check")
    if args.check:
        from .preflight import inspect, render
        report = inspect(args.state, args.token_file, port=args.port, web_root=args.web_root,
                         research_archives=args.research_archives)
        print(render(report, args.format or "json"))
        return 0 if report["status"] == "PASS" else 2
    try:
        token = read_token(args.token_file)
        with ReadServer(args.state, token, port=args.port, web_root=args.web_root,
                        research_archives=args.research_archives) as server:
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
