# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : worker.py
# Description : Appels bornés dans des processus distincts
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Bounded trusted Python calls in spawned processes; not a security sandbox."""
import json
import multiprocessing
import time

from .contracts import MAX_JSON_BYTES, encode


class CallFailure(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _child(sender, function, args):
    try:
        try:
            response = {"ok": True, "value": function(*args)}
            encoded = encode(response).encode("utf-8")
            if len(encoded) > MAX_JSON_BYTES:
                raise ValueError("worker response exceeds 1 MB")
        except Exception as exc:
            encoded = encode({"ok": False, "error": type(exc).__name__,
                              "message": str(exc)[:1000]}).encode("utf-8")
        sender.send_bytes(encoded)
    finally:
        sender.close()


def invoke(function, args, *, timeout, cancelled):
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(sender, function, args), daemon=True)
    deadline = time.monotonic() + timeout
    started = False
    try:
        if cancelled():
            raise CallFailure("CANCELLED", "cancellation requested before worker launch")
        try:
            process.start()
        except Exception as exc:
            raise CallFailure("WORKER_START_FAILED", "worker could not start: " + type(exc).__name__) from exc
        started = True
        sender.close()
        response = None
        while True:
            if cancelled():
                raise CallFailure("CANCELLED", "cancellation requested")
            if time.monotonic() >= deadline:
                raise CallFailure("TIMEOUT", "call deadline exceeded")
            if response is None and receiver.poll(0.01):
                try:
                    response = json.loads(receiver.recv_bytes(MAX_JSON_BYTES))
                except (EOFError, OSError, ValueError) as exc:
                    raise CallFailure("WORKER_LOST", "worker returned no valid receipt") from exc
            if not process.is_alive():
                if response is None:
                    raise CallFailure("WORKER_LOST", "worker exited without receipt")
                if process.exitcode != 0 or not response["ok"]:
                    raise CallFailure("CALL_ERROR", response.get("message", "worker failed"))
                return response["value"]
            if response is not None:
                process.join(0.01)
    finally:
        sender.close()
        receiver.close()
        if started:
            if process.is_alive():
                process.terminate()
                process.join(0.2)
            if process.is_alive():
                process.kill()
            process.join()
            process.close()
