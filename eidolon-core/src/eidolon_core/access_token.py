# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : access_token.py
# Description : Création exclusive d’un jeton local de consultation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Publish a complete private token file on Linux, never replace an existing one.

The parent directory must already exist and be trusted by its operator.
An atomic hard link publishes a fully written/fsynced inode. Directory fsync
confirms durability separately; once published, a token is never rolled back.
No token, fingerprint, path or raw exception is returned or printed.
"""
import argparse
import json
import os
from pathlib import Path
import secrets

from .presentation import header, message

PROTOCOL = "eidolon-read-token-setup/1"
MESSAGES = {
    "TOKEN_CREATED": "Jeton créé dans un fichier privé ; son contenu n’est pas affiché.",
    "INVALID_DESTINATION": "Choisir un nom de fichier dans un dossier existant.",
    "PARENT_UNAVAILABLE": "Dossier parent inaccessible ou lien final refusé ; aucun dossier créé.",
    "DESTINATION_EXISTS": "La destination existe déjà ; elle n’a pas été écrasée.",
    "TOKEN_WRITE_FAILED": "Création ou écriture du fichier temporaire impossible.",
    "TOKEN_PUBLISH_FAILED": "Publication impossible ; vérifier les droits et le support des liens physiques.",
    "TOKEN_DIRECTORY_SYNC_FAILED": "Fichier publié, mais durabilité du dossier non confirmée.",
    "TOKEN_CLEANUP_FAILED": "Nettoyage du temporaire incomplet ; vérifier le dossier localement.",
}


def create(destination):
    """Return a sanitized result; CREATED_REVIEW_REQUIRED means a file exists."""
    report = {"protocol": PROTOCOL, "status": "NOT_CREATED", "code": "INVALID_DESTINATION",
              "destination_created": False, "cleanup_complete": True,
              "durability_confirmed": False, "existing_servers_updated": False,
              "authorizes_execution": False}
    try:
        target = Path(destination)
        if target.name in {"", ".", ".."}:
            return report
    except (TypeError, ValueError):
        return report
    try:
        parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except (OSError, ValueError):
        report["code"] = "PARENT_UNAVAILABLE"
        return report
    staged = None
    descriptor = None
    phase = "write"
    try:
        # A random staging name is separate from the actual bearer token.
        name = ".eidolon-read-token-" + secrets.token_hex(16)
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        staged = name
        os.fchmod(descriptor, 0o600)  # exact mode, including under a restrictive umask
        data = (secrets.token_urlsafe(32) + "\n").encode("ascii")
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise OSError("incomplete write")
            offset += written
        os.fsync(descriptor)
        closing = descriptor
        descriptor = None  # never retry close on a possibly reused descriptor
        os.close(closing)
        phase = "publish"
        os.link(staged, target.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        report["destination_created"] = True
        report["code"] = "TOKEN_CREATED"
    except FileExistsError:
        report["code"] = "DESTINATION_EXISTS" if phase == "publish" else "TOKEN_WRITE_FAILED"
    except (OSError, ValueError, UnicodeError):
        report["code"] = "TOKEN_PUBLISH_FAILED" if phase == "publish" else "TOKEN_WRITE_FAILED"
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                report["cleanup_complete"] = False
        if staged is not None:
            try:
                os.unlink(staged, dir_fd=parent)
            except OSError:
                report["cleanup_complete"] = False
        if report["destination_created"]:
            try:
                os.fsync(parent)
                report["durability_confirmed"] = True
            except OSError:
                report["code"] = "TOKEN_DIRECTORY_SYNC_FAILED"
        try:
            os.close(parent)
        except OSError:
            report["cleanup_complete"] = False
    if not report["cleanup_complete"]:
        report["code"] = "TOKEN_CLEANUP_FAILED"
    if report["destination_created"]:
        report["status"] = ("CREATED" if report["durability_confirmed"] and report["cleanup_complete"]
                            else "CREATED_REVIEW_REQUIRED")
    return report


def render(report, output_format):
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    level = "OK" if report["status"] == "CREATED" else "ATTENTION" if report["destination_created"] else "ERREUR"
    return "\n".join((header(title="Jeton de consultation"),
                      message(level, report["code"] + " : " + MESSAGES[report["code"]]),
                      message("INFO", "Les serveurs déjà lancés conservent leur ancien jeton. "
                              "Vérifier avec http_api --check avant un lancement explicite.")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — créer un fichier jeton privé de consultation")
    parser.add_argument("--output", required=True, help="Nouveau fichier dans un dossier existant de confiance")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    report = create(args.output)
    print(render(report, args.format))
    return 0 if report["status"] == "CREATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
