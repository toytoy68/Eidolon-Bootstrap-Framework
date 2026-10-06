# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : preflight.py
# Description : Diagnostic local des prérequis de consultation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Inspect existing read-server inputs without binding or creating state.

Each check is an observation, not a lease on files or a full database audit.
Never include paths, tokens, exception messages or mission data in the report.
"""
import json
import sqlite3

from .contracts import ContractError
from .http_api import ReadOnlyStore, read_assets, read_token
from .presentation import header, message

PROTOCOL = "eidolon-http-preflight/1"
KNOWN_ERRORS = {
    "TOKEN_FILE_NOT_PRIVATE", "INVALID_TOKEN", "STATE_NOT_FOUND",
    "RECOVERY_REVIEW_ONLY", "UNSUPPORTED_READ_SCHEMA", "INVALID_STORE_ID",
    "INVALID_WEB_ROOT", "ASSET_TOO_LARGE",
    "BETA_PREPARATION_INCOMPLETE",
}
TEXT = {
    "BETA_PREPARATION_INCOMPLETE": "Jeu synthétique incomplet ; choisir une nouvelle destination et relancer sa préparation.",
    "TOKEN_VALID": "Jeton lisible, privé et au format attendu.",
    "TOKEN_FILE_NOT_PRIVATE": "Le jeton doit être un fichier régulier privé, appartenant à cet utilisateur.",
    "INVALID_TOKEN": "Format du jeton invalide.",
    "TOKEN_UNAVAILABLE": "Jeton inaccessible ; vérifier son fichier et les droits.",
    "STATE_READABLE": "Base existante lisible, schéma et identité reconnus, garde de récupération absente.",
    "STATE_NOT_FOUND": "Dossier ou base Core absent ; choisir un état existant.",
    "STATE_UNAVAILABLE": "Base illisible ou inaccessible ; vérifier localement le fichier et les droits.",
    "RECOVERY_REVIEW_ONLY": "État en revue de récupération ; terminer cette revue avant consultation.",
    "UNSUPPORTED_READ_SCHEMA": "Schéma non pris en charge ; aucune migration effectuée.",
    "INVALID_STORE_ID": "Identité de la base invalide.",
    "ASSETS_READABLE": "Les trois fichiers du client sont lisibles et respectent la limite de taille.",
    "NO_WEB_ROOT": "Client non demandé : seules les routes API seront disponibles.",
    "INVALID_WEB_ROOT": "Client incomplet, inaccessible ou lien symbolique refusé.",
    "ASSET_TOO_LARGE": "Un fichier du client dépasse la limite du serveur.",
    "PORT_VALID": "Numéro de port valide ; disponibilité non testée.",
    "INVALID_PORT": "Le port doit être un entier compris entre 0 et 65535.",
}


def inspect(state, token_file, *, port=8765, web_root=None):
    """Perform independent local checks; failures do not hide other failures."""
    checks = []

    def check(name, action, success, fallback, missing=None):
        try:
            action()
        except FileNotFoundError:
            code = missing or fallback
        except (ValueError, OSError, sqlite3.Error, ContractError) as exc:
            # Only fixed codes escape this boundary, never raw exception text.
            code = str(exc) if str(exc) in KNOWN_ERRORS else fallback
        else:
            checks.append({"name": name, "status": "PASS", "code": success})
            return
        checks.append({"name": name, "status": "FAIL", "code": code})

    check("token", lambda: read_token(token_file), "TOKEN_VALID", "TOKEN_UNAVAILABLE")
    check("state", lambda: ReadOnlyStore(state).health(), "STATE_READABLE",
          "STATE_UNAVAILABLE", "STATE_NOT_FOUND")
    if web_root is None:
        checks.append({"name": "client", "status": "SKIP", "code": "NO_WEB_ROOT"})
    else:
        check("client", lambda: read_assets(web_root), "ASSETS_READABLE", "INVALID_WEB_ROOT")
    valid_port = type(port) is int and 0 <= port <= 65535
    checks.append({"name": "port", "status": "PASS" if valid_port else "FAIL",
                   "code": "PORT_VALID" if valid_port else "INVALID_PORT"})
    return {"protocol": PROTOCOL, "status": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS",
            "checks": checks, "server_started": False, "port_availability_checked": False,
            "client_browser_tested": False, "full_database_audit": False,
            "authorizes_execution": False}


def render(report, output_format="json"):
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    if output_format != "human":
        raise ValueError("INVALID_FORMAT")
    lines = [header(title="Diagnostic de consultation")]
    levels = {"PASS": "OK", "FAIL": "ERREUR", "SKIP": "INFO"}
    for item in report["checks"]:
        lines.append(message(levels[item["status"]], item["code"] + " : " + TEXT[item["code"]]))
    lines.append(message("INFO", "Serveur non démarré ; port, navigateur et tunnel SSH non testés. "
                         "Ce diagnostic ne qualifie pas la bêta et ne remplace pas un audit de la base."))
    return "\n".join(lines)
