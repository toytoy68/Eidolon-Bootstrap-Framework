# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_veille_holdout_metadata.py
# Description : Holdout metadata is source data, never an answer oracle
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('veille_holdout',
    Path(__file__).resolve().parents[1] / 'tools/evaluation/dialogue_holdout_g294.py')
holdout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(holdout)
CaseMemory = holdout.CaseMemory


def test_rich_notes_preserve_dates_without_aliasing_the_fixture():
    note = {'information_id': 'dated', 'content': 'Hier inscription.',
            'provenance': {'timestamp': '2026-07-03T09:00:00+02:00'},
            'temporal': {'created_at': '2026-10-21T12:00:00Z'}}
    item = CaseMemory([note]).recall('Quand ?')['items'][0]
    assert item['provenance'] == note['provenance']
    assert item['temporal'] == note['temporal']
    item['temporal']['created_at'] = 'mutated'
    assert note['temporal']['created_at'] == '2026-10-21T12:00:00Z'


def test_old_pair_notes_keep_their_existing_shape():
    item = CaseMemory([['legacy', 'Ancienne note.']]).recall('note')['items'][0]
    assert (item['information_id'], item['revision'], item['content']) == ('legacy', 1, 'Ancienne note.')


def test_answer_oracle_fields_are_not_accepted_as_evidence():
    with pytest.raises(ValueError, match='synthetic evidence'):
        CaseMemory([{'information_id': 'note', 'content': 'Texte.',
                     'expected_answer': 'Do not leak this answer'}]).recall('question')


@pytest.mark.parametrize('text,expected', [
    ('Je ne peux donc pas affirmer ce nombre avec certitude.', True),
    ('Je ne peux pas confirmer cette date.', True),
    ('Le nombre est donc 58, je ne doute pas de cette réponse.', False),
    ('Le mot de passe est orchidée.', False),
])
def test_abstention_handles_donc_without_accepting_any_negation(text, expected):
    assert bool(holdout.ABSTAIN.search(text)) == expected
