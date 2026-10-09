# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : make_examples.py
# Description : Régénère les exemples contractuels conversation/1, sans horloge ni aléa (C-TASK-G084)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/examples/conversation/make_examples.py

Synthetic identifiers and the demo target catalogue only; tests/test_conversation.py checks
that these files still validate and that the proposal reply is reproduced exactly."""
import json
from pathlib import Path

from eidolon_core import conversation as cv
from eidolon_core.contracts import digest
from eidolon_core.diagnostics import demo_catalog

HERE = Path(__file__).resolve().parent
STORE, CONV = "s-" + "1" * 32, "c-" + "2" * 32
CATALOG = demo_catalog()


def turn(sequence, text, previous=None):
    return {"protocol": cv.TURN_PROTOCOL, "store_id": STORE, "conversation_id": CONV,
            "turn_id": "t-" + format(sequence, "032x"), "sequence": sequence, "role": "user", "text": text,
            "client_id": "pc-exemple", "client_turn_key": f"tour-{sequence}",
            "previous_turn_sha256": digest(previous) if previous else None}


def model(kind, text, template=None, target=None):
    return {"version": 1, "kind": kind, "text": text,
            "proposal": {"template": template, "parameters": {"target_reference": target}} if template else None}


def main():
    first = turn(1, "Peux-tu vérifier l'état du NAS ?")
    output = model("proposal", "Je peux lancer un diagnostic en lecture seule du NAS.", cv.DIAGNOSTIC, "nas")
    reply = cv.decide_reply(first, json.dumps(output), CATALOG)
    second = turn(2, "Et le service ?", first)
    clarification = cv.decide_reply(second, json.dumps(model("proposal", "Je diagnostique le service.",
                                                                  cv.DIAGNOSTIC, "service")), CATALOG)
    third = turn(3, "Redémarre le NAS.", second)
    refused = cv.decide_reply(third, json.dumps(model("proposal", "Je redémarre le NAS.",
                                                           "service_restart.simulated", "nas")), CATALOG)
    proposal = reply["proposal"]
    submission = {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": STORE, "client_id": "pc-exemple",
                  "command_key": "soumission-1", "conversation_id": CONV, "proposal_id": proposal["proposal_id"],
                  "proposal_version": proposal["version"], "proposal_sha256": reply["proposal_sha256"],
                  "actor": "toytoy", "reason": "Diagnostic demandé dans la conversation."}
    mission = {"id": "m-" + "4" * 32, "request": proposal["request"],
               "objective": {"kind": cv.DIAGNOSTIC, "request_sha256": digest(proposal["request"]),
                             "target_id": proposal["target_id"]}}
    link = cv.make_link(submission, proposal, mission)
    files = {"01-turn.json": first, "02-model-output.json": output, "03-reply-proposal.json": reply,
             "04-reply-clarification.json": clarification, "05-reply-out-of-scope.json": refused,
             "06-submission.json": submission, "07-link.json": link}
    for name, value in files.items():
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(name)


if __name__ == "__main__":
    main()
