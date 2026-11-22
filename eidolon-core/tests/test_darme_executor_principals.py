# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_darme_executor_principals.py
# Description : Opt-in real separate-UID execution and crash recovery
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
from pathlib import Path
import socket
import pytest
from eidolon_core import darme_executor as ex
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.worker import attempt_receipt_path

pytestmark = pytest.mark.skipif(os.environ.get("EIDOLON_PRINCIPAL_INTEGRATION") != "1",
                               reason="explicit separate Linux service UID")


def registry():
    return ex.remote_registry(os.environ["EIDOLON_EXECUTOR_SOCKET"],
                              int(os.environ["EIDOLON_EXECUTOR_UID"]))


def test_runtime_receipt_and_restart(tmp_path):
    store = Store(tmp_path / "core")
    runtime = Runtime(store, registry=registry())
    mission = runtime.run(runtime.create(DEMO_REQUEST)["id"])
    assert mission["status"] == "SUCCEEDED", mission.get("error")
    call = mission["calls"][0]
    assert call["status"] == "VERIFIED"
    path = attempt_receipt_path(store.worker_lease_path(mission["id"], call["id"], call["attempt"]))
    assert json.loads(path.read_text()) == {"ok": True, "value": call["output"]}
    assert Runtime(store, registry=registry()).run(mission["id"])["calls"] == mission["calls"]


def test_interrupted_call_remains_uncertain(tmp_path):
    class Stop(BaseException): pass
    def checkpoint(phase):
        if phase == "TOOL_RETURNED": raise Stop()
    store = Store(tmp_path / "core")
    runtime = Runtime(store, registry=registry(), checkpoint=checkpoint)
    identity = runtime.create(DEMO_REQUEST)["id"]
    with pytest.raises(Stop): runtime.run(identity)
    call = store.get(identity)["calls"][0]
    path = attempt_receipt_path(store.worker_lease_path(identity, call["id"], call["attempt"]))
    before = path.read_bytes()
    resumed = Runtime(store, registry=registry()).run(identity)
    assert resumed["status"] == "REVIEW_REQUIRED"
    assert resumed["error"]["code"] == "UNKNOWN_EFFECT"
    assert resumed["calls"][0]["attempt"] == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("extra", [{"tool": "shell"}, {"uid": 0}, {"text": "é" * 32769}])
def test_service_refuses_bypassed_client_policy(extra):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(8); sock.connect(os.environ["EIDOLON_EXECUTOR_SOCKET"])
        assert ex.peer_uid(sock) == int(os.environ["EIDOLON_EXECUTOR_UID"])
        ex.send(sock, {"version": 1, "id": "a" * 32, "tool": "text.stats", "text": "x", **extra})
        assert ex.receive(sock) == {"error": "refused"}


def test_core_cannot_modify_service_or_read_private_state():
    for name in ["EIDOLON_EXECUTOR_CODE", "EIDOLON_EXECUTOR_PRIVATE"]:
        path = Path(os.environ[name])
        assert not os.access(path, os.W_OK)
    with pytest.raises(PermissionError):
        Path(os.environ["EIDOLON_EXECUTOR_PRIVATE"]).read_bytes()
    assert not os.access(Path(os.environ["EIDOLON_EXECUTOR_SOCKET"]).parent, os.W_OK)
