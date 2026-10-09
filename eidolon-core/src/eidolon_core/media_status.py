# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_status.py
# Description : Lecture humaine d'un journal média, sans reprise ni appel moteur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Render local observations, never infer remote effects from a journal phase."""
import re

from .media_agents import MediaError
from .media_workflows import OPERATIONS
from .presentation import header, message, section

PHASES = {
    "SOURCE_UPLOAD_STARTED": "transfert de la source commencé",
    "SOURCE_UPLOAD_ACKNOWLEDGED": "reçu de transfert enregistré",
    "SOURCE_VERIFYING": "vérification de la source distante commencée",
    "SOURCE_VERIFIED": "empreinte de la source distante comparée",
    "QUEUE_SUBMITTING": "soumission à la file commencée",
    "QUEUE_ACKNOWLEDGED": "reçu de file enregistré",
    "ANALYSIS_SUBMITTING": "demande d'analyse commencée",
}
STATES = {
    "INTENT": "intention enregistrée ; revue nécessaire après interruption",
    "REVIEW_REQUIRED": "revue nécessaire ; effet ou résultat incertain",
    "QUEUED": "reçu de file enregistré ; résultat non vérifié",
    "RESULT_UNVERIFIED": "réponse d'analyse enregistrée ; contenu non vérifié",
}


def render_job(record):
    if type(record) is not dict or record.get("schema") != "media-job/1":
        raise MediaError("INVALID_JOB")
    # Only fixed labels and tightly checked identifiers enter the terminal.
    # Prompts, model replies, backend errors and paths remain in the JSON journal.
    state = record.get("state")
    state = state if type(state) is str and state in STATES else None
    phase = record.get("phase")
    phase = phase if type(phase) is str and phase in PHASES else None
    agent, operation = record.get("agent"), record.get("operation")
    key = agent + "." + operation if type(agent) is str and type(operation) is str else None
    key = key if key in OPERATIONS else None
    ident = record.get("id")
    ident = ident if type(ident) is str and re.fullmatch(r"media-[0-9a-f]{32}", ident) else None
    lines = [header(title="État d'un travail média"),
             message("INFO", "Lecture du journal local uniquement ; aucun moteur contacté."),
             section("Observation locale"),
             message("INFO", "Travail : " + (ident or "identifiant non reconnu")),
             message("INFO", "Opération : " + (key or "opération non reconnue")),
             message("ATTENTION", STATES[state] if state else "état non reconnu ; revue manuelle nécessaire"),
             message("INFO", "Dernière étape enregistrée : " + (PHASES[phase] if phase else "non renseignée ou non reconnue"))]
    backend = record.get("backend")
    receipt = record.get("result") if state == "QUEUED" else (
        record.get("phase_evidence") if state in {"INTENT", "REVIEW_REQUIRED"} and phase == "QUEUE_ACKNOWLEDGED" else None)
    prompt_id = receipt.get("prompt_id") if type(receipt) is dict else None
    pollable = (ident is not None and key in {"image.create", "image.edit", "video.create", "video.edit"}
                and type(backend) is dict and backend.get("adapter") in ("comfyui-prompt/1", "comfyui-prompt/2")
                and type(prompt_id) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", prompt_id) is not None)
    if pollable:
        # Endpoint is not echoed and does not become a runnable command.
        from .media_backends import endpoint
        try:
            endpoint(backend.get("endpoint"))
        except MediaError:
            pollable = False
    lines.append(section("Suite possible"))
    if pollable:
        lines.extend([message("INFO", "Identifiant du reçu : " + prompt_id),
                      message("INFO", "Utiliser explicitement eidolon-media poll avec ce dossier pour consulter l'historique."),
                      message("INFO", "Après un historique terminé, collect permet une collecte explicite vers un magasin choisi.")])
    elif state == "RESULT_UNVERIFIED":
        lines.append(message("INFO", "Consulter le résultat dans le journal JSON et vérifier son contenu ; aucune collecte ComfyUI pour cette analyse."))
    else:
        lines.append(message("ATTENTION", "Aucun reçu de file exploitable observé ; vérifier le moteur et le journal avant toute nouvelle demande."))
    if phase in {"SOURCE_UPLOAD_STARTED", "SOURCE_UPLOAD_ACKNOWLEDGED", "SOURCE_VERIFYING", "SOURCE_VERIFIED"}:
        lines.append(message("INFO", "Une source peut déjà être présente côté moteur ; aucun effacement ni nouveau transfert effectué."))
    lines.extend([message("ATTENTION", "La dernière étape ne prouve ni absence d'effet, ni état actuel du moteur. Ne pas renvoyer automatiquement la demande."),
                  message("INFO", "Ce contrôle ne lit pas les octets de la source et ne modifie pas le travail."),
                  message("INFO", "Aucune permission d'exécution ou réussite de mission n'est déduite du journal.")])
    return "\n".join(lines)
