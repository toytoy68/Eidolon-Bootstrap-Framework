# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_memory_freshness_g244.py
# Description : Preserve and expose Memory index uncertainty across dialogue.
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict
import os

import pytest

from eidolon_core import conversation as cv, dialogue as dg
from eidolon_core.contracts import ContractError, validate_context
from tests.test_dialogue import Base


def status(state='INDEX_STALE'):
    result = dict(state=state, reason='FULL_SOURCE_DIGEST_MISMATCH', generation='eidolon_test__abc',
                  source_digest='a' * 64, canonical_digest='b' * 64)
    if state == 'INDEX_SNAPSHOT_MATCH':
        result.update(reason='FULL_SOURCE_DIGEST_MATCH', canonical_digest='a' * 64)
    if state == 'INDEX_UNVERIFIED':
        result.update(reason='NO_FULL_SOURCE_DIGEST', source_digest=None, canonical_digest=None)
    return result


@pytest.mark.parametrize('state', ['INDEX_STALE', 'INDEX_SNAPSHOT_MATCH', 'INDEX_UNVERIFIED'])
def test_valid_index_status_is_preserved_without_aliasing(state):
    original = {'items': [], 'index_status': status(state)}
    result = validate_context(original)
    assert result == original
    result['index_status']['state'] = 'edited'
    assert original['index_status']['state'] == state


@pytest.mark.parametrize('mutation', [
    {'state': 'INDEX_CURRENT'}, {'state': []}, {'reason': 'invented'},
    {'source_digest': 'wrong'}, {'canonical_digest': 'a' * 64},
    {'generation': '../secret'}, {'generation': None}, {'extra': 'unexpected'},
    {'state': 'INDEX_SNAPSHOT_MATCH'}, {'state': 'INDEX_UNVERIFIED'},
])
def test_inconsistent_index_status_is_rejected(mutation):
    value = status()
    value.update(mutation)
    with pytest.raises(ContractError, match='index status'):
        validate_context({'items': [], 'index_status': value})


@pytest.mark.parametrize('value', [[], 'INDEX_STALE', True, {}, {'state': 'INDEX_STALE'}])
def test_malformed_index_status_is_rejected(value):
    with pytest.raises(ContractError, match='index status'):
        validate_context({'items': [], 'index_status': value})


def test_optional_index_status_preserves_older_and_lexical_providers():
    assert validate_context({'items': []}) == {'items': []}
    assert validate_context({'items': [], 'index_status': None})['index_status'] is None


class MemoryFreshnessDialogueTests(Base):
    def test_empty_stale_memory_is_sent_as_uncertain_and_announced(self):
        seen = []
        class Memory:
            def recall(self, query):
                return {'items': [], 'index_status': status()}
        class Spy(dg.SimulatedDialogueModel):
            def reply(self, text, history, memory):
                seen.append(deepcopy(memory))
                return super().reply(text, history, memory)
        result = self.say(self.dialogue(Spy(self.runtime.catalog), memory=Memory()), 'Bonjour')
        assert seen[0]['index_status'] == status()
        note = result['reply']['context']
        assert note['memory_index'] == 'INDEX_STALE'
        assert note['partial'] is True and note['memory_items'] == 0
        assert result['reply']['sources'] == []

    def test_snapshot_match_does_not_invent_partial_context(self):
        class Memory:
            def recall(self, query):
                return {'items': [], 'index_status': status('INDEX_SNAPSHOT_MATCH')}
        result = self.say(self.dialogue(memory=Memory()), 'Bonjour')
        note = result['reply']['context']
        assert note['memory_index'] == 'INDEX_SNAPSHOT_MATCH'
        assert note['partial'] is False

    def test_unverified_index_is_announced(self):
        class Memory:
            def recall(self, query):
                return {'items': [], 'index_status': status('INDEX_UNVERIFIED')}
        result = self.say(self.dialogue(memory=Memory()), 'Bonjour')
        assert result['reply']['context']['memory_index'] == 'INDEX_UNVERIFIED'
        assert result['reply']['context']['partial'] is True

    def test_bad_diagnostic_degrades_memory_without_stopping_dialogue(self):
        class Memory:
            def recall(self, query):
                return {'items': [], 'index_status': {'state': 'INDEX_CURRENT'}}
        result = self.say(self.dialogue(memory=Memory()), 'Bonjour')
        assert result['diagnostics']['memory_error'] == 'ContractError'
        assert result['reply']['context']['memory'] == 'unavailable'
        assert 'memory_index' not in result['reply']['context']

    def test_dropped_memory_does_not_claim_its_status_was_sent(self):
        class Memory:
            def recall(self, query):
                return {'items': [], 'index_status': status()}
        class Tight(dg.SimulatedDialogueModel):
            def reply(self, text, history, memory):
                raw, info = super().reply(text, history, memory)
                return raw, {**info, 'memory_dropped': True}
        result = self.say(self.dialogue(Tight(self.runtime.catalog), memory=Memory()), 'Bonjour')
        assert result['reply']['context']['memory'] == 'dropped_for_budget'
        assert 'memory_index' not in result['reply']['context']


@pytest.mark.parametrize('state', ['none', 'unavailable', 'dropped_for_budget'])
def test_index_note_cannot_claim_unsent_metadata(state):
    value = dict(history_sent=0, history_excluded=0, memory=state, memory_items=0,
                 memory_truncated_items=0, observations_sent=0, observations_excluded=0,
                 memory_index='INDEX_STALE')
    with pytest.raises(ContractError):
        cv.validate_context_note(value)


@pytest.mark.skipif(os.environ.get('EIDOLON_MEMORY_INTEGRATION') != '1', reason='explicit Memory integration')
def test_actual_memory_bundle_passes_core_boundary_and_prompt(tmp_path):
    pytest.importorskip('qdrant_client')
    from qdrant_client import QdrantClient
    from core.backend.filesystem import FilesystemBackend
    from core.backend.models import Memory
    from core.indexing.qdrant_index import QdrantIndex
    from core.retrieval.contextual import ContextualRecall
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.store import Store
    data = FilesystemBackend(tmp_path / 'memory/persistent', tmp_path / 'memory/history')
    with closing(QdrantClient(':memory:')) as client:
        index = QdrantIndex(client, 'eidolon_g244_test', embed=lambda _: [1., 0.],
                            dimensions=2, embedding_id='synthetic-v1', create=True)
        index.rebuild(data.persistent_root)
        data.store(Memory('new', content='synthetic new evidence'))
        bundle = validate_context(asdict(ContextualRecall(data, index=index).recall('evidence')))
        assert bundle['items'] == [] and bundle['index_status']['state'] == 'INDEX_STALE'
        catalog = synthetic_runtime(Store(tmp_path / 'state')).catalog
        messages = dg.build_messages('question', [], bundle, catalog)
        assert 'INDEX_STALE' in messages[1]['content']
        assert 'absence of a fact from memory' in messages[0]['content']
