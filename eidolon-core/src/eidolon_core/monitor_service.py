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
field follows Codex's published eidolon-machine/1 contract (G161), field by field; the socket's peer
account is checked (SO_PEERCRED) when the configuration names it. Grey is never presented as secure: the adapter keeps visibility/scope/freshness explicit.
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
import struct
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
REMOTE_SECONDS = 10                       # G166: at most one SSH read per remote machine per DARME sample
DEFAULT_TTL = 60
FUTURE_TOLERANCE = 5.0
STATUS = {"UNAUTHORIZED": 401, "READ_TOKEN_NOT_ALLOWED": 403, "HOST_REFUSED": 403, "ORIGIN_REFUSED": 403,
          "NOT_FOUND": 404, "METHOD_NOT_ALLOWED": 405, "INVALID_REQUEST": 400}


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def read_darme(path, *, timeout=SOCKET_TIMEOUT, peer_uid=None):
    """Raw JSON object from one DARME status socket, or a generic error code (never the OS message).

    peer_uid: the socket must be served by this account (SO_PEERCRED, as monitor_tools.read_status)."""
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    deadline = time.monotonic() + timeout
    try:
        connection.connect(path)
        if peer_uid is not None:
            _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != peer_uid:
                return None, "PEER_REFUSED"
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


def _number(value, *, low=0, high=None):
    return (type(value) in (int, float) and math.isfinite(value) and value >= low
            and (high is None or value <= high))


def _bytes(item, fields, *, scope=None):
    """{field: int >= 0} with free/available + used <= total, or None (the whole block, never a half)."""
    if item is None:
        return None
    if (not isinstance(item, dict) or any(type(item.get(f)) is not int or item[f] < 0 for f in fields)
            or item[fields[1]] + item[fields[2]] > item[fields[0]]):
        raise ValueError("invalid byte counters")
    result = {f: item[f] for f in fields}
    if scope is not None:
        if item.get("scope") != scope:
            raise ValueError("unknown disk scope")
        result["scope"] = scope
    return result


def _maybe(value, *, high=None, integer=False):
    if value is None:
        return None
    if integer and type(value) is not int:
        raise ValueError("integer expected")
    if not _number(value, high=high):
        raise ValueError("number expected")
    return value


def gpu_view(raw, *, now):
    """(GPU view, error) for the PROPOSED eidolon-gpu/1 block (docs/GPU-DISPLAY.md, G169).

    The source is named (VM101 today, VM100 with two V100 later): a value never moves from one machine
    to another. Absent values stay null; an invalid block is dropped alone (CPU metrics are kept)."""
    if raw is None:
        return None, None
    try:
        if not isinstance(raw, dict) or raw.get("schema") != "eidolon-gpu/1":
            raise ValueError("schema")
        source = raw["source"]
        if (not isinstance(source, dict) or set(source) != {"id", "label", "collector"}
                or not all(isinstance(source[k], str) and re.fullmatch(r"[A-Za-z0-9 ._-]{1,40}", source[k]) for k in source)):
            raise ValueError("source")
        sampled = datetime.fromisoformat(raw["sampled_at"])
        if sampled.tzinfo is None:
            raise ValueError("naive date")
        age = now - sampled.timestamp()
        if age < -FUTURE_TOLERANCE:
            return None, "GPU_CLOCK_SKEW"
        cadence = raw.get("cadence_seconds")
        if type(cadence) is not int or not 1 <= cadence <= 3600:
            raise ValueError("cadence")
        driver = raw.get("driver")
        if driver is not None and (not isinstance(driver, str) or not re.fullmatch(r"[0-9.]{1,20}", driver)):
            raise ValueError("driver")
        devices = raw.get("devices")
        if not isinstance(devices, list) or len(devices) > 8:
            raise ValueError("devices")
        out = []
        for device in devices:
            if not isinstance(device, dict) or type(device.get("index")) is not int or not 0 <= device["index"] < 16:
                raise ValueError("device index")
            name = device.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9 ._()/-]{1,64}", name):
                raise ValueError("device name")
            used, total = _maybe(device.get("memory_used_bytes"), integer=True), _maybe(device.get("memory_total_bytes"), integer=True)
            if used is not None and total is not None and used > total:
                raise ValueError("memory")
            power, limit = _maybe(device.get("power_w"), high=2000), _maybe(device.get("power_limit_w"), high=2000)
            out.append({"index": device["index"], "name": name,
                        "temperature_c": _maybe(device.get("temperature_c"), high=150),
                        "power_w": power, "power_limit_w": limit,
                        "utilization_percent": _maybe(device.get("utilization_percent"), high=100),
                        "memory_used_bytes": used, "memory_total_bytes": total})
        errors = raw.get("errors", [])
        if (not isinstance(errors, list) or len(errors) > 16
                or not all(isinstance(e, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,39}", e) for e in errors)):
            raise ValueError("errors")
        return {"source": dict(source), "sampled_at": sampled.astimezone(timezone.utc).isoformat(),
                "age_seconds": max(0, round(age)), "stale": age > max(DEFAULT_TTL, 3 * cadence),
                "cadence_seconds": cadence, "driver": driver, "devices": out, "errors": list(errors)}, None
    except (ValueError, KeyError, TypeError):
        return None, "GPU_INVALID"


def machine_view(raw, *, now):
    """(machine view, error) from the eidolon-machine/1 field published by Codex (G161).

    Allow-list of the contract fields only; one invalid block invalidates the view (no half truth)."""
    if raw is None:
        return None, None
    try:
        if not isinstance(raw, dict) or raw.get("schema") != "eidolon-machine/1":
            raise ValueError("schema")
        sampled = datetime.fromisoformat(raw["sampled_at"])
        if sampled.tzinfo is None:
            raise ValueError("naive date")
        age = now - sampled.timestamp()
        if age < -FUTURE_TOLERANCE:
            return None, "MACHINE_CLOCK_SKEW"
        cpu, count, load = raw.get("cpu_percent"), raw.get("cpu_count"), raw.get("load_1_5_15")
        if cpu is not None and not _number(cpu, high=100):
            raise ValueError("cpu")
        if type(count) is not int or not 1 <= count <= 4096:
            raise ValueError("cpu count")
        if load is not None and (not isinstance(load, list) or len(load) != 3 or not all(_number(x) for x in load)):
            raise ValueError("load")
        errors = raw.get("errors", [])
        if (not isinstance(errors, list) or len(errors) > 16
                or not all(isinstance(e, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,39}", e) for e in errors)):
            raise ValueError("errors")
        view = {"sampled_at": sampled.astimezone(timezone.utc).isoformat(), "age_seconds": max(0, round(age)),
                "stale": age > DEFAULT_TTL, "cpu_count": count, "cpu_percent": cpu,
                "load_1_5_15": list(load) if load is not None else None,
                "memory": _bytes(raw.get("memory"), ("total_bytes", "available_bytes", "used_bytes")),
                "swap": _bytes(raw.get("swap"), ("total_bytes", "free_bytes", "used_bytes")),
                "disk": _bytes(raw.get("disk"), ("total_bytes", "free_bytes", "used_bytes"),
                               scope="journal_filesystem"),
                "gpu": None, "errors": list(errors)}
        # G169: a GPU block only if it follows the proposed eidolon-gpu/1 contract; null on CPU VMs (G161).
        view["gpu"], gpu_error = gpu_view(raw.get("gpu"), now=now)
        if gpu_error:
            view["gpu_error"] = gpu_error
        return view, None
    except (ValueError, KeyError, TypeError):
        return None, "MACHINE_INVALID"


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
        "ssh_auth_monitoring": raw.get("ssh_auth_monitoring") is True,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "age_seconds": max(0, round(age)),
        "health_ttl_seconds": ttl,
    }
    machine, machine_error = machine_view(raw.get("machine"), now=now)
    if machine_error:
        darme["machine_error"] = machine_error
    return ("stale" if age > ttl else "ok"), darme, machine, None


class MonitorAPI:
    """Transport-free handler: (method, path, headers) -> (status, JSON value, extra headers)."""

    def __init__(self, credentials, machines, *, not_covered=(), read_token=None, allowed_hosts=None,
                 allowed_origin=None, reader=read_darme, remote_reader=None, clock=time.time,
                 cache_seconds=CACHE_SECONDS):
        self.credentials, self.machines, self.not_covered = credentials, list(machines), list(not_covered)
        self.read_authorization = ("Bearer " + read_token).encode("ascii") if read_token else None
        self.allowed_hosts, self.allowed_origin = allowed_hosts, allowed_origin
        self.reader, self.clock, self.cache_seconds = reader, clock, cache_seconds
        if remote_reader is None:
            from .monitor_remote import read_ssh as remote_reader
        self.remote_reader = remote_reader
        self._remote = {}                    # machine id -> (monotonic time, raw, error): one SSH read per 10 s
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
                raw, error = self._read(machine)
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

    def _read(self, machine):
        if "ssh" not in machine:
            return self.reader(machine["socket"], peer_uid=machine.get("peer_uid"))
        at, raw, error = self._remote.get(machine["id"], (-math.inf, None, None))
        if time.monotonic() - at >= REMOTE_SECONDS:
            raw, error = self.remote_reader(machine["ssh"])
            self._remote[machine["id"]] = (time.monotonic(), raw, error)
        return raw, error

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
        if (isinstance(machine, dict) and "ssh" in machine and "socket" not in machine
                and set(machine) <= {"id", "label", "ssh"}):
            # G166: remote DARME through the forced-command feed (monitor_remote.py, docs/MEMORY-CHANNEL.md).
            from .monitor_remote import validate
            machine["ssh"] = validate(machine["ssh"])
            if (not isinstance(machine["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", machine["id"])
                    or machine["id"] in seen or not isinstance(machine["label"], str)
                    or not re.fullmatch(r"[^\x00-\x1f<>]{1,40}", machine["label"])):
                raise ValueError("MONITOR_CONFIG_INVALID: machine id, label")
            seen.add(machine["id"])
            continue
        if (not isinstance(machine, dict) or not {"id", "label", "socket"} <= set(machine)
                or not set(machine) <= {"id", "label", "socket", "peer_user"}
                or not isinstance(machine["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", machine["id"])
                or machine["id"] in seen
                or not isinstance(machine["label"], str) or not re.fullmatch(r"[^\x00-\x1f<>]{1,40}", machine["label"])
                or not isinstance(machine["socket"], str) or not machine["socket"].startswith("/")
                or len(machine["socket"]) > 100 or ".." in machine["socket"]):
            raise ValueError("MONITOR_CONFIG_INVALID: machine id, label, absolute socket")
        seen.add(machine["id"])
        if "peer_user" in machine:
            if not isinstance(machine["peer_user"], str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", machine["peer_user"]):
                raise ValueError("MONITOR_CONFIG_INVALID: peer_user")
            import pwd
            try:
                machine["peer_uid"] = pwd.getpwnam(machine.pop("peer_user")).pw_uid
            except KeyError:
                raise ValueError("MONITOR_CONFIG_INVALID: unknown peer_user") from None
    not_covered = value.get("not_covered", [])
    if (not isinstance(not_covered, list) or len(not_covered) > 8
            or not all(isinstance(x, str) and re.fullmatch(r"[^\x00-\x1f<>]{1,60}", x) for x in not_covered)):
        raise ValueError("MONITOR_CONFIG_INVALID: not_covered")
    origin = value.get("allowed_origin")
    if origin is not None and not re.fullmatch(r"http://(127\.0\.0\.1|localhost):[0-9]{1,5}", origin):
        raise ValueError("MONITOR_CONFIG_INVALID: allowed_origin must be the local Core page")
    return value


def main(argv=None):
    from .comm_credentials import ReadOnlyClientCredentials, ReadOnlyCredentialStore
    from .http_api import read_token
    from .presentation import message
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
        api = MonitorAPI(ReadOnlyClientCredentials(ReadOnlyCredentialStore(args.state)), config["machines"],
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
            from .sd_notify import notify
            notify()                                # G167: Type=notify, ready only once the port is open
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
