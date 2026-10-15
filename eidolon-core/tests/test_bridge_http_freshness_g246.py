# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_bridge_http_freshness_g246.py
# Description : Actual Memory, Qdrant, HTTP bridge, client and dialogue together.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing
import os
import threading

import pytest

from eidolon_core.conversation_store import ConversationStore
from eidolon_core.dialogue import Dialogue, SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.memory import BridgeMemory
from eidolon_core.store import Store


@pytest.mark.skipif(os.environ.get('EIDOLON_MEMORY_INTEGRATION') != '1', reason='explicit Memory integration')
def test_real_http_bridge_carries_stale_empty_match_and_digest_drift_to_dialogue(tmp_path):
    pytest.importorskip('qdrant_client')
    from qdrant_client import QdrantClient
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.indexing.qdrant_index import QdrantIndex
    from core.retrieval.contextual import ContextualRecall
    from services.memory_bridge import BoundedRecallServer, make_handler
    token = 'synthetic-' + 'x' * 40
    token_path = tmp_path / 'bridge-token'
    token_path.write_text(token)
    token_path.chmod(0o600)
    backend = FilesystemBackend(tmp_path / 'engine/memory/persistent', tmp_path / 'engine/memory/history')
    runtime = synthetic_runtime(Store(tmp_path / 'state'))
    conversations = ConversationStore(runtime.store, create=True)
    cid = conversations.open(client_id='pc', client_key='http-freshness')['conversation_id']
    with closing(QdrantClient(':memory:')) as qdrant:
        index = QdrantIndex(qdrant, 'eidolon_g246_test', embed=lambda _: [1., 0.],
                            dimensions=2, embedding_id='synthetic-v1', create=True)
        index.rebuild(backend.persistent_root)
        backend.store(Memory('new', content='power measurement'))
        server = BoundedRecallServer(('127.0.0.1', 0), make_handler(ContextualRecall(backend, index=index), token))
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        dialogue = Dialogue(conversations, SimulatedDialogueModel(runtime.catalog), runtime.catalog,
                            memory=BridgeMemory(str(token_path), port=server.server_port))
        try:
            def say(key):
                result = dialogue.respond(cid, client_id='pc', client_turn_key=key, text='Bonjour')
                assert result['diagnostics']['memory_error'] is None
                return result['reply']
            stale = say('stale')
            assert stale['context']['memory_index'] == 'INDEX_STALE'
            assert stale['context']['memory_items'] == 0 and stale['context']['partial']
            assert stale['sources'] == []
            index.rebuild(backend.persistent_root)
            matched = say('matched')
            assert matched['context']['memory_index'] == 'INDEX_SNAPSHOT_MATCH'
            assert matched['context']['memory_items'] == 1
            assert matched['sources'] == ['new@1']
            path = backend.persistent_root / 'new.md'
            path.write_bytes(path.read_bytes().replace(b'power measurement', b'other measurement'))
            drift = say('drift')
            assert drift['context']['memory_index'] == 'INDEX_STALE'
            assert drift['context']['memory_items'] == 0 and drift['context']['partial']
            assert drift['sources'] == []
        finally:
            dialogue.close()
            server.shutdown()
            server.server_close()
            thread.join(2)
            assert not thread.is_alive()
