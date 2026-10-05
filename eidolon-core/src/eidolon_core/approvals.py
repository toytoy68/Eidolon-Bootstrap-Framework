# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : approvals.py
# Description : Décision locale liée à une action et une tentative précises
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Durable approval contracts; actor labels are audit text, not authentication."""
from .contracts import ContractError, digest, snapshot
from .simulation import timestamp


def action_binding(mission, call):
    return {"version": 1, "mission_id": mission["id"], "call_id": call["id"],
            "attempt": call["attempt"], "step": snapshot(call["step"]),
            "configuration_sha256": digest(mission["configuration"]),
            "objective_sha256": digest(mission["objective"]),
            "plan_sha256": digest(mission["plan"]), "context_sha256": digest(mission["context"]),
            "condition": snapshot(mission["action_condition"]),
            "observation_sha256": digest(mission["action_observation"])}


def check_proposal(mission, call):
    proposal = mission.get("proposal")
    expected = action_binding(mission, call)
    if (not isinstance(proposal, dict) or proposal.get("action") != expected
            or proposal.get("sha256") != digest(expected)):
        raise ContractError("APPROVAL_BINDING_CHANGED: action, condition or configuration changed")
    return proposal


def prepare(mission, call):
    proposal = mission.get("proposal")
    if proposal and proposal["action"]["attempt"] != call["attempt"]:
        mission.setdefault("proposal_history", []).append(snapshot(proposal))
        proposal = None
    if proposal is None:
        action = action_binding(mission, call)
        proposal = {"action": action, "sha256": digest(action), "status": "PENDING",
                    "created_at": timestamp(), "decisions": [], "consumed_at": None}
        mission["proposal"] = proposal
    return check_proposal(mission, call)


def decide(mission, call, *, expected_sha256, decision, actor, reason):
    proposal = check_proposal(mission, call)
    if (not isinstance(expected_sha256, str) or proposal["sha256"] != expected_sha256):
        raise ContractError("decision must name the exact proposal sha256")
    if any(not isinstance(v, str) or not v.strip() or len(v) > bound
           for v, bound in ((actor, 200), (reason, 4000))):
        raise ContractError("explicit bounded actor and reason required")
    allowed = {"approve": ("PENDING", "APPROVED"), "reject": ("PENDING", "REJECTED"),
               "revoke": ("APPROVED", "REVOKED")}
    if decision not in allowed or proposal["status"] != allowed[decision][0]:
        raise ContractError("decision is not valid for the current proposal status")
    entry = snapshot({"decision": decision, "actor": actor, "reason": reason,
                      "at": timestamp(), "proposal_sha256": expected_sha256})
    proposal["decisions"].append(entry)
    proposal["status"] = allowed[decision][1]
    return entry


def consume(mission, call):
    proposal = check_proposal(mission, call)
    if proposal["status"] != "APPROVED":
        raise ContractError("approved proposal required before tool authorization")
    proposal.update(status="USED", consumed_at=timestamp())
    call["approval_sha256"] = proposal["sha256"]
    # The caller must persist this WITH CALL_STARTED, never as a separate commit.


def consumed(mission, call):
    try:
        proposal = check_proposal(mission, call)
        return (proposal["status"] == "USED" and isinstance(proposal["consumed_at"], str)
                and bool(proposal["consumed_at"]) and bool(proposal["decisions"])
                and proposal["decisions"][-1]["decision"] == "approve"
                and proposal["decisions"][-1]["proposal_sha256"] == proposal["sha256"]
                and call.get("approval_sha256") == proposal["sha256"])
    except (ContractError, KeyError, TypeError):
        return False
