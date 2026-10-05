# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : objectives.py
# Description : Objectifs et couverture vérifiée indépendants du modèle
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""A deliberately narrow mission catalogue, never selected by model output.

Coverage is over the retained recall snapshot, not the whole memory corpus.
Trusted tool verifiers attest results; this module checks their mission coverage.
"""
from .contracts import ContractError, digest, reference
from .memory import DEMO_REQUEST


def define(request):
    supported = request == DEMO_REQUEST
    return {"version": 1, "kind": "recalled_text_statistics" if supported else None,
            "request_sha256": digest(request), "scope": "recalled_snapshot",
            "tool": "text.stats" if supported else None,
            "required_references": None, "context_sha256": None}


def bind(objective, context):
    return {**objective, "required_references": sorted(reference(i) for i in context["items"]),
            "context_sha256": digest(context)}


def check_contract(mission):
    expected = define(mission["request"])
    if mission["context"] is not None:
        expected = bind(expected, mission["context"])
    if mission.get("objective") != expected:
        raise ContractError("MISSION_CONTRACT_INVALID: objective or recall binding changed")
    return expected


def check_plan(mission):
    objective = check_contract(mission)
    required = objective["required_references"]
    if objective["kind"] is None or not required:
        raise ContractError("MISSION_NO_CRITERIA: no supported objective with evidence")
    references = []
    for step in mission["plan"]["steps"]:
        if step["tool"] != objective["tool"] or set(step["parameters"]) != {"reference"}:
            raise ContractError("MISSION_PLAN_MISMATCH: step does not serve the objective")
        references.append(step["parameters"]["reference"])
    if len(references) != len(set(references)):
        raise ContractError("MISSION_DUPLICATE_REFERENCE: a repeated source is not additional coverage")
    if sorted(references) != required:
        raise ContractError("MISSION_INCOMPLETE_PLAN: cover every reference in the retained recall")


def assess(mission):
    """Recomputed when persisted; a proposed plan or outcome is not evidence."""
    outcome = {"status": "PENDING", "scope": "recalled_snapshot",
               "covered_references": [], "missing_references": [], "code": "AWAITING_EVIDENCE"}
    try:
        objective = check_contract(mission)
    except ContractError:
        return {**outcome, "status": "CLARIFICATION", "code": "MISSION_CONTRACT_REQUIRED"}
    if objective["kind"] is None:
        return {**outcome, "status": "CLARIFICATION", "code": "MISSION_UNSUPPORTED"}
    required = objective["required_references"]
    if required is None:
        state = "PENDING" if mission["status"] in {"NEW", "RUNNING"} else "NO_EVIDENCE"
        return {**outcome, "status": state}
    if not required:
        return {**outcome, "status": "NO_EVIDENCE", "code": "MEMORY_EMPTY"}
    covered = set()
    valid_plan = True
    try:
        check_plan(mission)
    except (ContractError, TypeError, KeyError):
        valid_plan = False
    steps = (mission.get("plan") or {}).get("steps", [])
    for index, call in enumerate(mission["calls"]):
        step = call["step"]
        if (call["status"] == "VERIFIED" and index < len(steps) and step == steps[index]
                and step["tool"] == objective["tool"]
                and call.get("context_sha256") == objective["context_sha256"]
                and call.get("output_sha256") == digest(call.get("output"))
                and step["parameters"].get("reference") in required):
            covered.add(step["parameters"]["reference"])
    missing = sorted(set(required) - covered)
    achieved = bool(covered) and not missing and valid_plan and len(mission["calls"]) == len(required)
    state = "ACHIEVED" if achieved else ("PARTIAL" if covered else "NOT_ACHIEVED")
    code = "COVERAGE_VERIFIED" if achieved else ("INCOMPLETE_EVIDENCE" if covered else "NO_VERIFIED_RESULT")
    return {**outcome, "status": state, "code": code,
            "covered_references": sorted(covered), "missing_references": missing}
