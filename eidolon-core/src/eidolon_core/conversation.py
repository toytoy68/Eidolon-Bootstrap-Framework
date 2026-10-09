# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation.py
# Description : Contrat conversation/1 : tours, réponses, proposition figée, soumission et liens mission (C-TASK-G084)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Pure contract, no storage and no I/O (persistence is G085, the API G087).

Model text is data: it is shown, never executed and never an authorization. Only Core turns a
model "proposal" into a frozen mission proposal, from a catalogue the model cannot change, and
only a separate human submission naming the exact frozen digest may ever lead to a mission.
"""
import json
import re

from .commands import validate_scope
from .contracts import ContractError, digest, snapshot
from .objectives import DIAGNOSTIC, diagnostic_request
from .store import Store

PROTOCOL = "eidolon-conversation/1"
TURN_PROTOCOL = "eidolon-conversation-turn/1"
OUTPUT_VERSION = 1
REPLY_PROTOCOL = "eidolon-conversation-reply/1"
PROPOSAL_PROTOCOL = "eidolon-mission-proposal/1"
SUBMISSION_PROTOCOL = "eidolon-proposal-submission/1"
LINK_PROTOCOL = "eidolon-conversation-link/1"

MAX_TURN_TEXT = 8000
MAX_REPLY_TEXT = 4000
MAX_OUTPUT_BYTES = 16384
MAX_OUTPUT_DEPTH = 4
MAX_SOURCES = 5

TURN_FIELDS = {"protocol", "store_id", "conversation_id", "turn_id", "sequence", "role", "text",
               "client_id", "client_turn_key", "previous_turn_sha256"}
SUBMISSION_FIELDS = {"protocol", "store_id", "client_id", "command_key", "conversation_id", "proposal_id",
                     "proposal_version", "proposal_sha256", "actor", "reason"}
OUTPUT_KINDS = ("answer", "clarification", "proposal", "out_of_scope")

# The only missions a conversation may propose (MVP: one, read-only). Never chosen by the model:
# the model may only name a template; Core checks it here and derives the mission request itself.
TEMPLATES = {
    DIAGNOSTIC: {"parameters": ("target_reference",), "capability": "service.observe",
                 "label": "Diagnostic synthétique d'un service (lecture seule)"},
}


def _id(value, prefix, name):
    if not isinstance(value, str) or re.fullmatch(prefix + r"-[0-9a-f]{32}", value) is None:
        raise ContractError("INVALID_CONVERSATION: invalid " + name)
    return value


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError("INVALID_CONVERSATION: invalid " + name)
    return value


def _text(value, bound, name, code="INVALID_CONVERSATION"):
    if not isinstance(value, str) or not value.strip() or len(value) > bound:
        raise ContractError(f"{code}: {name} must hold 1..{bound} characters")
    return value


def _version(value, name):
    if type(value) is not int or not 1 <= value <= 2**31:
        raise ContractError("INVALID_CONVERSATION: invalid " + name)
    return value


def validate_turn(value):
    """A user turn as recorded by Core: ordered and chained to the previous turn digest."""
    value = snapshot(value)
    if not isinstance(value, dict) or set(value) != TURN_FIELDS or value["protocol"] != TURN_PROTOCOL:
        raise ContractError("INVALID_CONVERSATION: exact versioned turn fields required")
    validate_scope(value["store_id"], value["client_id"], value["client_turn_key"])
    _id(value["conversation_id"], "c", "conversation_id")
    _id(value["turn_id"], "t", "turn_id")
    _version(value["sequence"], "sequence")
    if value["role"] != "user":
        raise ContractError("INVALID_CONVERSATION: only user turns are recorded as turns")
    _text(value["text"], MAX_TURN_TEXT, "text")
    previous = value["previous_turn_sha256"]
    if (value["sequence"] == 1) != (previous is None):
        raise ContractError("INVALID_CONVERSATION: only the first turn has no previous digest")
    if previous is not None:
        _sha(previous, "previous_turn_sha256")
    return value


def check_turn_order(previous, turn):
    """The next turn must follow the previous one exactly (no gap, fork or replay)."""
    turn = validate_turn(turn)
    if previous is None:
        if turn["sequence"] != 1:
            raise ContractError("TURN_OUT_OF_ORDER: first turn must have sequence 1")
        return turn
    previous = validate_turn(previous)
    if (turn["conversation_id"] != previous["conversation_id"] or turn["store_id"] != previous["store_id"]
            or turn["sequence"] != previous["sequence"] + 1
            or turn["previous_turn_sha256"] != digest(previous)):
        raise ContractError("TURN_OUT_OF_ORDER: turn does not follow the recorded conversation")
    return turn


def same_request(existing, candidate, code):
    """Idempotency: an identical retry returns the recorded item, a changed one is refused."""
    if existing is None:
        return False
    if digest(existing) != digest(candidate):
        raise ContractError(code + ": key already bound to another request")
    return True


def parse_dialogue_output(raw):
    """Strict model output: {"version": 1, "kind", "text", "proposal"}. Success is not evidence."""
    if not isinstance(raw, str):
        raise ContractError("INVALID_MODEL_OUTPUT: bounded JSON text required")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError:
        raise ContractError("INVALID_MODEL_OUTPUT: UTF-8 text required") from None
    if size > MAX_OUTPUT_BYTES:
        raise ContractError("INVALID_MODEL_OUTPUT: output exceeds the size bound")
    depth, quoted, escaped = 0, False, False
    for char in raw:  # Structural depth only; brackets inside strings do not count.
        if quoted:
            escaped, quoted = (False, quoted) if escaped else (char == "\\", char != '"')
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_OUTPUT_DEPTH:
                raise ContractError("INVALID_MODEL_OUTPUT: nesting exceeds the bound")
        elif char in "]}":
            depth -= 1

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ContractError("INVALID_MODEL_OUTPUT: duplicate JSON key")
            result[key] = item
        return result

    def nonfinite(_):
        raise ContractError("INVALID_MODEL_OUTPUT: non-finite number")

    try:
        output = snapshot(json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite))
    except ContractError:
        raise
    except (ValueError, RecursionError):
        raise ContractError("INVALID_MODEL_OUTPUT: invalid JSON") from None
    if (not isinstance(output, dict) or set(output) != {"version", "kind", "text", "proposal"}
            or type(output["version"]) is not int or output["version"] != OUTPUT_VERSION
            or output["kind"] not in OUTPUT_KINDS):
        raise ContractError("INVALID_MODEL_OUTPUT: exact version, kind, text and proposal required")
    _text(output["text"], MAX_REPLY_TEXT, "model text", "INVALID_MODEL_OUTPUT")
    proposal = output["proposal"]
    if output["kind"] != "proposal":
        if proposal is not None:
            raise ContractError("INVALID_MODEL_OUTPUT: only a proposal carries a proposal")
    elif (not isinstance(proposal, dict) or set(proposal) != {"template", "parameters"}
          or not isinstance(proposal["template"], str) or not isinstance(proposal["parameters"], dict)):
        raise ContractError("INVALID_MODEL_OUTPUT: proposal needs template and parameters")
    return output


def capabilities():
    """What a conversation can propose, for out-of-scope explanations (never from the model)."""
    return [{"template": name, "label": spec["label"]} for name, spec in sorted(TEMPLATES.items())]


def _proposal(turn, template, parameters, selected, catalog, previous):
    if previous is not None:
        previous = validate_proposal(previous)
        if (previous["conversation_id"] != turn["conversation_id"] or previous["store_id"] != turn["store_id"]):
            raise ContractError("INVALID_CONVERSATION: previous proposal belongs to another conversation")
    body = {"protocol": PROPOSAL_PROTOCOL, "store_id": turn["store_id"],
            "conversation_id": turn["conversation_id"],
            "proposal_id": previous["proposal_id"] if previous else "p-" + digest(turn)[:32],
            "version": previous["version"] + 1 if previous else 1,
            "supersedes_sha256": proposal_sha256(previous) if previous else None,
            "source_turn_id": turn["turn_id"], "source_turn_sha256": digest(turn),
            "template": template, "target_reference": parameters["target_reference"],
            "target_id": selected.target.id, "catalog_sha256": catalog.fingerprint(),
            "request": diagnostic_request(parameters["target_reference"]),
            "requires_human_submission": True, "authorizes_execution": False}
    return validate_proposal(body)


def validate_proposal(value):
    value = snapshot(value)
    fields = {"protocol", "store_id", "conversation_id", "proposal_id", "version", "supersedes_sha256",
              "source_turn_id", "source_turn_sha256", "template", "target_reference", "target_id",
              "catalog_sha256", "request", "requires_human_submission", "authorizes_execution"}
    if not isinstance(value, dict) or set(value) != fields or value["protocol"] != PROPOSAL_PROTOCOL:
        raise ContractError("INVALID_PROPOSAL: exact versioned proposal fields required")
    _id(value["store_id"], "s", "store_id")
    _id(value["conversation_id"], "c", "conversation_id")
    _id(value["proposal_id"], "p", "proposal_id")
    _id(value["source_turn_id"], "t", "source_turn_id")
    _version(value["version"], "proposal version")
    _sha(value["source_turn_sha256"], "source_turn_sha256")
    _sha(value["catalog_sha256"], "catalog_sha256")
    if (value["version"] == 1) != (value["supersedes_sha256"] is None):
        raise ContractError("INVALID_PROPOSAL: only version 1 supersedes nothing")
    if value["supersedes_sha256"] is not None:
        _sha(value["supersedes_sha256"], "supersedes_sha256")
    if value["template"] not in TEMPLATES:
        raise ContractError("INVALID_PROPOSAL: unsupported template")
    for key in ("target_reference", "target_id"):
        _text(value[key], 200, key)
    # The mission request is derived by Core, never copied from the model text.
    if value["request"] != diagnostic_request(value["target_reference"]):
        raise ContractError("INVALID_PROPOSAL: request is not the Core-derived request")
    if value["requires_human_submission"] is not True or value["authorizes_execution"] is not False:
        raise ContractError("INVALID_PROPOSAL: a proposal never authorizes execution")
    return value


def proposal_sha256(proposal):
    return digest(validate_proposal(proposal))


CONTEXT_MEMORY = ("none", "sent", "dropped_for_budget", "unavailable")


def validate_context_note(context):
    """What the model actually received (G091): whole earlier turns sent/excluded and the memory state.

    Turns are never cut inside: a turn is sent whole or excluded whole, so a negation, a date or a
    unit is never silently removed from a message. Memory extracts may already be truncated by the
    memory engine; their count is reported, never hidden.
    """
    if context is None:
        return None
    keys = {"history_sent", "history_excluded", "memory", "memory_items", "memory_truncated_items",
            "observations_sent", "observations_excluded"}
    if (not isinstance(context, dict) or set(context) != keys or context["memory"] not in CONTEXT_MEMORY
            or any(type(context[k]) is not int or not 0 <= context[k] <= 100_000 for k in keys - {"memory"})
            or context["memory_truncated_items"] > context["memory_items"]
            or (context["memory"] != "sent" and context["memory_items"] != 0)):
        raise ContractError("INVALID_CONVERSATION: invalid context note")
    return dict(context, partial=context["history_excluded"] > 0 or context["memory"] in ("dropped_for_budget", "unavailable")
                or context["memory_truncated_items"] > 0 or context["observations_excluded"] > 0)


MEDIA_TEMPLATE = re.compile(r"media\.(image|video)\.(create|edit|analyze)")
PROFILE_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,39}")


def validate_model_identity(value):
    """G098: which dialogue profile and model produced (or were asked for) this reply. None if unknown.

    It names the model; it is not evidence that the model's text is true, and never chosen by the model.
    """
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"profile", "model_id"}
            or not (value["profile"] is None or (isinstance(value["profile"], str)
                                                 and PROFILE_NAME.fullmatch(value["profile"])))
            or not (value["model_id"] is None or (isinstance(value["model_id"], str)
                                                  and 1 <= len(value["model_id"]) <= 300))):
        raise ContractError("INVALID_CONVERSATION: invalid model identity")
    return dict(value)


# A reference written in the model's text, e.g. "note-v100@3": checked against the sources Core sent.
CITATION = re.compile(r"(?<![\w.@-])([A-Za-z0-9][A-Za-z0-9_.:-]{0,120}@[0-9]{1,9})(?![\w@])")


def citation_check(model_text, sources):
    """G096: which references the model claims, and which of them Core did NOT send (unsupported)."""
    claimed = sorted(set(CITATION.findall(model_text or "")))[:20]
    return {"claimed": claimed, "unsupported": [c for c in claimed if c not in sources]}


def decide_reply(turn, output, catalog, *, previous_proposal=None, sources=(), context=None, model=None, media=None):
    """Core's reply to one user turn. The model text is quoted; Core decides the kind."""
    turn = validate_turn(turn)
    context = validate_context_note(context)
    model = validate_model_identity(model)
    unusable = "MODEL_UNAVAILABLE" if output is None else None
    if output is not None:
        try:
            output = parse_dialogue_output(output)
        except ContractError:
            output, unusable = None, "MODEL_OUTPUT_INVALID"   # never guessed, never repaired
    sources = list(sources)
    if len(sources) > MAX_SOURCES or any(not isinstance(s, str) or not 1 <= len(s) <= 300 for s in sources):
        raise ContractError("INVALID_CONVERSATION: sources must be at most five bounded references")
    reply = {"protocol": REPLY_PROTOCOL, "store_id": turn["store_id"], "conversation_id": turn["conversation_id"],
             "in_reply_to": turn["turn_id"], "turn_sha256": digest(turn), "kind": None,
             "model_text": None, "core_note": None, "candidates": [], "sources": sorted(set(sources)),
             "context": context, "citations": None, "model": model,
             "proposal": None, "proposal_sha256": None,
             "model_text_is_evidence": False, "authorizes_execution": False}
    if output is None:
        return {**reply, "kind": "UNAVAILABLE", "core_note": unusable, "context": None}
    reply["model_text"] = output["text"]
    reply["citations"] = citation_check(output["text"], reply["sources"])
    if output["kind"] in ("answer", "clarification"):
        return {**reply, "kind": output["kind"].upper()}
    if output["kind"] == "out_of_scope":
        return {**reply, "kind": "OUT_OF_SCOPE", "core_note": "MODEL_DECLINED",
                "candidates": [c["template"] for c in capabilities()]}
    template, parameters = output["proposal"]["template"], output["proposal"]["parameters"]
    if media is not None and MEDIA_TEMPLATE.fullmatch(template):
        # G122: Core freezes the media proposal itself (conversation_media.freeze over ITS attachments).
        kind, value = media(turn, output["proposal"])
        if kind == "PROPOSAL":
            return {**reply, "kind": "PROPOSAL", "proposal": value, "proposal_sha256": digest(value)}
        return {**reply, "kind": kind, "core_note": value}
    spec = TEMPLATES.get(template)
    if spec is None:
        return {**reply, "kind": "OUT_OF_SCOPE", "core_note": "TEMPLATE_UNSUPPORTED",
                "candidates": [c["template"] for c in capabilities()]}
    if (set(parameters) != set(spec["parameters"])
            or any(not isinstance(parameters[k], str) or not 1 <= len(parameters[k]) <= 200 for k in parameters)):
        return {**reply, "kind": "CLARIFICATION", "core_note": "PARAMETERS_INVALID"}
    selected = catalog.lookup(parameters["target_reference"], spec["capability"])
    if selected.status == "TARGET_AMBIGUOUS":
        return {**reply, "kind": "CLARIFICATION", "core_note": "TARGET_AMBIGUOUS",
                "candidates": list(selected.candidates)}
    if selected.status == "TARGET_ABSENT":
        return {**reply, "kind": "CLARIFICATION", "core_note": "TARGET_ABSENT"}
    if selected.status != "FOUND":
        return {**reply, "kind": "OUT_OF_SCOPE", "core_note": selected.status}
    proposal = _proposal(turn, template, parameters, selected, catalog, previous_proposal)
    return {**reply, "kind": "PROPOSAL", "proposal": proposal, "proposal_sha256": proposal_sha256(proposal)}


def validate_submission(value):
    """The human act that may start a mission: it names the exact frozen proposal."""
    value = snapshot(value)
    if not isinstance(value, dict) or set(value) != SUBMISSION_FIELDS or value["protocol"] != SUBMISSION_PROTOCOL:
        raise ContractError("INVALID_SUBMISSION: exact versioned submission fields required")
    validate_scope(value["store_id"], value["client_id"], value["command_key"])
    _id(value["conversation_id"], "c", "conversation_id")
    _id(value["proposal_id"], "p", "proposal_id")
    _version(value["proposal_version"], "proposal_version")
    _sha(value["proposal_sha256"], "proposal_sha256")
    for name, bound in (("actor", 200), ("reason", 4000)):
        _text(value[name], bound, name)
    return value


def check_submission(submission, current):
    """Accept only the latest, unchanged proposal of this conversation and Store."""
    submission = validate_submission(submission)
    if current is None:
        raise ContractError("PROPOSAL_UNKNOWN: no proposal to submit")
    current = validate_proposal(current)
    if (submission["store_id"] != current["store_id"]
            or submission["conversation_id"] != current["conversation_id"]
            or submission["proposal_id"] != current["proposal_id"]):
        raise ContractError("PROPOSAL_UNKNOWN: submission names another proposal")
    if submission["proposal_version"] != current["version"]:
        raise ContractError("PROPOSAL_STALE: a newer proposal version exists; review it")
    if submission["proposal_sha256"] != proposal_sha256(current):
        raise ContractError("PROPOSAL_CHANGED: reviewed proposal differs from the recorded one")
    return submission


def mission_arguments(proposal):
    """What Core passes to Store.create: the derived request and explicit intent, nothing else."""
    proposal = validate_proposal(proposal)
    return proposal["request"], {"kind": proposal["template"], "target_reference": proposal["target_reference"]}


def make_link(submission, proposal, mission):
    submission = check_submission(submission, proposal)
    link = {"protocol": LINK_PROTOCOL, "store_id": proposal["store_id"],
            "conversation_id": proposal["conversation_id"], "proposal_id": proposal["proposal_id"],
            "proposal_version": proposal["version"], "proposal_sha256": proposal_sha256(proposal),
            "submission_sha256": digest(submission), "mission_id": mission["id"],
            "mission_request_sha256": digest(mission["request"])}
    return check_link(link, proposal, mission)


def check_link(link, proposal, mission):
    """A link is valid only if the mission really is the frozen proposal (not just its id)."""
    link = snapshot(link)
    fields = {"protocol", "store_id", "conversation_id", "proposal_id", "proposal_version", "proposal_sha256",
              "submission_sha256", "mission_id", "mission_request_sha256"}
    if not isinstance(link, dict) or set(link) != fields or link["protocol"] != LINK_PROTOCOL:
        raise ContractError("LINK_INVALID: exact versioned link fields required")
    try:
        Store.check_id(link["mission_id"])
    except ValueError:
        raise ContractError("LINK_INVALID: invalid mission_id") from None
    _sha(link["submission_sha256"], "submission_sha256")
    proposal = validate_proposal(proposal)
    if (link["store_id"] != proposal["store_id"] or link["conversation_id"] != proposal["conversation_id"]
            or link["proposal_id"] != proposal["proposal_id"] or link["proposal_version"] != proposal["version"]
            or link["proposal_sha256"] != proposal_sha256(proposal)):
        raise ContractError("LINK_INVALID: link does not name this frozen proposal")
    objective = mission.get("objective") if isinstance(mission, dict) else None
    if (not isinstance(objective, dict) or mission.get("id") != link["mission_id"]
            or mission.get("request") != proposal["request"]
            or link["mission_request_sha256"] != digest(proposal["request"])
            or objective.get("kind") != proposal["template"]
            or objective.get("request_sha256") != digest(proposal["request"])
            or objective.get("target_id") != proposal["target_id"]):
        raise ContractError("LINK_INVALID: mission is not the submitted proposal")
    return link
