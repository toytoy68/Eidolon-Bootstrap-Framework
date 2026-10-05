# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : worker.py
# Description : Appels bornés, reçus atomiques et verrous des exécutants
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Trusted spawned calls, not a sandbox; a local lease does not prove no effect."""
from contextlib import nullcontext
from datetime import datetime, timezone
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time

from .contracts import MAX_JSON_BYTES, encode


class CallFailure(RuntimeError):
    def __init__(self, code, message, *, receipt=None, authorized=None):
        super().__init__(message)
        self.code = code
        self.receipt = receipt  # Unverified envelope retained for review, never success.
        self.authorized = authorized


def attempt_receipt_path(lease_path):
    return Path(lease_path).with_suffix(".receipt.json")


def _error(code, exc):
    message = str(exc)[:1000].encode("utf-8", errors="backslashreplace").decode("utf-8")
    return {"ok": False, "code": code, "error": type(exc).__name__, "message": message}


def _child(channel, function, args, receipt_path, lease_path):
    try:
        with (open(lease_path, "a") if lease_path else nullcontext()) as lease:
            if lease is not None:
                fcntl.flock(lease, fcntl.LOCK_EX)
            try:
                channel.send_bytes(b"ready")
                # EOF/reset before permission cannot execute the provider.
                permission = channel.recv_bytes(16)
            except (EOFError, OSError):
                return
            if permission != b"execute":
                return
            if lease is not None:
                # Keep the same inode locked. Mark authorization before entering
                # provider code; an interrupted write is conservatively unknown.
                lease.write("authorized\n")
                lease.flush()
                os.fsync(lease.fileno())
            try:
                value = function(*args)
            except Exception as exc:
                response = _error("CALL_ERROR", exc)
            else:
                response = {"ok": True, "value": value}
            try:
                encoded = encode(response).encode("utf-8")
                if len(encoded) > MAX_JSON_BYTES:
                    raise ValueError("worker response exceeds 1 MB")
            except Exception as exc:
                encoded = encode(_error("INVALID_RESPONSE", exc)).encode("utf-8")
            # A complete bounded receipt is either present or absent. Unlike a
            # large pipe message it cannot leave recv_bytes blocked on a partial
            # write when the child is terminated at the deadline.
            pending = Path(receipt_path).with_suffix(".pending")
            with pending.open("wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, receipt_path)
    finally:
        channel.close()


def _read_receipt(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
    except FileNotFoundError:
        return None
    if len(raw) > MAX_JSON_BYTES:
        raise CallFailure("WORKER_LOST", "invalid receipt size")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get("ok")) is not bool:
            raise ValueError("invalid envelope")
        if value["ok"] and "value" not in value:
            raise ValueError("missing output")
        return value
    except (ValueError, RecursionError) as exc:
        raise CallFailure("WORKER_LOST", "worker returned no valid receipt") from exc


def invoke(function, args, *, timeout, cancelled, lease_path=None, on_started=None):
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe(duplex=True)
    with tempfile.TemporaryDirectory(prefix="eidolon-worker-") as directory:
        # Tool receipts belong to the attempt, not to the parent's lifetime.
        receipt_path = (attempt_receipt_path(lease_path) if lease_path
                        else Path(directory) / "receipt.json")
        process = ctx.Process(target=_child, args=(child, function, args, str(receipt_path),
                                                   str(lease_path) if lease_path else None), daemon=True)
        deadline = time.monotonic() + timeout
        started = False
        failure = None
        authorized = False
        try:
            if cancelled():
                raise CallFailure("CANCELLED", "cancellation requested before worker launch", authorized=False)
            try:
                process.start()
            except Exception as exc:
                raise CallFailure("WORKER_START_FAILED", "worker could not start: " + type(exc).__name__, authorized=False) from exc
            started = True
            child.close()
            while True:
                if cancelled():
                    failure = ("CANCELLED", "cancellation requested")
                    break
                if time.monotonic() >= deadline:
                    failure = ("TIMEOUT", "call deadline exceeded")
                    break
                if not authorized and parent.poll(0.01):
                    try:
                        ready = parent.recv_bytes(16)
                    except (EOFError, OSError) as exc:
                        raise CallFailure("WORKER_LOST", "worker exited before launch handshake", authorized=False) from exc
                    if ready != b"ready":
                        raise CallFailure("WORKER_LOST", "invalid worker handshake", authorized=False)
                    if on_started:
                        on_started({"pid": process.pid,
                                    "started_at": datetime.now(timezone.utc).isoformat(),
                                    "protocol": "lease-v2"})
                    # Persisted launch precedes permission; recheck cancellation.
                    if cancelled() or time.monotonic() >= deadline:
                        continue
                    # A failed/partial send is ambiguous, not proof of no permission.
                    authorized = True
                    parent.send_bytes(b"execute")
                process.join(0.01)
                if not process.is_alive():
                    # Recheck cancellation/deadline on the following iteration.
                    if cancelled():
                        failure = ("CANCELLED", "cancellation requested")
                    elif time.monotonic() >= deadline:
                        failure = ("TIMEOUT", "call deadline exceeded")
                    break
        finally:
            child.close()
            parent.close()
            if started:
                if process.is_alive():
                    process.terminate()
                    process.join(0.2)
                if process.is_alive():
                    process.kill()
                process.join()
                exitcode = process.exitcode
                process.close()
        # Read AFTER stop/join even on timeout or cancellation. Completed output
        # remains evidence for review; it does not override cancellation/deadline.
        response = _read_receipt(receipt_path)
        if failure:
            raise CallFailure(*failure, receipt=response, authorized=authorized)
        if response is None:
            raise CallFailure("WORKER_LOST", "worker exited without receipt", authorized=authorized)
        if exitcode != 0 or not response["ok"]:
            raise CallFailure(response.get("code", "CALL_ERROR"),
                              response.get("message", "worker failed"), receipt=response, authorized=authorized)
        return response["value"]
