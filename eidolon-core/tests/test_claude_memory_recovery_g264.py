# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_memory_recovery_g264.py
# Description : Reprise de Core après indisponibilité de Memory, pont HTTP réel synthétique (Claude, G264-10)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit integration (EIDOLON_MEMORY_INTEGRATION=1, Memory on PYTHONPATH), loopback, synthetic corpus.
Real Memory backend, real HTTP bridge, real Core client and Dialogue; the model is the simulated one wrapped
to RECORD the memory it is given. Server-side recovery only; the INDEX_ display is not re-reviewed (G262-7)."""
import os
import threading

import pytest

from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import Dialogue, SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.memory import BridgeMemory
from eidolon_core.store import Store

pytestmark = pytest.mark.skipif(os.environ.get("EIDOLON_MEMORY_INTEGRATION") != "1",
                                reason="explicit Memory integration (EIDOLON_MEMORY_INTEGRATION=1)")
TOKEN = "synthetic-" + "t" * 40


class Recording(SimulatedDialogueModel):
    def __init__(self, catalog):
        super().__init__(catalog)
        self.memories = []

    def reply(self, text, history, memory, *rest, **kwargs):
        self.memories.append(None if memory is None else [i["information_id"] for i in memory["items"]])
        return super().reply(text, history, memory, *rest, **kwargs)


class Bridge:
    """A real bridge that can be stopped and restarted on the SAME port."""

    def __init__(self, backend):
        from core.retrieval.contextual import ContextualRecall
        from services.memory_bridge import make_handler
        self.handler = make_handler(ContextualRecall(backend), TOKEN)
        self.port, self.server, self.thread, self.calls = 0, None, None, 0

    def start(self):
        from services.memory_bridge import BoundedRecallServer
        self.server = BoundedRecallServer(("127.0.0.1", self.port), self.handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        assert not self.thread.is_alive()


@pytest.fixture
def world(tmp_path):
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    token_path = tmp_path / "bridge-token"
    token_path.write_text(TOKEN)
    token_path.chmod(0o600)
    backend = FilesystemBackend(tmp_path / "engine/memory/persistent", tmp_path / "engine/memory/history")
    backend.store(Memory("before", content="power measurement before the outage"))
    runtime = synthetic_runtime(Store(tmp_path / "state"))
    conversations = ConversationStore(runtime.store, create=True)
    bridge = Bridge(backend)
    bridge.start()
    model = Recording(runtime.catalog)
    dialogue = Dialogue(conversations, model, runtime.catalog,
                        memory=BridgeMemory(str(token_path), port=bridge.port, timeout=2.0))
    try:
        yield dialogue, conversations, bridge, backend, model
    finally:
        dialogue.close()
        if bridge.thread is not None and bridge.thread.is_alive():
            bridge.stop()


def turn(dialogue, cid, key, text="power measurement"):
    return dialogue.respond(cid, client_id="pc", client_turn_key=key, text=text)


def test_outage_then_recovery_never_attributes_an_earlier_memory_to_a_later_turn(world):
    from core.backend.models import Memory
    dialogue, conversations, bridge, backend, model = world
    first = conversations.open(client_id="pc", client_key="g264-a")["conversation_id"]
    a = turn(dialogue, first, "a")
    assert a["diagnostics"]["memory_error"] is None and a["reply"]["sources"] == ["before@1"]
    assert a["reply"]["context"]["memory"] == "sent" and model.memories[-1] == ["before"]

    bridge.stop()                                                   # Memory unavailable
    b = turn(dialogue, first, "b")
    assert b["diagnostics"]["memory_error"] is not None and TOKEN not in str(b)
    assert b["reply"]["sources"] == [] and b["reply"]["context"]["memory"] == "unavailable"
    assert b["reply"]["context"]["memory_items"] == 0 and "memory_index" not in b["reply"]["context"]
    assert model.memories[-1] is None                               # the model got no memory, not A's

    backend.store(Memory("during", content="power measurement written during the outage"))
    bridge.start()                                                  # same port, nothing restarted in Core
    second = conversations.open(client_id="pc", client_key="g264-b")["conversation_id"]
    c = turn(dialogue, second, "c")
    assert c["diagnostics"]["memory_error"] is None
    assert sorted(c["reply"]["sources"]) == ["before@1", "during@1"]  # current state, fetched for THIS turn
    assert sorted(model.memories[-1]) == ["before", "during"]
    d = turn(dialogue, first, "d")                                  # the conversation that saw the outage
    assert d["diagnostics"]["memory_error"] is None and d["reply"]["context"]["memory"] == "sent"
    # Each turn keeps its own context: B stays "unavailable" in the stored history.
    stored = conversations.page(first)["items"]
    assert [i["reply"]["context"]["memory"] for i in stored] == ["sent", "unavailable", "sent"]
    assert [i["reply"]["sources"] for i in stored] == [["before@1"], [], sorted(d["reply"]["sources"])]


def test_repeated_outage_counts_one_error_per_turn_and_no_hidden_retry(world):
    dialogue, conversations, bridge, backend, model = world
    cid = conversations.open(client_id="pc", client_key="g264-c")["conversation_id"]
    bridge.stop()
    errors = [turn(dialogue, cid, f"k{n}")["diagnostics"]["memory_error"] for n in range(3)]
    assert all(e is not None for e in errors) and len(model.memories) == 3 and model.memories == [None] * 3
    bridge.start()
    assert turn(dialogue, cid, "back")["diagnostics"]["memory_error"] is None


def test_a_replayed_turn_key_after_recovery_does_not_refetch_or_change_its_context(world):
    dialogue, conversations, bridge, backend, model = world
    cid = conversations.open(client_id="pc", client_key="g264-d")["conversation_id"]
    bridge.stop()
    first = turn(dialogue, cid, "same-key")
    bridge.start()
    again = turn(dialogue, cid, "same-key")                         # client retry of the SAME turn
    assert again["reply"]["context"] == first["reply"]["context"]   # recorded answer, not a new recall
    assert len(model.memories) == 1
