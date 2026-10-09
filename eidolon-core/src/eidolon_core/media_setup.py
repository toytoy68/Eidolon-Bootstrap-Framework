# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_setup.py
# Description : État de configuration des six opérations média, sans moteur ni source
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Offline installation aid, not an engine health check or execution permission.

Only configured FFmpeg file metadata and an optional artifact-store marker are
read. No source, inventory payload, socket, subprocess, job or model is opened.
CONFIGURED_SCOPE means structural configuration for the requested operations.
The per-request preflight and execution still validate their actual inputs.
"""
import json
import re

from .media_agents import MediaError
from .media_artifacts import ArtifactStore
from .media_backends import LocalMediaBackend, endpoint, ffmpeg_executable, vision_model
from .media_preflight import fingerprint
from .media_workflows import OPERATIONS, WORKFLOW_OPERATIONS, definition
from .presentation import header, message, section

HINTS = {
    "MISSING_COMFY_ENDPOINT": "Renseigner comfy_endpoint avec l'adresse loopback du moteur ComfyUI choisi.",
    "MISSING_OLLAMA_ENDPOINT": "Renseigner ollama_endpoint avec l'adresse loopback du moteur Ollama choisi.",
    "MISSING_VISION_MODEL": "Renseigner vision_model avec le nom exact d'un modèle Vision installé localement.",
    "MISSING_FFMPEG": "Renseigner ffmpeg avec le chemin absolu de l'exécutable local.",
    "MISSING_WORKFLOW": "Ajouter le workflow au format API et ses bindings pour cette opération.",
    "INVALID_ENDPOINT": "Vérifier l'adresse : HTTP, IP loopback littérale, port explicite, sans chemin ni identifiants.",
    "LOCAL_ENDPOINT_REQUIRED": "Vérifier l'adresse : HTTP, IP loopback littérale, port explicite, sans chemin ni identifiants.",
    "VISION_MODEL_NOT_CONFIGURED": "Vérifier le nom exact du modèle Vision ; aucun modèle n'est téléchargé par ce contrôle.",
    "FFMPEG_NOT_CONFIGURED": "Vérifier que le chemin absolu ffmpeg désigne un fichier existant.",
    "FFMPEG_NOT_EXECUTABLE": "Vérifier les droits d'exécution du programme FFmpeg choisi.",
    "WORKFLOW_BINDINGS_MISMATCH": "Vérifier prompt, width, height, source pour modifier et duration_seconds pour la vidéo.",
    "INVALID_WORKFLOW_BINDING": "Chaque binding doit désigner une entrée existante distincte : [noeud, champ].",
    "INVALID_WORKFLOW_NODE": "Vérifier les identifiants de noeuds, class_type et les dictionnaires inputs.",
    "INVALID_WORKFLOW_CONFIG": "Vérifier la structure prompt/bindings du workflow API.",
    "UNKNOWN_WORKFLOW_OPERATION": "Les workflows concernent image.create, image.edit, video.create et video.edit.",
    "INVALID_STAGED_SOURCES": "Vérifier les empreintes SHA-256 et noms simples de fichiers déjà déposés dans ComfyUI.",
    "ARTIFACT_STORE_NOT_CONFIGURED": "Vérifier artifact_store : root et store_id, retournés par artifact-init.",
    "ARTIFACT_STORE_MISMATCH": "Utiliser l'identité du magasin choisi ; ne pas remplacer son marqueur.",
    "ARTIFACT_PERMISSIONS": "Vérifier propriétaire, permissions privées et absence de liens du magasin choisi.",
    "WORKFLOW_TOO_LARGE": "Réduire le modèle de workflow sous 500 000 octets ; la demande réelle sera revérifiée.",
}
DEFAULT_HINT = "Vérifier la configuration et les fichiers choisis avec le guide MEDIA-AGENTS ; aucune réparation automatique."


def issue(code):
    return {"code": code, "action": HINTS.get(code, DEFAULT_HINT)}


def _attempt(check, issues):
    try:
        return check()
    except (MediaError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        issues.append(issue(exc.code if isinstance(exc, MediaError) else "MEDIA_INPUT_OR_STORAGE_ERROR"))
        return None


def _setting(config, name, validate, issues):
    if name not in config:
        issues.append(issue("MISSING_" + name.upper()))
        return None
    return _attempt(lambda: validate(config[name]), issues)


def _artifact(config):
    if "artifact_store" not in config:
        return {"state": "NOT_CONFIGURED", "required_for_local_source": False, "contents_checked": False}
    entry = config["artifact_store"]
    if (type(entry) is not dict or set(entry) != {"root", "store_id"}
            or not isinstance(entry["root"], str) or not entry["root"]
            or not isinstance(entry["store_id"], str)):
        raise MediaError("ARTIFACT_STORE_NOT_CONFIGURED")
    store = ArtifactStore(entry["root"], expected_store_id=entry["store_id"])
    return {"state": "IDENTITY_OBSERVED", "store_id": store.store_id,
            "required_for_local_source": False, "contents_checked": False,
            "capacity_checked": False, "pending_imports_checked": False}


def check_configuration(config, *, require=None):
    if (require is not None and (type(require) not in (list, tuple) or not require
            or any(type(k) is not str or k not in OPERATIONS for k in require))):
        raise MediaError("INVALID_REQUIRED_OPERATIONS")
    required = list(OPERATIONS) if require is None else [k for k in OPERATIONS if k in require]
    config = LocalMediaBackend(config).config  # shared validation and detached snapshot; no I/O
    config_sha = fingerprint(config)
    common = []
    workflows = config.get("workflows", {})
    if type(workflows) is not dict:
        common.append(issue("INVALID_WORKFLOW_CONFIG"))
    elif set(workflows) - WORKFLOW_OPERATIONS:
        common.append(issue("UNKNOWN_WORKFLOW_OPERATION"))
    staged = config.get("staged_sources", {})
    if (type(staged) is not dict or any(
            not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)
            or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", name)
            or ".." in name or name == "." for sha, name in staged.items())):
        common.append(issue("INVALID_STAGED_SOURCES"))
    artifact = _attempt(lambda: _artifact(config), common)
    rows = []
    for key in OPERATIONS:
        agent, operation = key.split(".")
        errors = []
        row = {"operation": key, "required": key in required,
               "source_required": operation != "create", "issues": errors}
        if operation == "analyze":
            _setting(config, "ollama_endpoint", endpoint, errors)
            model = _setting(config, "vision_model", vision_model, errors)
            if model is not None:
                row["model"] = model
            if agent == "video":
                _setting(config, "ffmpeg", ffmpeg_executable, errors)
            row["backend"] = "ollama-vision/1"
        else:
            row["backend"] = "comfyui-prompt/2"
            _setting(config, "comfy_endpoint", endpoint, errors)
            if type(workflows) is dict and key not in workflows:
                errors.append(issue("MISSING_WORKFLOW"))
            else:
                template = _attempt(lambda: definition(config, key), errors)
                if template is not None:
                    prompt, bindings = template
                    raw = json.dumps(prompt, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    if len(raw) > 500_000:
                        errors.append(issue("WORKFLOW_TOO_LARGE"))
                    row.update(source_required="source" in bindings, nodes=len(prompt),
                               node_classes=len({v["class_type"] for v in prompt.values()}),
                               template_sha256=fingerprint(workflows[key]))
            row["source_transfer"] = config.get("source_transfer", "verify-staged")
            if row["source_required"]:
                row["source_check"] = ("STAGING_AND_CONTENT_CHECK_REQUIRED" if row["source_transfer"] == "verify-staged"
                                       else "UPLOAD_AND_CONTENT_CHECK_REQUIRED")
        row["state"] = ("INVALID" if any(not e["code"].startswith("MISSING_") for e in errors)
                        else "NOT_CONFIGURED" if errors else "CONFIGURED")
        rows.append(row)
    state = ("INVALID" if common or any(r["state"] == "INVALID" for r in rows) else
             "INCOMPLETE" if any(r["required"] and r["state"] != "CONFIGURED" for r in rows) else "CONFIGURED_SCOPE")
    return {"schema": "media-configuration-check/1", "state": state,
            "configuration_sha256": config_sha, "required_operations": required,
            "operations": rows, "issues": common,
            "artifact_store": artifact or {"state": "INVALID", "contents_checked": False},
            "staged_source_count": len(staged) if type(staged) is dict else None,
            "staged_sources_content_checked": False, "server_contacted": False,
            "source_content_read": False, "process_started": False, "job_created": False,
            "execution_authorized": False, "hardware_qualified": False,
            "runtime_catalog_registered": False, "execution_from_home": False}


def render_configuration(report):
    lines = [header(title="Configuration des agents média"),
             message("INFO", "Contrôle hors ligne : aucun moteur contacté, aucune source lue, aucun programme lancé."),
             section("Opérations")]
    for row in report["operations"]:
        level = "OK" if row["state"] == "CONFIGURED" else "ERREUR" if row["state"] == "INVALID" else "ATTENTION"
        state = {"CONFIGURED": "configuration structurelle vérifiée", "NOT_CONFIGURED": "configuration à compléter", "INVALID": "configuration refusée"}[row["state"]]
        lines.append(message(level, row["operation"] + " : " + state + (" (demandée)" if row["required"] else "")))
        lines.extend(message("INFO", e["code"] + " — " + e["action"]) for e in row["issues"])
        if row.get("source_check"):
            lines.append(message("INFO", "Source à choisir : dépôt/transfert et empreinte seront vérifiés pour la demande réelle."))
    lines.append(section("Configuration commune"))
    lines.extend(message("ERREUR", e["code"] + " — " + e["action"]) for e in report["issues"])
    artifact = report["artifact_store"]
    lines.append(message("INFO", "Magasin d'artefacts : " + artifact["state"] + " ; contenus et capacité non contrôlés."))
    lines.extend([section("Étape suivante"),
                  message("INFO", "Préparer une demande, puis utiliser eidolon-media preflight pour ses entrées réelles."),
                  message("ATTENTION", "La présence des modèles, nœuds et GPU n'est pas vérifiée. Ce diagnostic n'autorise aucune exécution.")])
    return "\n".join(lines)


def render_setup_error(code):
    return "\n".join([header(title="Diagnostic des agents média"), message("ERREUR", code),
                      message("INFO", HINTS.get(code, DEFAULT_HINT))])
