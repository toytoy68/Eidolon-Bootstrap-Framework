# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_holdout_g294.py
# Description : Holdout G294 hors modèle : notation stricte et parcours de conversation réel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Offline: canned model outputs through the production path (ChatDialogueModel with a
fake Ollama transport, ConversationAPI, decide_reply). No real model is qualified here."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "evaluation"))
import dialogue_holdout_g294 as holdout  # noqa: E402

CASES = {c["id"]: c for c in holdout.load(Path(holdout.__file__).with_name("dialogue_holdout_g294.json"))["cases"]}


def canned_model(outputs, model="gemma3:4b"):
    """Production ChatDialogueModel; only the HTTP transport is replaced."""
    from eidolon_core.dialogue import ChatDialogueModel
    from eidolon_core.model_config import _decode
    config = {"version": 1, "provider": "ollama", "endpoint": "http://127.0.0.1:11500", "model": model,
              "think": False, "options": {"num_ctx": 8192, "num_predict": 768, "temperature": 0, "seed": 42},
              "timeout_seconds": 150, "max_prompt_bytes": 24000}
    seen = []

    class Transport:
        def post(self, url, body, timeout=None, max_bytes=None, headers=None):
            request = json.loads(body)
            seen.append(request)
            content = request["messages"][-1]["content"]
            text = next(v for k, v in outputs.items() if k in content)
            message = json.dumps({"version": 1, "kind": text[0], "text": text[1], "proposal": None})
            return 200, "application/json", json.dumps({"model": model, "message": {"role": "assistant",
                "content": message}, "done": True, "done_reason": "stop"}).encode()

    def factory(catalog):
        model_ = ChatDialogueModel(_decode(json.dumps(config).encode()), catalog)
        model_.adapter.transport = Transport()
        return model_
    return factory, seen


@pytest.mark.parametrize("case_id,kind,text,expected", [
    # Fabricated answers that the G287 scorer accepts (its abstention check is any "pas").
    ("never-executed", "answer", "Nous avons obtenu 25 sur 30, pas mal [banc-dialogue@1].", "FAIL"),
    ("wrong-benchmark", "answer", "Le score est de 71,4 %, je n'en doute pas [banc-mmlu@1].", "FAIL"),
    ("missing-date", "answer", "Les V100 arrivent le 28 octobre, pas avant.", "FAIL"),
    ("future-price", "answer", "Une V100 coûtera 900 euros en 2030, pas plus.", "FAIL"),
    ("invented-ref-in-memory", "answer", "La grappe compte 3 disques [fiche-xyz@4].", "FAIL"),
    ("homonym", "answer", "Version 0.22.3 [hermes-agent@1] ; le sac a coûté 250 euros.", "FAIL"),
    ("useless-clarification", "clarification", "De quel pont parles-tu ?", "FAIL"),
    ("stale-corrected", "answer", "La carte a 6 Go.", "FAIL"),                      # right value, no citation
    # Correct behaviour.
    ("never-executed", "answer", "Je ne trouve aucun score MLPerf Agents : aucune exécution [mlperf-plan@1].", "PASS"),
    ("wrong-benchmark", "answer", "Je ne trouve pas de résultat HellaSwag-FR ; seul MMLU-FR a été lancé [banc-mmlu@1].", "PASS"),
    ("missing-date", "answer", "La date n'est pas confirmée par le vendeur [livraison@1].", "PASS"),
    ("stale-corrected", "answer", "D'après la correction du 20 octobre, 6 Go [vm100-gpu@1].", "PASS"),
    ("useful-clarification", "clarification", "Parles-tu de VM100 ou de VM110 ?", "PASS"),
    ("homonym", "answer", "Hermes Agent est en version 0.22.3 [hermes-agent@1].", "PASS"),
    # Abstains but repeats a figure of the other note: a human must read it.
    ("wrong-year", "answer", "Je ne trouve pas de mesure en 2026 ; celle de 2025 donnait 41 [debit-2025@1].", "REVIEW"),
])
def test_strict_verdicts_through_the_production_conversation_path(tmp_path, case_id, kind, text, expected):
    case = CASES[case_id]
    factory, seen = canned_model({case["question"]: (kind, text)})
    row = holdout.run_case(case, factory, tmp_path)
    assert row["verdict"] == expected, row
    assert len(seen) == 1                                                  # one real adapter call per turn
    if case["items"]:
        assert case["items"][0][1] in seen[0]["messages"][-1]["content"]  # notes reached the model


def test_g287_scorer_accepts_these_fabrications():
    """Contrast: the same outputs pass the abstention check of tools/evaluation/dialogue_g287.py."""
    source = (Path(holdout.__file__).with_name("dialogue_g287.py")).read_text()
    assert "any(x in t.lower() for x in ('pas','inconnu','aucun','ignore','insuffisant','manqu'))" in source
    for text in ("Nous avons obtenu 25 sur 30, pas mal.", "Les V100 arrivent le 28 octobre, pas avant."):
        assert any(x in text.lower() for x in ('pas', 'inconnu', 'aucun', 'ignore', 'insuffisant', 'manqu'))
        assert not holdout.ABSTAIN.search(text)


def test_holdout_shape():
    assert len(CASES) == 22
    assert {c["family"] for c in CASES.values()} >= {"near_negative", "homonym", "stale", "conflict",
        "reference_spoof", "injection", "paraphrase", "clarification", "future", "unverified"}
    for case in CASES.values():
        assert case["kind"] and set(case["kind"]) <= {"ANSWER", "CLARIFICATION", "OUT_OF_SCOPE"}
        for identity in case["cite"]:
            assert identity.split("@")[0] in {i for i, _ in case["items"]}


QWEN = "hf.co/mradermacher/Qwen3-4B-Element8-Eva-Hermes-Heretic-GGUF:Q4_K_M"


@pytest.mark.parametrize("model,adapted", [("gemma3:4b", True), (QWEN, False)])
def test_production_prompt_adaptation_per_model(tmp_path, model, adapted):
    """G294-F05 (fact, not a defect by itself): production applies the G286 grounding examples
    and best-last ordering to gemma3 only. G293 measured Qwen WITH --grounding (bench-only), so
    its 57/62 is not the configuration a Qwen profile would get in Core today."""
    from eidolon_core import gemma_dialogue
    case = CASES["homonym"]
    factory, seen = canned_model({case["question"]: ("answer", "0.22.3 [hermes-agent@1]")}, model=model)
    holdout.run_case(case, factory, tmp_path)
    content = "\n".join(m["content"] for m in seen[0]["messages"])
    assert (gemma_dialogue.EXAMPLES in content) is adapted
    first, second = content.find("hermes-agent"), content.find("hermes-sac")
    assert (second < first) is adapted          # best-ranked note last only for gemma3
