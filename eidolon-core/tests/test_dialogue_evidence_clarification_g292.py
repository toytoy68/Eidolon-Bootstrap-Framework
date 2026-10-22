"""Guard the Core prompt policy for bounded memory and clarification behavior."""
from eidolon_core.dialogue import SYSTEM_PROMPT


def test_retrieval_candidates_are_not_automatically_proof():
    assert 'Memory returns retrieval candidates, not proof of answerability' in SYSTEM_PROMPT
    assert 'semantic similarity, high score' in SYSTEM_PROMPT
    assert 'Never cite a merely related memory' in SYSTEM_PROMPT


def test_clarification_only_when_it_can_help():
    assert 'ONLY if the user\'s answer can resolve an ambiguity' in SYSTEM_PROMPT
    assert 'otherwise use kind answer to state the limitation' in SYSTEM_PROMPT
    assert 'Do not ask for clarification when the evidence already supports' in SYSTEM_PROMPT


def test_future_and_conflicting_facts_have_explicit_reserves():
    assert 'future prices, forecasts or hypothetical values' in SYSTEM_PROMPT
    assert 'If sources conflict, are stale or are UNVERIFIED' in SYSTEM_PROMPT
