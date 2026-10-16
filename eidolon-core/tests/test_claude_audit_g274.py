# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_audit_g274.py
# Description : Sondes de l'audit global G274 (Claude) — défauts reproduits
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Each test states the expected behaviour and fails on the audited code.

Synthetic data only; real Memory bridge over loopback where the contract matters.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from tests.test_beta_runtime_g270 import config

# Strict: an XPASS fails the run, so the marker must go with the correction.
F001 = pytest.mark.xfail(strict=True, reason="G274-F001: raw turn text sent as recall query")
F002 = pytest.mark.xfail(strict=True, reason="G274-F002: one unextractable file aborts the root")
F003 = pytest.mark.xfail(strict=True, reason="G274-F003: failed admission leaves a WAITING head")
F004 = pytest.mark.xfail(strict=True, reason="G274-F004: equal-FRR tie broken by the lowest threshold")


# --------------------------------------------------------------------------- F001
def _real_bridges(tmp_path, stack, conf):
    pytest.importorskip("core.information.remember")
    from core.backend.filesystem import FilesystemBackend
    from services.memory_bridge import build_recall, BoundedRecallServer, make_handler
    from services.remember_bridge import RememberEndpoint
    from services.profile_binding import binding
    for i in range(2):
        root = tmp_path / f"memory{i}"
        FilesystemBackend(root / "memory/persistent", root / "memory/history")
        binding(root, f"user{i}", apply=True)
        handler = make_handler(build_recall(root), str(i) * 40, remember=RememberEndpoint(root, f"user{i}"),
                               write_token=str(i + 2) * 40, profile_id=f"user{i}")
        server = BoundedRecallServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        conf["profiles"][f"user{i}"]["memory_port"] = server.server_address[1]


def _api(tmp_path, services):
    from eidolon_core.client_credentials import ClientCredentials
    from eidolon_core.conversation_api import ConversationAPI
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.dialogue import SimulatedDialogueModel
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.store import Store
    runtime = synthetic_runtime(Store(tmp_path / "core-state"))
    ConversationStore(runtime.store, create=True)
    key = ClientCredentials(runtime.store, create=True).pair(client_id="pc0", actor="actor0")["token"]
    api = ConversationAPI(runtime, dialogue_model=SimulatedDialogueModel(runtime.catalog), services=services)

    def call(route, body):
        return api.handle("POST", "/v1/conversations/" + route,
                          {"Authorization": ["Bearer " + key], "Content-Type": ["application/json"]},
                          json.dumps(body).encode())
    return api, call


TURNS = [
    pytest.param("Que sais-tu de la V100 ?", id="control-one-line"),       # green on the audited code
    pytest.param("Bonjour,\nque sais-tu de la V100 ?", id="multiline", marks=F001),
    pytest.param("Que sais-tu de la V100 ? " + "contexte " * 70, id="long", marks=F001),  # 600+ chars
    pytest.param("Que sais-tu de la V100 ?\t(tabulation)", id="tab", marks=F001),
]


@pytest.mark.parametrize("text", TURNS)
def test_f001_ordinary_turn_text_still_reaches_memory_recall(tmp_path, text):
    """G274-F001: the raw turn text is sent as the bridge query (<=500 chars, no control).

    Expected: a healthy bridge holding a matching memory is used for an ordinary
    multi-line or long message. Observed on 940616c: memory state 'unavailable'.
    """
    from eidolon_core.beta_runtime import BetaRuntime
    conf = config(tmp_path)
    with ExitStack() as stack:
        _real_bridges(tmp_path, stack, conf)
        services = BetaRuntime(conf)
        api, call = _api(tmp_path, services)
        try:
            proposal = services.preview("pc0", "actor0", "keep", "remember", {"text": "La V100 est en cave."})
            assert services.commit("pc0", proposal["proposal"]["id"], proposal["sha256"])["state"] == "COMMITTED"
            status, opened = call("open", {"client_key": "page"})
            assert status == 200
            status, result = call("turn", {"conversation_id": opened["conversation_id"],
                                           "client_turn_key": "t1", "text": text})
            assert status == 200, result
            context = result["reply"]["context"]
            assert context["memory"] == "sent", context
            assert context["memory_items"] >= 1, context
        finally:
            api.close()


@pytest.mark.parametrize("text", TURNS)
def test_f001_shared_bridge_memory_path(tmp_path, text):
    """Same defect on the historical --memory-bridge-token-file path (BridgeMemory)."""
    pytest.importorskip("core.information.remember")
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from services.memory_bridge import build_recall, BoundedRecallServer, make_handler
    from eidolon_core.dialogue import Dialogue
    from eidolon_core.memory import BridgeMemory
    root = tmp_path / "memory"
    FilesystemBackend(root / "memory/persistent", root / "memory/history").store(
        Memory("v100", content="La V100 est en cave."))
    server = BoundedRecallServer(("127.0.0.1", 0), make_handler(build_recall(root), "r" * 40))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    token = tmp_path / "token"
    token.write_text("r" * 40)
    token.chmod(0o600)
    try:
        dialogue = Dialogue.__new__(Dialogue)
        dialogue.memory = BridgeMemory(str(token), port=server.server_address[1])
        context, sources, error = dialogue._recall(text)
        assert error is None and sources == ["v100@1"], (error, sources)
    finally:
        server.shutdown()
        server.server_close()


# --------------------------------------------------------------------------- F002
def _library(tmp_path):
    from eidolon_core.library_sync import Library
    conf = config(tmp_path)
    return Library(conf, conf["state_directory"]), Path(conf["profiles"]["user0"]["file_roots"]["nas"])


def _image_only_pdf():
    # Minimal valid PDF, one empty page: pdftotext succeeds with no text layer (a scan).
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


@pytest.mark.parametrize("name,payload", [
    pytest.param("vide.txt", b"", id="empty", marks=F002),
    pytest.param("blanc.md", b"   \n", id="blank", marks=F002),
    pytest.param("gros.pdf", b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024), id="over-4MiB", marks=F002),
    pytest.param("scan.pdf", None, id="image-only-pdf", marks=F002),   # no text layer
    pytest.param("autre.txt", b"Un second fichier lisible.", id="control-readable"),
])
def test_f002_one_unextractable_document_does_not_block_the_whole_root(tmp_path, name, payload):
    """G274-F002: any single extraction refusal aborts the complete generation.

    Expected: the readable note is synchronized and the other file is reported as
    present but not extracted. Observed on 940616c: ValueError, nothing synchronized,
    and every later --watch tick is refused for as long as the file exists.
    """
    if payload is None:
        if not Path("/usr/bin/pdftotext").is_file():
            pytest.skip("pdftotext absent")
        payload = _image_only_pdf()
    library, root = _library(tmp_path)
    (root / name).write_bytes(payload)
    result = library.scan("pc0", "nas")
    assert result["files"] >= 1
    paths = {entry["path"] for entry in library.page("pc0", "nas")["entries"]}
    assert "note.txt" in paths


# --------------------------------------------------------------------------- F003
def _gpu(tmp_path):
    from eidolon_core.gpu_queue import Queue
    directory = tmp_path / "gpu"
    directory.mkdir(mode=0o700)
    return Queue({"schema": "eidolon-gpu-queue/1", "directory": str(directory), "capacity_mib": 16000,
                  "resident_mib": 2000, "dialogue_mib": 6000, "media_mib": 9000})


@F003
def test_f003_transient_lock_during_admission_leaves_no_orphan_head(tmp_path, monkeypatch):
    """G274-F003: an exception between enqueue and admission leaves a WAITING row.

    A real competing SQLite lock held 2.5 s (> the 2 s busy timeout) right after the
    enqueue makes acquire() raise. Expected: the failed attempt withdraws its request.
    Observed on 940616c: the WAITING dialogue row (priority 100 + aging) stays at the
    head, and every later dialogue turn ends with GPU_ADMISSION_TIMEOUT although the
    whole capacity is free, until an operator runs cancel-waiting.
    """
    from eidolon_core.contracts import ContractError
    from eidolon_core.gpu_queue import Queue, ScheduledModel
    queue = _gpu(tmp_path)
    original = Queue.enqueue
    path = Path(queue.config["directory"]) / "gpu-queue.sqlite3"
    hold = threading.Event()

    def enqueue_then_competing_lock(self, key, kind):
        row = original(self, key, kind)
        if not hold.is_set():
            hold.set()
            other = sqlite3.connect(path, timeout=0, isolation_level=None, check_same_thread=False)
            other.execute("BEGIN EXCLUSIVE")
            threading.Timer(2.5, lambda: (other.execute("COMMIT"), other.close())).start()
        return row
    monkeypatch.setattr(Queue, "enqueue", enqueue_then_competing_lock)

    class Model:
        model_id = "synthetic"

        def reply(self, *args, **kwargs):
            return "ok"
    with pytest.raises(sqlite3.OperationalError):
        ScheduledModel(Model(), queue, seconds=5).reply("first")
    time.sleep(0.8)  # the competing transaction is gone
    assert [job["state"] for job in queue.inspect()["jobs"]] == [], queue.inspect()["jobs"]
    assert ScheduledModel(Model(), queue, seconds=1).reply("second") == "ok"


def test_f003_control_operator_cancel_restores_admission(tmp_path):
    """Control (green on 940616c): the documented manual recovery does work."""
    from eidolon_core.contracts import ContractError
    from eidolon_core.gpu_queue import ScheduledModel
    queue = _gpu(tmp_path)
    queue.enqueue("dialogue-orphan", "dialogue")

    class Model:
        def reply(self, *args, **kwargs):
            return "ok"
    with pytest.raises(ContractError, match="GPU_ADMISSION_TIMEOUT"):
        ScheduledModel(Model(), queue, seconds=0.3).reply("blocked")
    queue.cancel_waiting("dialogue-orphan")
    assert ScheduledModel(Model(), queue, seconds=0.3).reply("free") == "ok"


# --------------------------------------------------------------------------- F004
def _trials(rows):
    return [{"id": f"t{i}", "split": split, "sessions": sessions, "genuine": genuine, "score": score}
            for i, (split, sessions, genuine, score) in enumerate(rows, 1)]


def _dataset(rows):
    return {"schema": "eidolon-identity-evaluation/1", "synthetic": True, "trials": _trials(rows),
            "engine": {"name": "synthetic", "modality": "voice", "model_sha256": "a" * 64,
                       "preprocessing": "synthetic"}}


SEPARABLE = [("calibration", ["a", "b"], True, .9), ("calibration", ["a", "c"], True, .9),
             ("calibration", ["b", "c"], False, .3), ("calibration", ["a", "d"], False, .5),
             ("validation", ["x", "y"], True, .9), ("validation", ["x", "z"], False, .55)]


@F004
@pytest.mark.parametrize("max_far", [0.0, 0.5])
def test_f004_equal_frr_prefers_the_threshold_that_accepts_fewer_impostors(max_far):
    """G274-F004: ties on FRR are broken by the LOWEST threshold (min of tuples).

    Calibration genuine 0.9/0.9, impostors 0.3/0.5: 0.9 separates perfectly (FRR 0, FAR 0).
    Observed on 940616c: 0.5+eps (target 0) or 0.3+eps (target 0.5), and the validation
    impostor at 0.55 is accepted.
    """
    from eidolon_core.identity_evaluation import evaluate
    report = evaluate(_dataset(SEPARABLE), max_far=max_far)
    assert report["calibration"]["frr"] == 0
    assert report["calibration"]["far"] == 0
    assert report["candidate_threshold"] == 0.9
    assert report["validation"]["false_accepts"] == 0


def test_f004_control_frr_stays_the_first_criterion():
    """Control (green on 940616c and with the patch): FRR first, FAR within target."""
    from eidolon_core.identity_evaluation import evaluate
    rows = [("calibration", ["a", "b"], True, .8), ("calibration", ["a", "c"], True, .6),
            ("calibration", ["b", "c"], False, .7), ("calibration", ["c", "d"], False, .65),
            ("validation", ["x", "y"], True, .9), ("validation", ["x", "z"], False, .2)]
    report = evaluate(_dataset(rows), max_far=0.5)
    assert report["calibration"]["frr"] == 0.5 and report["calibration"]["far"] <= 0.5
