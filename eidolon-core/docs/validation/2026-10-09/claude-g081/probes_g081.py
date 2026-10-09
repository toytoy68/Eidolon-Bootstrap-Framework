# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g081.py
# Description : Matrice observée stockage occupé / indisponible sur l'API de lecture et l'API de conversation (C-TASK-G081)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/validation/2026-10-09/claude-g081/probes_g081.py

Observation only: no Core file is modified. Synthetic Store in a temporary folder, loopback only.
Prints one JSON line per scenario: HTTP status, error code, elapsed time, side effects."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
import time

from eidolon_core import http_api
from eidolon_core.conversation_api import ConversationAPI
from eidolon_core.client_credentials import ClientCredentials
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

TOKEN = "synthetic_probe_token_" + "x" * 32


class Server:
    def __init__(self, state):
        self.server = http_api.ReadServer(state, TOKEN, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def post(self, path="/v1/missions", data=None, timeout=15):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=timeout)
        started = time.monotonic()
        try:
            conn.request("POST", path, body=json.dumps(data or {}).encode(),
                         headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
            response = conn.getresponse()
            raw = response.read()
        finally:
            conn.close()
        try:
            code = json.loads(raw).get("error")
        except ValueError:
            code = "NON_JSON"
        return response.status, code, round(time.monotonic() - started, 2)

    def close(self):
        self.server.shutdown(); self.thread.join(5); self.server.server_close()


def fresh(base, name):
    store = Store(Path(base) / name)
    Runtime(store).create(DEMO_REQUEST)
    return store


def record(scenario, status, code, elapsed, **extra):
    print(json.dumps({"api": "read", "scenario": scenario, "status": status, "error": code, "seconds": elapsed, **extra},
                     ensure_ascii=False), flush=True)


def read_api(base):
    store = fresh(base, "baseline")
    s = Server(store.directory)
    record("baseline", *s.post())

    # Another process holds an EXCLUSIVE lock (rollback journal): readers cannot read.
    holder = sqlite3.connect(store.path, isolation_level=None, timeout=0)
    holder.execute("BEGIN EXCLUSIVE")
    record("exclusive_lock_held", *s.post())
    holder.execute("ROLLBACK")
    # A RESERVED lock (writer not yet committing) still lets readers read.
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("UPDATE sync_metadata SET value=value WHERE key='store_id'")
    record("reserved_lock_held", *s.post())
    holder.execute("ROLLBACK"); holder.close()
    record("after_lock_released", *s.post())

    # Capacity saturation: MAX_CONNECTIONS idle sockets, then one more request.
    idle = [socket.create_connection(("127.0.0.1", s.server.server_port)) for _ in range(http_api.MAX_CONNECTIONS)]
    time.sleep(0.2)
    record("connections_saturated", *s.post())
    for sock in idle:
        sock.close()
    time.sleep(3.5)
    s.close()

    for name, damage in (("wal_mode", lambda p: sqlite3.connect(p).execute("PRAGMA journal_mode=WAL").fetchone()),
                         ("corrupted_header", lambda p: p.write_bytes(b"not a database" + p.read_bytes()[14:])),
                         ("file_missing", lambda p: p.unlink())):
        store = fresh(base, name)
        s = Server(store.directory)
        damage(store.path)
        status, code, elapsed = s.post()
        record(name, status, code, elapsed, file_exists_after=store.path.exists(),
               file_bytes_after=store.path.stat().st_size if store.path.exists() else None)
        s.close()

    store = fresh(base, "recovery_marker")
    s = Server(store.directory)
    (store.directory / "RECOVERY-REVIEW-ONLY").write_text("revue")
    record("recovery_review_only", *s.post())
    s.close()


def conversation_api(base):
    runtime = synthetic_runtime(Store(Path(base) / "conversations"))
    ConversationStore(runtime.store, create=True)
    key = ClientCredentials(runtime.store, create=True).pair(client_id="pc", actor="toytoy")["token"]
    api = ConversationAPI(runtime, dialogue_model=SimulatedDialogueModel(runtime.catalog))
    headers = {"Authorization": ["Bearer " + key], "Content-Type": ["application/json"]}

    def call(scenario):
        started = time.monotonic()
        status, body = api.handle("POST", "/v1/conversations/open", headers, b'{"client_key":"probe"}')
        print(json.dumps({"api": "conversations", "scenario": scenario, "status": status, "error": body.get("error"),
                          "seconds": round(time.monotonic() - started, 2)}), flush=True)
    call("baseline")
    path = Path(runtime.store.directory) / "conversations" / "conversations.sqlite3"
    holder = sqlite3.connect(path, isolation_level=None, timeout=0)
    holder.execute("BEGIN EXCLUSIVE")
    call("exclusive_lock_held")
    holder.execute("ROLLBACK"); holder.close()
    path.write_bytes(b"not a database" + path.read_bytes()[14:])
    call("corrupted_header")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        read_api(tmp)
        conversation_api(tmp)
    sys.exit(0)
