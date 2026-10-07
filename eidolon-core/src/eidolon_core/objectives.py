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
from .targets import Catalog

DIAGNOSTIC = "service_diagnostic.synthetic"
RESTART = "service_restart.simulated"
TARGETED = {DIAGNOSTIC, RESTART}
RESEARCH = "research_retrieval.synthetic"
RESEARCH_TOOL = "research.retrieve.synthetic"


def restart_request(target):
    return "Simuler le redémarrage du service : " + target


def restart_parameters(mission):
    condition = mission["action_condition"]
    return {"target": mission["objective"]["target_id"], "expected_revision": condition["revision"],
            "world_id": condition["world_id"], "operation_id": mission["id"]}


def diagnostic_request(target):
    return "Diagnostiquer le service synthétique : " + target


def define(request, intent=None, configuration=None):
    if type(intent) is dict and intent.get("kind") == RESEARCH:
        from .query_cleanup import clean_query
        if (set(intent) != {"kind", "query", "required_pages"}
                or type(intent["query"]) is not str
                or type(intent["required_pages"]) is not int or not 1 <= intent["required_pages"] <= 2
                or request != "Rechercher des pages synthétiques : " + intent["query"]):
            raise ContractError("INVALID_RESEARCH_MISSION")
        clean_query(intent["query"])
        return {"version": 1, "kind": RESEARCH, "scope": "synthetic_retrieved_text",
                "request_sha256": digest(request), "tool": RESEARCH_TOOL,
                "query": intent["query"], "required_pages": intent["required_pages"],
                "required_references": [], "context_sha256": None}
    if intent is not None:
        if (not isinstance(intent, dict) or set(intent) != {"kind", "target_reference"}
                or intent["kind"] not in TARGETED or not isinstance(intent["target_reference"], str)
                or request != (diagnostic_request if intent["kind"] == DIAGNOSTIC else restart_request)(intent["target_reference"])):
            raise ContractError("invalid explicit mission intent")
        catalog = Catalog.from_config((configuration or {}).get("targets"))
        restart = intent["kind"] == RESTART
        capability = "service.restart.simulated" if restart else "service.observe"
        selected = catalog.lookup(intent["target_reference"], capability)
        return {"version": 1, "kind": intent["kind"], "scope": "synthetic_action" if restart else "synthetic_service",
                "request_sha256": digest(request), "tool": capability if restart else "service.observe.synthetic",
                "required_references": [], "context_sha256": None,
                "selection_status": selected.status, "candidates": list(selected.candidates),
                "target_id": selected.target.id if selected.target else None,
                "capability": capability, "catalog_sha256": catalog.fingerprint()}
    supported = request == DEMO_REQUEST
    return {"version": 1, "kind": "recalled_text_statistics" if supported else None,
            "request_sha256": digest(request), "scope": "recalled_snapshot",
            "tool": "text.stats" if supported else None,
            "required_references": None, "context_sha256": None}


def bind(objective, context):
    return {**objective, "required_references": ([] if objective["kind"] in TARGETED | {RESEARCH} else
                                                sorted(reference(i) for i in context["items"])),
            "context_sha256": digest(context)}


def check_contract(mission):
    expected = define(mission["request"], mission.get("intent"), mission["configuration"])
    if mission["context"] is not None:
        expected = bind(expected, mission["context"])
    if mission.get("objective") != expected:
        raise ContractError("MISSION_CONTRACT_INVALID: objective or recall binding changed")
    return expected


def check_plan(mission):
    objective = check_contract(mission)
    required = objective["required_references"]
    if objective["kind"] == RESEARCH:
        steps = mission["plan"]["steps"]
        if (len(steps) != 1 or steps[0]["tool"] != RESEARCH_TOOL
                or steps[0]["parameters"] != {"query": objective["query"], "required_pages": objective["required_pages"], "operation_id": mission["id"]}):
            raise ContractError("MISSION_PLAN_MISMATCH: exactly the explicit synthetic research request is required")
        return
    if objective["kind"] in TARGETED:
        steps = mission["plan"]["steps"]
        if (objective["selection_status"] != "FOUND" or len(steps) != 1
                or steps[0]["tool"] != objective["tool"]
                or steps[0]["parameters"] != (restart_parameters(mission) if objective["kind"] == RESTART else
                                            {"target": objective["target_id"]})):
            raise ContractError("MISSION_PLAN_MISMATCH: step must serve exactly the selected target and typed objective")
        return
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
    if objective["kind"] == RESEARCH:
        return assess_research(mission, objective)
    if objective["kind"] in TARGETED:
        return assess_diagnostic(mission, objective)
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


def assess_diagnostic(mission, objective):
    outcome = {"status": "NOT_ACHIEVED", "scope": objective["scope"],
               "covered_references": [], "missing_references": [],
               "target_id": objective["target_id"], "code": "NO_VERIFIED_OBSERVATION"}
    if objective["selection_status"] != "FOUND":
        return {**outcome, "status": "CLARIFICATION", "code": objective["selection_status"],
                "candidates": objective["candidates"]}
    try:
        check_plan(mission)
    except (ContractError, TypeError, KeyError):
        return outcome
    calls = mission["calls"]
    if len(calls) == 1:
        call = calls[0]
        if (call["status"] == "VERIFIED" and call["step"] == mission["plan"]["steps"][0]
                and call.get("context_sha256") == objective["context_sha256"]
                and call.get("output_sha256") == digest(call.get("output"))
                and call.get("target_binding") == {"target_id": objective["target_id"],
                    "capability": objective["capability"], "catalog_sha256": objective["catalog_sha256"]}):
            if objective["kind"] == RESTART:
                from .approvals import consumed
                if not consumed(mission, call):
                    return {**outcome, "code": "APPROVAL_NOT_CONSUMED"}
            return {**outcome, "status": "ACHIEVED", "code": (
                "SIMULATED_ACTION_VERIFIED" if objective["kind"] == RESTART else "OBSERVATION_VERIFIED")}
    return outcome


def assess_research(mission, objective):
    """Coverage is retrieved synthetic pages, never the truth of their content."""
    outcome = {"status": "NOT_ACHIEVED", "scope": objective["scope"],
               "covered_references": [], "missing_references": [], "code": "NO_VERIFIED_RETRIEVAL"}
    try:
        check_plan(mission)
    except (ContractError, TypeError, KeyError):
        return outcome
    calls = mission["calls"]
    if len(calls) != 1:
        return outcome
    call = calls[0]
    output = call.get("output")
    if (call["status"] != "VERIFIED" or call["step"] != mission["plan"]["steps"][0]
            or call.get("context_sha256") != objective["context_sha256"]
            or type(output) is not dict or call.get("output_sha256") != digest(output)):
        return outcome
    count = output.get("readable_pages")
    if type(count) is not int or not 0 <= count <= 2:
        return outcome
    achieved = count >= objective["required_pages"] and output.get("status") == "READ_TARGET_MET"
    return {**outcome, "status": "ACHIEVED" if achieved else "PARTIAL" if count else "NOT_ACHIEVED",
            "code": "SYNTHETIC_RETRIEVAL_VERIFIED" if achieved else "RETRIEVAL_TARGET_NOT_MET",
            "readable_pages": count, "required_pages": objective["required_pages"]}
