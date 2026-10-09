# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_cancel.py
# Description : Annulation ciblée depuis la conversation : proposition figée, soumission humaine, demande ≠ effet (C-TASK-G100)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""A cancellation asked in the conversation is a PROPOSAL naming one exact mission, never an action.

- Only missions created from this client's own submissions in this conversation can be named.
- Core freezes {mission_id, request digest, link digest}; the human submits that exact digest.
- The existing CancelCommands records a stop REQUEST (flag + audit + receipt). That is "request
  received", never "cancelled": the effect is observed only when the mission itself reaches CANCELLED.
- Media engine jobs are NOT cancellable from here: no per-job contract is safe yet, and a global engine
  interrupt (e.g. ComfyUI /interrupt) would stop other people's work. That case is NOT_AVAILABLE.
"""
from .commands import CancelCommands
from .contracts import ContractError, digest
from .store import TERMINAL

PROPOSAL_PROTOCOL = "eidolon-cancel-proposal/1"
# Stage of a cancellation as the conversation may show it. None of them is a claim the work stopped
# unless the mission itself says CANCELLED.
STAGES = ("request_received", "effect_observed", "finished_without_cancellation", "already_finished",
          "uncertain")


def candidates(conversations, store, *, client_id, conversation_id):
    """Active missions this client created from this conversation, oldest first."""
    found = []
    for mission_id in conversations.missions_of(client_id, conversation_id):
        mission = store.get(mission_id)
        if mission["status"] not in TERMINAL:
            found.append({"mission_id": mission_id, "status": mission["status"], "request": mission["request"]})
    return found


def _proposal(conversations, store, *, client_id, conversation_id, mission_id):
    linked = conversations.missions_of(client_id, conversation_id)
    if not isinstance(mission_id, str) or mission_id not in linked:
        raise ContractError("MISSION_UNKNOWN: not a mission created from this conversation by this client")
    mission = store.get(mission_id)
    link = linked[mission_id]
    if link["mission_request_sha256"] != digest(mission["request"]):
        raise ContractError("LINK_INVALID: the mission no longer matches its conversation link")
    # Stable fields only: the digest does not change while the mission runs (its revision does).
    return {"protocol": PROPOSAL_PROTOCOL, "store_id": conversations.store_id, "conversation_id": conversation_id,
            "client_id": client_id, "mission_id": mission_id, "mission_request_sha256": link["mission_request_sha256"],
            "link_sha256": digest(link), "action": "REQUEST_MISSION_STOP", "engine_interrupt": "NEVER",
            "requires_human_submission": True, "authorizes_execution": False,
            "success_claim": "ONLY_FROM_MISSION_STATUS_CANCELLED"}, mission


def propose(conversations, store, *, client_id, conversation_id, mission_id=None, target="mission"):
    """("PROPOSAL", proposal, sha, status) | ("CLARIFICATION", code, candidates) | ("REFUSED"/"NOT_AVAILABLE", code)."""
    if target == "media_job":
        return ("NOT_AVAILABLE", "MEDIA_CANCEL_NOT_AVAILABLE")    # never a global engine interrupt
    if target != "mission":
        return ("REFUSED", "CANCEL_TARGET_UNSUPPORTED")
    if mission_id is None:
        active = candidates(conversations, store, client_id=client_id, conversation_id=conversation_id)
        if not active:
            return ("CLARIFICATION", "NO_ACTIVE_MISSION", [])
        if len(active) > 1:
            return ("CLARIFICATION", "MISSION_AMBIGUOUS", [a["mission_id"] for a in active])
        mission_id = active[0]["mission_id"]
    proposal, mission = _proposal(conversations, store, client_id=client_id, conversation_id=conversation_id,
                                  mission_id=mission_id)
    if mission["status"] in TERMINAL:
        return ("REFUSED", "MISSION_ALREADY_FINISHED", mission["status"])
    return ("PROPOSAL", proposal, digest(proposal), mission["status"])


def submit(conversations, store, *, client, conversation_id, mission_id, proposal_sha256, command_key, reason):
    """Human submission of the exact frozen cancellation proposal; records a stop REQUEST only."""
    proposal, _ = _proposal(conversations, store, client_id=client["client_id"], conversation_id=conversation_id,
                            mission_id=mission_id)
    if proposal_sha256 != digest(proposal):
        raise ContractError("PROPOSAL_CHANGED: reviewed cancellation proposal differs from Core's")
    receipt = CancelCommands(store).submit({
        "protocol": "eidolon-cancel-command/1", "store_id": conversations.store_id,
        "client_id": client["client_id"], "command_key": command_key, "mission_id": mission_id,
        "actor": client["actor"], "reason": reason})
    return receipt


def view(receipt, mission):
    """What the conversation may say about a cancellation, from the receipt and the mission NOW."""
    if receipt is None:
        return "uncertain"                       # response lost: look the receipt up, never resend blindly
    if receipt["cancel_outcome"] == "ALREADY_TERMINAL":
        return "already_finished"
    status = mission["status"]
    if status == "CANCELLED":
        return "effect_observed"
    if status == "ABANDONED":
        return "uncertain"
    if status in TERMINAL:
        return "finished_without_cancellation"  # the result arrived first; it is kept, not hidden
    return "request_received"
