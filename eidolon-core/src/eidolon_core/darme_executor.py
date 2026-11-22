# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_executor.py
# Description : Opt-in separate-principal executor for text.stats
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Linux Unix-socket boundary for one pure capability, with mutual peer checks.

The trusted operator supplies socket path and both numeric UIDs. The service
directory and code must be unwritable by Core. This is not an executor for
arbitrary commands or external effects. Runtime retains its existing journal
and uncertainty handling; this transport never retries a request.
"""
import argparse
from dataclasses import dataclass
import json
import os
import socket
import stat
import struct
import time
import uuid

from .contracts import ContractError
from .sandbox_tools import execute, validate, MAX_TEXT_BYTES
from .tools import Registry, Tool, verify_stats

MAX_FRAME = 524288


def peer_uid(sock):
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET,
                         socket.SO_PEERCRED, struct.calcsize("3i")))[1]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def receive(sock, *, timeout=7):
    deadline = time.monotonic() + timeout
    def exact(size):
        chunks = bytearray()
        while len(chunks) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("frame deadline")
            sock.settimeout(remaining)
            data = sock.recv(size - len(chunks))
            if not data:
                raise ValueError("incomplete frame")
            chunks.extend(data)
        return chunks
    size = struct.unpack("!I", exact(4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("frame budget")
    value = json.loads(exact(size), object_pairs_hook=_unique)
    if type(value) is not dict:
        raise ValueError("object required")
    return value


def send(sock, value):
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False).encode()
    if len(raw) > MAX_FRAME:
        raise ValueError("frame budget")
    sock.sendall(struct.pack("!I", len(raw)) + raw)


def dispatch(request):
    if (set(request) != {"version", "id", "tool", "text"}
            or type(request["version"]) is not int or request["version"] != 1
            or request["tool"] != "text.stats"
            or type(request["id"]) is not str
            or len(request["id"]) != 32
            or any(c not in "0123456789abcdef" for c in request["id"])
            or type(request["text"]) is not str
            or len(request["text"].encode("utf-8")) > MAX_TEXT_BYTES):
        raise ValueError("independent policy refused")
    # Reuse the independently validated fixed bubblewrap worker. No callbacks,
    # reference paths, programs, URLs or claimed UIDs cross this boundary.
    from .contracts import reference
    item = {"information_id": "service-input", "revision": 1,
            "content": request["text"]}
    parameters = {"reference": reference(item)}
    result = execute(parameters, {"items": [item]})
    return {"version": 1, "id": request["id"], "result": result}


def handle(sock, allowed_uid):
    sock.settimeout(7)
    if peer_uid(sock) != allowed_uid:
        return
    try:
        send(sock, dispatch(receive(sock)))
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, ContractError):
        # No raw request or exception text: inputs may contain private content.
        try:
            send(sock, {"error": "refused"})
        except OSError:
            pass


def serve(path, allowed_uid):
    if type(allowed_uid) is not int or allowed_uid < 0 or allowed_uid == os.getuid():
        raise ValueError("a separate Core UID is required")
    parent = os.path.dirname(path)
    info = os.lstat(parent)
    if (not os.path.isabs(path) or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o022):
        raise ValueError("service-owned non-writable socket directory required")
    # Never remove a pre-existing path. The service manager owns stale socket
    # cleanup, after stopping the previous instance.
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(path)
        try:
            os.chmod(path, 0o660)
            listener.listen(8)
            while True:
                connection, _ = listener.accept()
                with connection:
                    handle(connection, allowed_uid)
        finally:
            os.unlink(path)


@dataclass(frozen=True)
class RemoteExecutor:
    path: str
    service_uid: int

    def __call__(self, parameters, context):
        text = validate(parameters, context)["content"]
        request_id = uuid.uuid4().hex
        try:
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(8)
                sock.connect(self.path)
                if peer_uid(sock) != self.service_uid:
                    raise RuntimeError("unexpected executor principal")
                send(sock, {"version": 1, "id": request_id,
                            "tool": "text.stats", "text": text})
                response = receive(sock)
            if (set(response) != {"version", "id", "result"}
                    or type(response["version"]) is not int or response["version"] != 1
                    or response["id"] != request_id
                    or not verify_stats(parameters, context, response["result"])):
                raise ValueError("executor evidence mismatch")
            return response["result"]
        except (OSError, ValueError, KeyError) as exc:
            raise RuntimeError("executor unavailable or invalid; no local fallback") from exc


def remote_registry(path, service_uid):
    if type(service_uid) is not int or service_uid < 0 or service_uid == os.getuid():
        raise ValueError("a separate service UID is required")
    return Registry([Tool("text.stats", "darme-socket-1", "none", validate,
                         RemoteExecutor(path, service_uid), verify_stats,
                         "text-stats-recompute/1")])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--core-uid", type=int, required=True)
    args = parser.parse_args()
    serve(args.socket, args.core_uid)
