# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : action_view.py
# Description : Lecture des accords et preuves sans autoriser ni exécuter
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Pure projection of a durable snapshot. Never an execution permission.

No IO, clock, expiry or live health lookup. Historical human attestations remain
attestations. Missing evidence never becomes evidence of absence of an effect.
"""
from .contracts import digest, ContractError
from .store import TERMINAL

DECISIONS = {
    "PENDING": "Proposition en attente de décision, sans expiration automatique.",
    "APPROVED": "Accord enregistré ; les contrôles d'exécution restent obligatoires.",
    "REJECTED": "Proposition refusée.",
    "REVOKED": "Accord révoqué.",
    "USED": "Accord consommé au lancement ; cela ne prouve pas un effet.",
}
EFFECTS = {
    "NOT_STARTED": "Aucun lancement enregistré pour cette proposition.",
    "NOT_AUTHORIZED": "Cette tentative n'a pas reçu l'autorisation d'appeler l'outil.",
    "NO_EFFECT_REPORTED": "Absence d'effet déclarée lors d'une réconciliation humaine, pas vérifiée par cette vue.",
    "UNKNOWN": "Effet inconnu ; aucune absence d'effet déduite du statut de l'accord.",
    "RESULT_UNVERIFIED": "Résultat conservé, vérification encore requise.",
    "VERIFIED_PAST_EFFECT": "Effet passé vérifié ; la santé actuelle du service n'est pas connue par cette vue.",
    "INCONSISTENT_EVIDENCE": "Preuve incohérente ; cette vue ne confirme aucun effet.",
}


def _matches(value, expected):
    try:
        return expected == digest(value)
    except ContractError:
        return False


def _attempt(mission, proposal):
    binding = proposal["action"]
    for call in mission.get("calls", []):
        if call["id"] != binding["call_id"]:
            continue
        if call["attempt"] == binding["attempt"]:
            return call
        for prior in call.get("attempt_history", []):
            if prior["attempt"] == binding["attempt"]:
                return prior
    return None


def _effect(proposal, attempt):
    if attempt is None:
        return "UNKNOWN"
    if proposal["status"] != "USED":
        return "NOT_STARTED" if attempt.get("status") == "PREPARED" else "UNKNOWN"
    if attempt.get("approval_sha256") != proposal["sha256"]:
        return "INCONSISTENT_EVIDENCE"
    if attempt.get("status") in {"VERIFIED", "RETURNED"}:
        if attempt.get("output") is None or not _matches(attempt["output"], attempt.get("output_sha256")):
            return "INCONSISTENT_EVIDENCE"
        return "VERIFIED_PAST_EFFECT" if attempt["status"] == "VERIFIED" else "RESULT_UNVERIFIED"
    # A retained successful receipt contradicts a claim that nothing happened;
    # even here, it is not promoted to a verified result.
    for key in ("late_receipt", "recovered_receipt", "error_receipt"):
        if key in attempt:
            if not _matches(attempt[key], attempt.get(key + "_sha256")):
                return "INCONSISTENT_EVIDENCE"
            if attempt[key].get("ok") is True:
                return "RESULT_UNVERIFIED"
    reconciliation = attempt.get("reconciliation", {})
    if reconciliation.get("decision") == "not-authorized":
        return "NOT_AUTHORIZED"
    if reconciliation.get("decision") == "no-effect":
        if reconciliation.get("worker_authorized") is False:
            return "NOT_AUTHORIZED"
        if reconciliation.get("confirmed_no_effect") is True:
            return "NO_EFFECT_REPORTED"
    return "UNKNOWN"


def action_view(mission):
    """Describe the CURRENT proposal and its exact attempt, including history."""
    proposal = mission.get("proposal")
    if not proposal:
        return None
    binding = proposal["action"]
    status = proposal["status"]
    attempt = _attempt(mission, proposal)
    error = (mission.get("error") or {}).get("code")
    last = mission.get("last_condition_check")
    condition = binding["condition"]
    changed = last is not None and any(last.get(k) != value for k, value in condition.items())
    if mission["status"] in TERMINAL:
        code, message = "MISSION_CLOSED", "Mission close ; cet accord ne permet aucun nouveau lancement."
    elif mission.get("cancel_requested"):
        code, message = "CANCEL_REQUESTED", "Annulation demandée ; cet affichage n'autorise aucune action."
    elif error == "CONFIGURATION_CHANGED":
        code, message = "CONFIGURATION_MISMATCH", "Reprise bloquée avec la configuration utilisée ; ne pas déduire une invalidité définitive."
    elif not _matches(binding, proposal.get("sha256")) or error == "APPROVAL_INVALID":
        code, message = "BINDING_INVALID", "Liaison de l'accord incohérente ; examen requis."
    elif changed or error == "ACTION_PRECONDITION_CHANGED":
        code, message = "STALE_CONDITION", "Condition observée différente de celle approuvée ; nouvelle mission après revue."
    elif status == "PENDING":
        code, message = "AWAITING_DECISION", "Une décision explicite reste nécessaire."
    elif status in {"REJECTED", "REVOKED"}:
        code, message = status, "Cette proposition ne permet pas de lancer l'action."
    elif status == "USED":
        code, message = "CONSUMED", "Accord déjà consommé ; consulter la preuve et la tentative, sans rejouer l'action."
    else:
        code, message = "RECHECK_REQUIRED", "Accord enregistré ; permissions, configuration et condition doivent être revérifiées par run."
    effect = _effect(proposal, attempt) if _matches(binding, proposal.get("sha256")) else "INCONSISTENT_EVIDENCE"
    return {"version": 1, "snapshot_only": True, "authorizes_execution": False,
            "proposal_sha256": proposal["sha256"], "call_id": binding["call_id"], "attempt": binding["attempt"],
            "decision": {"status": status, "message": DECISIONS.get(status, "État d'accord inconnu.")},
            "applicability": {"code": code, "message": message},
            "effect": {"code": effect, "message": EFFECTS[effect]}}


def presented_mission(mission):
    """Add a fresh view to CLI JSON without changing the stored mission."""
    result = {k: v for k, v in mission.items() if k != "action_view"}
    view = action_view(mission)
    if view is not None:
        result["action_view"] = view
    return result
