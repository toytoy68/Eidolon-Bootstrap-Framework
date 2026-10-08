# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : qualification_io.py
# Description : Lecture bornée et vérification hors ligne d'un rapport
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Read an explicit regular report file; never create state or start a model.

The digest identifies the bytes checked, not their authenticity. Metadata checks
detect ordinary concurrent replacements/writes, not a hostile filesystem. Parent
directories are operator-selected; only the final path component refuses symlinks.
"""
import hashlib
import os
import stat

from .qualification import MAX_BYTES, ReportError, validate
from .presentation import header, message

CHECK_SCHEMA = "eidolon-qualification-check/1"
EXIT_CODES = {"PASSED_SCOPE": 0, "INCOMPLETE": 2, "REJECTED": 3}


class QualificationCheckError(ValueError):
    """Stable diagnostics without reflecting a private path or malformed input."""


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_report(path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        initial = os.fstat(descriptor)
        if not stat.S_ISREG(initial.st_mode):
            raise QualificationCheckError("REPORT_NOT_REGULAR")
        if initial.st_size > MAX_BYTES:
            raise QualificationCheckError("REPORT_TOO_LARGE")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read(MAX_BYTES + 1)
            final = os.fstat(stream.fileno())
        current = os.stat(path, follow_symlinks=False)
        if len(raw) > MAX_BYTES:
            raise QualificationCheckError("REPORT_TOO_LARGE")
        if (_signature(initial) != _signature(final)
                or _signature(initial) != _signature(current)
                or len(raw) != initial.st_size):
            raise QualificationCheckError("REPORT_CHANGED")
        return raw
    except OSError:
        raise QualificationCheckError("REPORT_UNAVAILABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def check_report(path):
    raw = read_report(path)
    try:
        verdict = validate(raw)
    except ReportError:
        # The pure validator's detailed exception can contain unknown keys from
        # the input. CLI diagnostics must not copy malformed private content.
        raise QualificationCheckError("REPORT_MALFORMED") from None
    return {"schema": CHECK_SCHEMA, "report_sha256": hashlib.sha256(raw).hexdigest(),
            "authorizes_execution": False, "telemetry_authenticated": False,
            **verdict.to_dict()}


def render_check(result):
    status = result["status"]
    scope = result["scope"]
    labels = {"PASSED_SCOPE": ("OK", "Rapport cohérent dans le périmètre déclaré."),
              "INCOMPLETE": ("ATTENTION", "Rapport incomplet."),
              "REJECTED": ("ERREUR", "Rapport rejeté par les critères de vérification.")}
    level, label = labels[status]
    lines = [header(title="Vérification d'un rapport"), message(level, label),
             message("INFO", "Verdict : " + status),
             message("INFO", "Origine déclarée : " + scope["origin"]),
             message("INFO", f"Profil {scope['profile']} ; moteur {scope['engine']} ; modèle {scope['model']}"),
             message("INFO", "Périmètre déclaré : " + scope["statement"]),
             message("INFO", "SHA-256 du rapport : " + result["report_sha256"])]
    for reason in result["reasons"]:
        lines.append(message("ATTENTION", reason["code"] + " : " + reason["detail"]))
    lines.append(message("ATTENTION", "Authenticité des mesures non vérifiée ; aucune qualification matérielle ni autorisation d'exécution."))
    return "\n".join(lines)
