# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_darme_executor.py
# Description : Independent policy and authenticated transport failures
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
import socket
import struct
import threading
import time

import pytest
from eidolon_core import darme_executor as ex
from eidolon_core.memory import DEMO_REQUEST, SyntheticMemory
from eidolon_core.contracts import reference
from eidolon_core.tools import text_stats


def request(**changes):
    return {"version": 1, "id": "a" * 32, "tool": "text.stats", "text": "été", **changes}


@pytest.mark.parametrize("changes", [
    {"tool": "shell"}, {"uid": 0}, {"version": True}, {"id": "../state"},
    {"text": ["x"]}, {"text": "é" * 32769}, {"text": "\ud800"},
])
def test_service_revalidates_before_worker(monkeypatch, changes):
    monkeypatch.setattr(ex, "execute", lambda *a: pytest.fail("worker must not run"))
    with pytest.raises((ValueError, UnicodeError)):
        ex.dispatch(request(**changes))


def test_fixed_worker_receives_only_text(monkeypatch):
    monkeypatch.setattr(ex, "execute", text_stats)
    reply = ex.dispatch(request())
    assert reply["id"] == "a" * 32
    assert reply["result"]["characters"] == 3
    assert reply["result"]["utf8_bytes"] == 5


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'[]', b'{'])
def test_strict_frames(raw):
    a, b = socket.socketpair()
    with a, b:
        a.sendall(struct.pack("!I", len(raw)) + raw)
        with pytest.raises(ValueError): ex.receive(b)


def test_budget_rejected_before_reading_body():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(struct.pack("!I", ex.MAX_FRAME + 1))
        with pytest.raises(ValueError, match="budget"): ex.receive(b)


def test_partial_frames_do_not_extend_total_deadline():
    a, b = socket.socketpair()
    def trickle():
        try:
            for byte in struct.pack("!I", 2) + b'{}':
                a.sendall(bytes([byte])); time.sleep(0.04)
        except OSError:
            pass
    with a, b:
        thread = threading.Thread(target=trickle); thread.start()
        started = time.monotonic()
        try:
            with pytest.raises(TimeoutError): ex.receive(b, timeout=0.07)
            assert time.monotonic() - started < 0.2
        finally:
            b.close(); thread.join(timeout=1)
        assert not thread.is_alive()


def test_wrong_peer_is_rejected_before_read(monkeypatch):
    a, b = socket.socketpair()
    with a, b:
        monkeypatch.setattr(ex, "receive", lambda _: pytest.fail("must not read"))
        ex.handle(b, os.getuid() + 10000)


def test_same_uid_is_not_independent(tmp_path):
    with pytest.raises(ValueError): ex.remote_registry(str(tmp_path / "s"), os.getuid())
    with pytest.raises(ValueError): ex.serve(str(tmp_path / "s"), os.getuid())


@pytest.mark.parametrize("mode", ["wrong_uid", "wrong_id", "wrong_result", "version_bool", "refused", "closed"])
def test_client_fails_closed(tmp_path, monkeypatch, mode):
    path = str(tmp_path / "socket")
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(path); listener.listen(1)
    trusted_uid = os.getuid() + 1
    monkeypatch.setattr(ex, "peer_uid", lambda _: trusted_uid if mode != "wrong_uid" else trusted_uid + 1)
    context = SyntheticMemory().recall(DEMO_REQUEST)
    parameters = {"reference": reference(context["items"][0])}
    errors = []
    def server():
        try:
            with listener:
                conn, _ = listener.accept()
                with conn:
                    if mode in ("wrong_uid", "closed"): return
                    req = ex.receive(conn)
                    reply = {"version": 1, "id": req["id"], "result": text_stats(parameters, context)}
                    if mode == "wrong_id": reply["id"] = "b" * 32
                    if mode == "wrong_result": reply["result"]["characters"] = -1
                    if mode == "version_bool": reply["version"] = True
                    if mode == "refused": reply = {"error": "refused"}
                    ex.send(conn, reply)
        except BaseException as err: errors.append(err)
    thread = threading.Thread(target=server); thread.start()
    try:
        with pytest.raises(RuntimeError):
            ex.remote_registry(path, trusted_uid).get("text.stats").execute(parameters, context)
    finally: thread.join(timeout=10)
    assert not thread.is_alive() and not errors


def test_missing_service_has_no_fallback(tmp_path):
    context = SyntheticMemory().recall(DEMO_REQUEST)
    with pytest.raises(RuntimeError, match="no local fallback"):
        ex.remote_registry(str(tmp_path / "missing"), os.getuid() + 1).get("text.stats").execute(
            {"reference": reference(context["items"][0])}, context)
