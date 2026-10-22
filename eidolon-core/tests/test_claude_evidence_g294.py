# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_evidence_g294.py
# Description : Sondes G294 : réponse non étayée affichée sans signal de Core
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""G294-F02: Core records an ANSWER whose figures come from nowhere, or that cites a
source it never sent, with core_note None. The UI then shows it as an ordinary answer
(the small unsupported-citation line excepted). Strict xfail on the audited code."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_claude_holdout_g294 import CASES, canned_model, holdout  # noqa: E402



def turn(tmp_path, case_id, kind, text):
    case = CASES[case_id]
    factory, _ = canned_model({case["question"]: (kind, text)})
    from eidolon_core.client_credentials import ClientCredentials
    from eidolon_core.conversation_api import ConversationAPI
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.store import Store
    import json
    runtime = synthetic_runtime(Store(tmp_path / "s"))
    ConversationStore(runtime.store, create=True)
    key = ClientCredentials(runtime.store, create=True).pair(client_id="c", actor="a")["token"]
    api = ConversationAPI(runtime, dialogue_model=factory(runtime.catalog),
                          memory=holdout.CaseMemory(case["items"]) if case["items"] else None)
    head = {"Authorization": ["Bearer " + key], "Content-Type": ["application/json"]}
    try:
        _, opened = api.handle("POST", "/v1/conversations/open", head, json.dumps({"client_key": "k"}).encode())
        _, result = api.handle("POST", "/v1/conversations/turn", head, json.dumps(
            {"conversation_id": opened["conversation_id"], "client_turn_key": "t", "text": case["question"]}).encode())
        _, page = api.handle("POST", "/v1/conversations/page", head,
                             json.dumps({"conversation_id": opened["conversation_id"]}).encode())
        return result["reply"], page
    finally:
        api.close()


@pytest.mark.parametrize("case_id,text", [
    ("future-price", "Une V100 coûtera 900 euros en 2030."),
    ("missing-date", "Les V100 arrivent le 28 octobre [livraison@1]."),
    ("never-executed", "Score MLPerf Agents : 87 % [mlperf-plan@1]."),
])
def test_invented_figure_is_flagged(tmp_path, case_id, text):
    reply, _ = turn(tmp_path, case_id, "answer", text)
    assert reply["kind"] == "ANSWER"
    assert reply["core_note"] == "NUMBER_NOT_IN_SOURCES"
    assert reply["evidence_check"]["semantic_relevance_checked"] is False


def test_unsupported_citation_sets_a_core_note(tmp_path):
    reply, _ = turn(tmp_path, "invented-ref-in-memory", "answer", "La grappe compte 3 disques [fiche-xyz@4].")
    assert reply["core_note"] == "CITATION_UNSUPPORTED"


def test_flag_is_durable_and_replayed(tmp_path):
    reply, page = turn(tmp_path, "future-price", "answer", "Une V100 coûtera 900 euros en 2030.")
    recorded = [t for t in page["items"] if t.get("reply")][-1]["reply"]
    assert recorded["core_note"] == "NUMBER_NOT_IN_SOURCES" == reply["core_note"]


@pytest.mark.parametrize("case_id,text", [
    ("stale-corrected", "D'après la correction du 20 octobre, 6 Go [vm100-gpu@1]."),
    ("useless-clarification", "Le pont écoute sur le port 18765 [pont-port@1]."),
    ("homonym", "Hermes Agent est en version 0.22.3 [hermes-agent@1]."),
])
def test_control_grounded_answers_carry_no_note(tmp_path, case_id, text):
    """Green on the audited code and with the patch: figures present in the notes sent."""
    reply, _ = turn(tmp_path, case_id, "answer", text)
    assert reply["core_note"] is None


def test_known_limit_calculation_is_flagged_not_blocked(tmp_path):
    """600 = 2 x 300 is correct but absent from the note: flagged for review, still an ANSWER."""
    reply, _ = turn(tmp_path, "calculation", "answer", "Ensemble, 600 W [gpu-tdp@1].")
    assert reply["kind"] == "ANSWER" and reply["core_note"] == "NUMBER_NOT_IN_SOURCES"


def test_known_limit_related_but_wrong_evidence_is_not_detected(tmp_path):
    """The G293 P1: a figure from ANOTHER benchmark, present in a note sent, cited correctly.
    No lexical check can see that the note answers a different question (green before and after)."""
    reply, _ = turn(tmp_path, "never-executed", "answer", "Nous avons obtenu 25 sur 30 [banc-dialogue@1].")
    assert reply["kind"] == "ANSWER" and reply["core_note"] is None


def test_history_user_numbers_count_but_model_guesses_do_not():
    from eidolon_core.dialogue import evidence_check
    reply = {"kind": "ANSWER", "model_text": "Donc 42 et 7.", "core_note": None, "citations": {"unsupported": []}}
    history = [{"user": "Retiens le nombre 42.", "reply_text": "D'accord, et 7 aussi."}]
    evidence_check(reply, text="Et alors ?", history=history, memory=None, observations=[])
    assert reply["evidence_check"]["numbers_not_in_sources"] == ["7"]
