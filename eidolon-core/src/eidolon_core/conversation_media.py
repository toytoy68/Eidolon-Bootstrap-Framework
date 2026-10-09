# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_media.py
# Description : Contrat conversation ↔ agents Image/Vidéo : proposition figée, référence opaque, accord lié (C-TASK-G094)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Boundary contract only: nothing here uploads, runs an engine or reads a file.

Codex owns media_*.py (requests, artifact store, engines); this module owns the conversation side:
a media proposal is frozen by Core from a model suggestion, may only name an artifact that Core has
ATTACHED to this owner and conversation (an opaque media-artifact-ref/1, never a path), and is turned
into a media request only after a human submission naming its exact digest. Media states never become
SUCCEEDED: an engine or queue receipt is not an achieved objective.
"""
import re

from . import conversation as cv
from .contracts import ContractError, digest, snapshot
from .media_agents import MediaError, prepare
from .media_artifacts import validate_reference

PROPOSAL_PROTOCOL = "eidolon-media-proposal/1"
ATTACHMENT_PROTOCOL = "eidolon-conversation-attachment/1"
TEMPLATE = re.compile(r"media\.(image|video)\.(create|edit|analyze)")
PARAMETERS = {"prompt", "artifact_id", "format", "duration_seconds"}
# Media job state → what the conversation may show. No state maps to a success of the objective.
STAGES = {"LOCAL_DRAFT": "draft", "INTENT": "created", "QUEUED": "running",
          "ENGINE_COMPLETED_UNVERIFIED": "result_unverified", "OUTPUTS_IMPORTED_UNVERIFIED": "result_unverified",
          "RESULT_UNVERIFIED": "result_unverified", "REVIEW_REQUIRED": "unknown_effect",
          "COLLECTION_INCOMPLETE": "unknown_effect"}


def templates():
    return [f"media.{agent}.{op}" for agent in ("image", "video") for op in ("create", "edit", "analyze")]


def attachment(*, store_id, owner_client_id, conversation_id, reference):
    """Recorded by Core when an operator or an authenticated upload attaches an artifact (never the browser)."""
    try:
        reference = validate_reference(reference)
    except MediaError:
        raise ContractError("INVALID_MEDIA: invalid artifact reference") from None
    value = {"protocol": ATTACHMENT_PROTOCOL, "store_id": store_id, "owner_client_id": owner_client_id,
             "conversation_id": conversation_id, "reference": reference}
    return validate_attachment(value)


def validate_attachment(value):
    value = snapshot(value)
    if (not isinstance(value, dict) or set(value) != {"protocol", "store_id", "owner_client_id", "conversation_id",
                                                       "reference"} or value["protocol"] != ATTACHMENT_PROTOCOL):
        raise ContractError("INVALID_MEDIA: exact attachment fields required")
    cv._id(value["store_id"], "s", "store_id")
    cv._id(value["conversation_id"], "c", "conversation_id")
    if not isinstance(value["owner_client_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}",
                                                                      value["owner_client_id"]):
        raise ContractError("INVALID_MEDIA: invalid owner")
    try:
        validate_reference(value["reference"])
    except MediaError:
        raise ContractError("INVALID_MEDIA: invalid artifact reference") from None
    return value


def freeze(turn, suggestion, attachments, *, owner_client_id, previous=None):
    """Core's media proposal from a model suggestion {"template", "parameters"}; or a clarification code.

    Returns ("PROPOSAL", proposal) or ("CLARIFICATION" | "OUT_OF_SCOPE", code). The artifact comes from
    Core's attachment record for this owner and conversation, never from the suggestion itself.
    """
    turn = cv.validate_turn(turn)
    if not isinstance(suggestion, dict) or set(suggestion) != {"template", "parameters"}:
        return "OUT_OF_SCOPE", "MEDIA_TEMPLATE_UNSUPPORTED"
    match = TEMPLATE.fullmatch(suggestion["template"]) if isinstance(suggestion["template"], str) else None
    parameters = suggestion["parameters"]
    if match is None:
        return "OUT_OF_SCOPE", "MEDIA_TEMPLATE_UNSUPPORTED"
    if not isinstance(parameters, dict) or set(parameters) - PARAMETERS or "prompt" not in parameters:
        return "CLARIFICATION", "MEDIA_PARAMETERS_INVALID"     # a "source" path is never a parameter
    agent, operation = match.groups()
    artifact = None
    if operation != "create":
        wanted = parameters.get("artifact_id")
        mine = [validate_attachment(a) for a in attachments]
        found = [a["reference"] for a in mine if a["reference"]["artifact_id"] == wanted
                 and a["owner_client_id"] == owner_client_id and a["conversation_id"] == turn["conversation_id"]
                 and a["store_id"] == turn["store_id"]]
        if not found:
            return "CLARIFICATION", "MEDIA_ARTIFACT_NOT_ATTACHED"
        artifact = found[0]
    elif "artifact_id" in parameters:
        return "CLARIFICATION", "MEDIA_PARAMETERS_INVALID"
    request = {"agent": agent, "operation": operation, "prompt": parameters["prompt"]}
    if artifact is not None:
        request["artifact"] = artifact
    for key in ("format", "duration_seconds"):
        if key in parameters:
            request[key] = parameters[key]
    try:
        prepared = prepare(request)                          # Codex's own validation of the request
    except MediaError:
        return "CLARIFICATION", "MEDIA_PARAMETERS_INVALID"
    if previous is not None:
        previous = validate_proposal(previous)
    body = {"protocol": PROPOSAL_PROTOCOL, "store_id": turn["store_id"], "conversation_id": turn["conversation_id"],
            "proposal_id": previous["proposal_id"] if previous else "p-" + digest(["media", turn])[:32],
            "version": previous["version"] + 1 if previous else 1,
            "supersedes_sha256": digest(previous) if previous else None,
            "source_turn_id": turn["turn_id"], "source_turn_sha256": digest(turn), "owner_client_id": owner_client_id,
            "agent": prepared["agent"], "operation": prepared["operation"], "prompt": prepared["prompt"],
            "artifact": prepared.get("artifact"), "format": prepared["format"],
            "duration_seconds": prepared["duration_seconds"], "executor": "eidolon-media",
            "requires_human_submission": True, "authorizes_execution": False,
            "success_claim": "NEVER_FROM_ENGINE_OR_QUEUE_STATE"}
    return "PROPOSAL", validate_proposal(body)


def validate_proposal(value):
    value = snapshot(value)
    fields = {"protocol", "store_id", "conversation_id", "proposal_id", "version", "supersedes_sha256",
              "source_turn_id", "source_turn_sha256", "owner_client_id", "agent", "operation", "prompt", "artifact",
              "format", "duration_seconds", "executor", "requires_human_submission", "authorizes_execution",
              "success_claim"}
    if not isinstance(value, dict) or set(value) != fields or value["protocol"] != PROPOSAL_PROTOCOL:
        raise ContractError("INVALID_MEDIA: exact media proposal fields required")
    cv._id(value["store_id"], "s", "store_id")
    cv._id(value["conversation_id"], "c", "conversation_id")
    cv._id(value["proposal_id"], "p", "proposal_id")
    cv._version(value["version"], "proposal version")
    if (value["version"] == 1) != (value["supersedes_sha256"] is None):
        raise ContractError("INVALID_MEDIA: only version 1 supersedes nothing")
    if (value["executor"] != "eidolon-media" or value["requires_human_submission"] is not True
            or value["authorizes_execution"] is not False or value["success_claim"] != "NEVER_FROM_ENGINE_OR_QUEUE_STATE"):
        raise ContractError("INVALID_MEDIA: a media proposal never authorizes execution or claims success")
    request = media_request(value, _validated=True)
    if (value["operation"] == "create") != (value["artifact"] is None):
        raise ContractError("INVALID_MEDIA: an artifact is required for edit/analyze only")
    if prepare(request)["prompt"] != value["prompt"]:          # the frozen text is Codex's normalized text
        raise ContractError("INVALID_MEDIA: prompt is not normalized")
    return value


def media_request(proposal, *, _validated=False):
    """The request handed to Codex's media agents after submission: an opaque artifact, never a path."""
    if not _validated:
        proposal = validate_proposal(proposal)
    request = {"agent": proposal["agent"], "operation": proposal["operation"], "prompt": proposal["prompt"]}
    if proposal["artifact"] is not None:
        request["artifact"] = proposal["artifact"]
    if proposal["format"] is not None:
        request["format"] = proposal["format"]
    if proposal["duration_seconds"] is not None:
        request["duration_seconds"] = proposal["duration_seconds"]
    try:
        prepared = prepare(request)
    except MediaError as exc:
        raise ContractError("INVALID_MEDIA: " + str(exc)) from None
    if prepared.get("source") is not None:
        raise ContractError("INVALID_MEDIA: a source path is never part of a conversation request")
    return request


def check_submission(submission, current):
    """Same human submission contract as missions (G084), bound to the latest unchanged media proposal."""
    submission = cv.validate_submission(submission)
    if current is None:
        raise ContractError("PROPOSAL_UNKNOWN: no media proposal to submit")
    current = validate_proposal(current)
    if (submission["store_id"] != current["store_id"] or submission["conversation_id"] != current["conversation_id"]
            or submission["proposal_id"] != current["proposal_id"]):
        raise ContractError("PROPOSAL_UNKNOWN: submission names another proposal")
    if submission["client_id"] != current["owner_client_id"]:
        raise ContractError("CLIENT_MISMATCH: only the owner may submit this media proposal")
    if submission["proposal_version"] != current["version"]:
        raise ContractError("PROPOSAL_STALE: a newer media proposal exists; review it")
    if submission["proposal_sha256"] != digest(current):
        raise ContractError("PROPOSAL_CHANGED: reviewed media proposal differs from the recorded one")
    return submission


def stage(state):
    """Conversation stage of a media job state; unknown states are shown as received, never as success."""
    return STAGES.get(state)
