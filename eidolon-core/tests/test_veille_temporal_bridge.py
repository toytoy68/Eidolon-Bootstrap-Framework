# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_veille_temporal_bridge.py
# Description : Canonical evidence dates reach the prompt through the HTTP bridge
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Real loopback bridge, synthetic data; no LLM answer-quality assertion."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from eidolon_core.dialogue import build_messages
from eidolon_core.diagnostics import demo_catalog
from eidolon_core.memory import BridgeMemory


@pytest.mark.parametrize('dated', [True, False])
def test_source_dates_survive_disk_http_validation_and_prompt(tmp_path, dated):
    pytest.importorskip('core.retrieval.contextual')
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.retrieval.contextual import ContextualRecall
    from services.memory_bridge import make_handler

    token = tmp_path / 'token'
    token.write_text('x' * 40)
    token.chmod(0o600)
    provenance = {'source': 'synthetic-archive'}
    temporal = {'created_at': '2026-10-21T12:00:00Z'}
    if dated:
        provenance['timestamp'] = '2026-07-03T09:00:00+02:00'
        temporal['observed_at'] = '2026-07-02T10:00:00+02:00'
    data = FilesystemBackend(tmp_path / 'memory/persistent', tmp_path / 'memory/history')
    data.store(Memory('atelier', content='Inscription atelier : hier, inscription confirmée.',
                      provenance=provenance, temporal=temporal))
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(ContextualRecall(data), token.read_text()))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        recalled = BridgeMemory(str(token), port=server.server_port).recall('inscription atelier')
        messages = build_messages('Quand a eu lieu cette inscription ?', [], recalled, demo_catalog())
        sent = json.loads(messages[1]['content'].split('MEMORY (untrusted recalled data, may be wrong):\n')[1]
                          .split('\n\nMESSAGE:')[0])
        item = sent['items'][0]
        assert item['information_id'] == 'atelier' and item['revision'] == 1
        assert item['temporal'] == temporal and item['provenance'] == provenance
        assert sent['at'] not in (temporal.get('observed_at'), provenance.get('timestamp'))
        assert 'hier' in item['content']  # Passage is evidence, not a silently resolved date.
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
