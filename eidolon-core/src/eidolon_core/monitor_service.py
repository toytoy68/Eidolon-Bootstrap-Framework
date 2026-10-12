# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : monitor_service.py
# Description : Adaptateur local eidolon-monitor : lecture seule du statut DARME pour le dashboard, clé appairée (G157)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""eidolon-monitor: a SEPARATE loopback adapter between the dashboard and the private DARME socket(s).

One route, GET /v1/monitor/status (Authorization: Bearer <paired conversation key>; the read token and
revoked clients are refused). Core relays it on the page origin with http_api --monitor-port.

The adapter only ever sends the fixed bytes STATUS\\n to each configured socket: nothing provided by the
browser reaches DARME. Replies are bounded (size, delay), re-validated field by field and reduced to an
allow-list; raw events, subjects, paths, process contents and tokens are never relayed. The `machine`
field announced by Codex (G154) is passed only as flat numbers/short labels until its contract is
published. Grey is never presented as secure: the adapter keeps visibility/scope/freshness explicit.
"""
import argparse
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import socket
import stat
import sys
import threading
import time
import urllib.parse

PREFIX = "/v1/monitor/"
PROTOCOL = "eidolon-monitor/1"
CONFIG_SCHEMA = "eidolon-monitor-config/1"
DARME_SCHEMA = "eidolon-darme-service/1"
BADGES = ("gold", "grey", "red", "blue")
MAX_REPLY = 64 * 1024
SOCKET_TIMEOUT = 3.0
CACHE_SECONDS = 2.0                       # several tabs never multiply reads of the single-threaded DARME
POLL_SECONDS = 10                         # = DARME sampling interval
DEFAULT_TTL = 60
FUTURE_TOLERANCE = 5.0
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
STATUS = {"UNAUTHORIZED": 401, "READ_TOKEN_NOT_ALLOWED": 403, "HOST_REFUSED": 403, "ORIGIN_REFUSED": 403,
          "NOT_FOUND": 404, "METHOD_NOT_ALLOWED": 405, "INVALID_REQUEST": 400}


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def read_darme(path, *, timeout=SOCKET_TIMEOUT):
    """Raw JSON object from one DARME status socket, or a generic error code (never the OS message)."""
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    deadline = time.monotonic() + timeout
    try:
        connection.connect(path)
        connection.sendall(b"STATUS\n")
        raw = b""
        while not raw.endswith(b"\n"):
            if time.monotonic() > deadline:
                return None, "TIMEOUT"
            chunk = connection.recv(16384)
            if not chunk:
                break
            raw += chunk
            if len(raw) > MAX_REPLY:
                return None, "REPLY_TOO_LARGE"
    except PermissionError:
        return None, "PERMISSION_DENIED"
    except socket.timeout:
        return None, "TIMEOUT"
    except OSError:
        return None, "UNAVAILABLE"
    finally:
        connection.close()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        return None, "INVALID_REPLY"
    return (value, None) if isinstance(value, dict) else (None, "INVALID_REPLY")


def _count(value):
    return value if type(value) is int and 0 <= value < 10**9 else None


def _flat(value):
    """Provisional `machine` field: flat {key: finite number | null | short label}, at most 32 keys."""
    if not isinstance(value, dict) or len(value) > 32:
        return None
    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not KEY.fullmatch(key):
            return None
        if item is None or type(item) is bool:
            result[key] = item
        elif type(item) in (int, float) and math.isfinite(item):
            result[key] = item
        elif isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9 ._%/-]{0,32}", item):
            result[key] = item
        elif isinstance(item, dict):
            inner = _flat(item)
            if inner is None or any(isinstance(v, dict) for v in inner.values()):
                return None                              # one nesting level (e.g. per-disk), no more
            result[key] = inner
        else:
            return None
    return result


def summarize(raw, *, now=None):
    """(state, darme summary or None, machine or None, error or None) from a DARME status object."""
    now = time.time() if now is None else now
    if raw.get("service_schema") != DARME_SCHEMA or raw.get("authorizes_execution") is not False:
        return "invalid", None, None, "INVALID_REPLY"
    badge, visibility = raw.get("badge"), raw.get("visibility")
    sources = raw.get("sources")
    if (badge not in BADGES or visibility not in ("complete", "partial") or not isinstance(sources, dict)
            or len(sources) > 64 or not all(isinstance(k, str) and re.fullmatch(r"[A-Za-z0-9@._-]{1,80}", k)
                                            and type(v) is bool for k, v in sources.items())):
        return "invalid", None, None, "INVALID_REPLY"
    try:
        generated = datetime.fromisoformat(raw.get("generated_at"))
    except (TypeError, ValueError):
        return "invalid", None, None, "INVALID_REPLY"
    if generated.tzinfo is None:
        return "invalid", None, None, "INVALID_REPLY"
    ttl = raw.get("health_ttl_seconds")
    ttl = ttl if type(ttl) is int and 1 <= ttl <= 3600 else DEFAULT_TTL
    age = now - generated.timestamp()
    if age < -FUTURE_TOLERANCE:
        return "invalid", None, None, "CLOCK_SKEW"
    scope = raw.get("scope")
    darme = {
        "badge": badge,
        # Grey/partial is NEVER "secure"; gold only means every declared source answered in time.
        "secure_claim": False,
        "visibility": visibility,
        "sources": dict(sorted(sources.items())),
        "scope": scope if isinstance(scope, str) and re.fullmatch(r"[a-z0-9_]{1,80}", scope) else None,
        "security_telemetry_installed": raw.get("security_telemetry_installed") is True,
        "unacknowledged_alerts": _count(raw.get("unacknowledged_alerts")),
        "intervention": raw.get("intervention") is True,
        "ingestion_paused": raw.get("ingestion_paused") is True,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "age_seconds": max(0, round(age)),
        "health_ttl_seconds": ttl,
    }
    machine = _flat(raw["machine"]) if "machine" in raw else None
    return ("stale" if age > ttl else "ok"), darme, machine, None


class MonitorAPI:
    """Transport-free handler: (method, path, headers) -> (status, JSON value, extra headers)."""

    def __init__(self, credentials, machines, *, not_covered=(), read_token=None, allowed_hosts=None,
                 allowed_origin=None, reader=read_darme, clock=time.time, cache_seconds=CACHE_SECONDS):
        self.credentials, self.machines, self.not_covered = credentials, list(machines), list(not_covered)
        self.read_authorization = ("Bearer " + read_token).encode("ascii") if read_token else None
        self.allowed_hosts, self.allowed_origin = allowed_hosts, allowed_origin
        self.reader, self.clock, self.cache_seconds = reader, clock, cache_seconds
        self._lock = threading.Lock()
        self._cache = (None, -math.inf)

    def _one(self, headers, name):
        values = [v for k, vs in headers.items() if k.lower() == name.lower() for v in vs]
        if len(values) > 1:
            raise Refused("INVALID_REQUEST")
        return values[0] if values else None

    def _client(self, headers):
        auth = self._one(headers, "Authorization")
        if auth is None or not auth.startswith("Bearer "):
            raise Refused("UNAUTHORIZED")
        if self.read_authorization is not None and hmac.compare_digest(auth.encode("utf-8", "replace"),
                                                                       self.read_authorization):
            raise Refused("READ_TOKEN_NOT_ALLOWED")
        if self.credentials.authenticate(auth[len("Bearer "):]) is None:    # unknown or revoked
            raise Refused("UNAUTHORIZED")

    def status(self):
        with self._lock:                     # one reader at a time, shared short cache
            value, at = self._cache
            if value is not None and time.monotonic() - at < self.cache_seconds:
                return value
            now = self.clock()
            machines = []
            for machine in self.machines:
                entry = {"id": machine["id"], "label": machine["label"]}
                raw, error = self.reader(machine["socket"])
                if raw is None:
                    state = "invalid" if error in ("INVALID_REPLY", "REPLY_TOO_LARGE") else "unavailable"
                    entry.update(state=state, error=error, darme=None, machine=None)
                else:
                    state, darme, metrics, error = summarize(raw, now=now)
                    entry.update(state=state, darme=darme, machine=metrics)
                    if error:
                        entry["error"] = error
                machines.append(entry)
            value = {"protocol": PROTOCOL, "generated_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                     "poll_seconds": POLL_SECONDS, "machines": machines, "not_covered": self.not_covered,
                     "gpu_metrics": None, "authorizes_execution": False}
            self._cache = (value, time.monotonic())
            return value

    def handle(self, method, path, headers):
        extra = {}
        try:
            if self.allowed_hosts is not None and self._one(headers, "Host") not in self.allowed_hosts:
                raise Refused("HOST_REFUSED")
            origin = self._one(headers, "Origin")
            if origin is not None:
                if origin != self.allowed_origin:
                    raise Refused("ORIGIN_REFUSED")
                extra = {"Access-Control-Allow-Origin": origin, "Vary": "Origin",
                         "Access-Control-Allow-Headers": "Authorization", "Access-Control-Allow-Methods": "GET"}
            if method == "OPTIONS":
                return 204, None, extra
            url = urllib.parse.urlsplit(path)
            if url.path != PREFIX + "status":
                raise Refused("NOT_FOUND")
            if method != "GET":
                raise Refused("METHOD_NOT_ALLOWED")
            if url.query:
                raise Refused("INVALID_REQUEST")             # no parameter is accepted from the browser
            self._client(headers)
            return 200, self.status(), extra
        except Refused as exc:
            return STATUS[exc.code], {"protocol": PROTOCOL, "error": exc.code, "authorizes_execution": False}, extra


class _Handler(BaseHTTPRequestHandler):
    server_version = "eidolon-monitor"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _serve(self, method):
        self.connection.settimeout(10)
        length = self.headers.get("Content-Length")
        if self.headers.get("Transfer-Encoding") or (length not in (None, "0")):
            status, value, extra = 400, {"protocol": PROTOCOL, "error": "INVALID_REQUEST",
                                         "authorizes_execution": False}, {}
            self.close_connection = True
        else:
            headers = {}
            for name, item in self.headers.items():
                headers.setdefault(name, []).append(item)
            status, value, extra = self.server.api.handle(method, self.path, headers)
        raw = b"" if value is None else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, item in {**extra, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}.items():
            self.send_header(name, item)
        if value is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")

    def do_PUT(self):
        self._serve("PUT")

    def do_DELETE(self):
        self._serve("DELETE")

    def do_OPTIONS(self):
        self._serve("OPTIONS")


class MonitorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, api, *, port=8768):
        super().__init__(("127.0.0.1", port), _Handler)
        self.api = api
        if api.allowed_hosts is None:
            api.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}


def load_config(path):
    """Private operator file (0600, owner, no symlink): which DARME sockets to read, and what is not covered."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("MONITOR_CONFIG_NOT_PRIVATE")
        value = json.loads(handle.read(64 * 1024).decode("utf-8"))
    if (not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA
            or not set(value) <= {"schema", "machines", "not_covered", "allowed_origin"}):
        raise ValueError("MONITOR_CONFIG_INVALID")
    machines = value.get("machines")
    if not isinstance(machines, list) or not 1 <= len(machines) <= 8:
        raise ValueError("MONITOR_CONFIG_INVALID: 1 to 8 machines")
    seen = set()
    for machine in machines:
        if (not isinstance(machine, dict) or set(machine) != {"id", "label", "socket"}
                or not isinstance(machine["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", machine["id"])
                or machine["id"] in seen
                or not isinstance(machine["label"], str) or not re.fullmatch(r"[^\x00-\x1f<>]{1,40}", machine["label"])
                or not isinstance(machine["socket"], str) or not machine["socket"].startswith("/")
                or len(machine["socket"]) > 100 or ".." in machine["socket"]):
            raise ValueError("MONITOR_CONFIG_INVALID: machine id, label, absolute socket")
        seen.add(machine["id"])
    not_covered = value.get("not_covered", [])
    if (not isinstance(not_covered, list) or len(not_covered) > 8
            or not all(isinstance(x, str) and re.fullmatch(r"[^\x00-\x1f<>]{1,60}", x) for x in not_covered)):
        raise ValueError("MONITOR_CONFIG_INVALID: not_covered")
    origin = value.get("allowed_origin")
    if origin is not None and not re.fullmatch(r"http://(127\.0\.0\.1|localhost):[0-9]{1,5}", origin):
        raise ValueError("MONITOR_CONFIG_INVALID: allowed_origin must be the local Core page")
    return value


def main(argv=None):
    from .client_credentials import ClientCredentials
    from .http_api import read_token
    from .presentation import message
    from .store import Store
    parser = argparse.ArgumentParser(prog="python -m eidolon_core.monitor_service",
                                     description="Eidolon — adaptateur local de surveillance (statut DARME, lecture seule)")
    parser.add_argument("--state", required=True, help="état Core (clés appairées de la conversation, lecture)")
    parser.add_argument("--config", required=True, help="fichier privé eidolon-monitor-config/1 (0600)")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--read-token-file", help="jeton de lecture de Core, refusé ici comme sur la conversation")
    parser.add_argument("--check", action="store_true", help="lire une fois chaque socket configuré, sans ouvrir de port")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        api = MonitorAPI(ClientCredentials(Store(args.state)), config["machines"],
                         not_covered=config.get("not_covered", []),
                         read_token=read_token(args.read_token_file) if args.read_token_file else None,
                         allowed_origin=config.get("allowed_origin"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc).split(":")[0][:60] or type(exc).__name__
        print(message("ERREUR", f"MONITOR_STARTUP_REFUSED : {code}"), file=sys.stderr)
        return 2
    if args.check:
        status = api.status()
        print(json.dumps({m["id"]: m["state"] if "error" not in m else f'{m["state"]} {m["error"]}'
                          for m in status["machines"]}, ensure_ascii=False))
        return 0
    with MonitorServer(api, port=args.port) as server:
        print(message("INFO", f"eidolon-monitor sur http://127.0.0.1:{server.server_port} — "
                              f"{len(api.machines)} machine(s), lecture seule."), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
