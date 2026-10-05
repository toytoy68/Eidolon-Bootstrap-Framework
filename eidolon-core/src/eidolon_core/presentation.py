# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : presentation.py
# Description : Présentation console commune, sans effet métier
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Human console rendering; business state and machine output stay separate."""
from . import __version__

COMPANY_NAME = "Eidolon Core Technologies"
COMPANY_SHORT = "ECT"
COMPANY_MOTTO = "Local AI • Modular • Reliable • Reproducible"
PRESENTATION_STANDARD = "Eidolon Presentation Standard v1"
WIDTH = 57


def safe_text(value):
    """Display terminal controls as text, including untrusted provider errors."""
    return "".join(c if c.isprintable() else f"\\u{ord(c):04x}" for c in str(value))


def header(component="Eidolon Core", title="Suivi de mission"):
    def row(text):
        return "#" + safe_text(text).center(WIDTH - 2) + "#"
    return "\n".join(("", "#" * WIDTH, row(""), row(component), row(title),
                      row(""), "#" * WIDTH, "", f"{COMPANY_NAME} ({COMPANY_SHORT})",
                      COMPANY_MOTTO, f"Version            : {__version__}", ""))


def section(title):
    return "\n" + "=" * WIDTH + "\n" + safe_text(title) + "\n" + "=" * WIDTH


def message(level, text):
    if level not in {"INFO", "OK", "ATTENTION", "ERREUR"}:
        raise ValueError("unknown presentation level")
    return f"[{level}] {safe_text(text)}"


def preview():
    """Static presentation preview, never a claim that software was installed."""
    return "\n".join((
        header(title="Aperçu de présentation"),
        message("INFO", "Aperçu du style d'installation — aucune installation exécutée."),
        "", "Ce programme va :", "", "  • Présenter l'identité Eidolon",
        "  • Afficher les sections et les niveaux de message",
        "  • Montrer le format du bilan final",
        section("Vérifications"), message("INFO", "Standard : " + PRESENTATION_STANDARD),
        message("ATTENTION", "Cet aperçu ne vérifie ni Debian, ni Docker, ni le GPU."),
        section("Résumé"), message("OK", "Présentation générée."),
        section("Prochaine étape"),
        "  PYTHONPATH=src python -m eidolon_core --format human demo", "",
    ))


def render_result(result):
    status = result["status"]
    label = {"NEW": "Mission créée", "RUNNING": "Mission en cours",
             "BLOCKED": "Mission bloquée", "REVIEW_REQUIRED": "Réconciliation requise",
             "SUCCEEDED": "Mission réussie", "FAILED": "Mission échouée",
             "CANCELLED": "Mission annulée", "ABANDONED": "Mission abandonnée — effet inconnu"}[status]
    level = {"SUCCEEDED": "OK", "FAILED": "ERREUR", "BLOCKED": "ATTENTION",
             "REVIEW_REQUIRED": "ATTENTION", "CANCELLED": "ATTENTION", "ABANDONED": "ATTENTION"}.get(status, "INFO")
    progress = result["progress"]
    lines = [header(), f"Mission            : {safe_text(result['id'])}",
             f"Demande            : {safe_text(result['request'])}",
             f"Phase              : {safe_text(result['phase'])}",
             f"Étapes vérifiées   : {progress['completed']} / {progress['total'] if progress['total'] is not None else '?'}",
             section("Résumé"), message(level, label)]
    if result.get("cancel_requested"):
        lines.append(message("ATTENTION", "Demande d'annulation enregistrée."))
    if result.get("error"):
        error = result["error"]
        lines.append(message(level, f"{error['code']} : {error['message']}"))
    if result["calls"]:
        lines.append(section("Résultats et preuves"))
        for call in result["calls"]:
            verified = call["status"] == "VERIFIED"
            lines.append(message("OK" if verified else "INFO", f"{call['id']} — {call['status']}"))
            if verified:
                lines.append(message("INFO", f"Vérificateur : {call['verifier']}"))
                for key, value in call["output"].items():
                    lines.append("  " + safe_text(key) + " : " + safe_text(value))
    if result.get("context"):
        lines.append(section("Sources et réserves"))
        for item in result["context"]["items"]:
            lines.append(message("ATTENTION" if item["needs_review"] else "INFO",
                                 f"{item['information_id']}@{item['revision']} — "
                                 f"statut={item['epistemic_status']}, revue={item['needs_review']}"))
        lines.append(message("INFO", "Un résultat technique vérifié ne confirme pas le contenu des sources."))
    if result.get("events"):
        lines.append(section("Journal"))
        for event in result["events"]:
            lines.append(message("INFO", f"{event['sequence']} | {event['at']} | {event['kind']}"))
    lines.extend((section("Prochaine étape"),
                  message("INFO", "Inspection détaillée : show " + result["id"] + " --events (avec les mêmes options --state)."),
                  ""))
    return "\n".join(lines)


def render_error(error, message_text):
    return header(title="Diagnostic") + "\n" + message("ERREUR", f"{error} : {message_text}")
