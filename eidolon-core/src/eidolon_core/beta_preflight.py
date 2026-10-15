# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_preflight.py
# Description : Diagnostic hors ligne avant lancement des profils
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read-only configuration checks; never instantiate BetaRuntime or open its DB.

Default: read the JSON configuration only. --local-files additionally opens the
configured directories and reads credentials under the invoking Linux account.
No network, listing of user files, service, lock or state write. This is a bounded
observation, not an atomic snapshot, an installation or deployment authorization.
"""
import argparse
import json
import os
from pathlib import Path
import stat

from .beta_runtime import validate_config
from .bridge_credentials import read_bridge_token
from .runtime_json import read_json_snapshot, _open_directory, missing_primitives


class UsageError(ValueError):
    pass


class CheckRefused(ValueError):
    """Only static internal diagnostic codes may be exposed."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo unknown arguments: an operator may have pasted a secret.
        raise UsageError("INVALID_ARGUMENTS")


def inspect(filename, *, local_files=False):
    checks = []

    def record(name, status, code):
        checks.append({"check": name, "status": status, "code": code})

    def attempt(name, function):
        try:
            value = function()
        except CheckRefused as exc:
            record(name, "FAIL", str(exc))
            return None
        except (OSError, ValueError):
            record(name, "FAIL", "UNAVAILABLE_OR_INVALID")
            return None
        record(name, "PASS", "CHECKED")
        return value

    def result():
        blocked = any(c["status"] == "FAIL" for c in checks)
        return {"schema": "eidolon-beta-preflight/1",
                "state": "BLOCKED" if blocked else "LOCAL_FILES_VALID" if local_files else "CONFIG_VALID",
                "scope": "local_files" if local_files else "config_only",
                "beta_authorized": False, "checks": checks}, 2 if blocked else 0

    if missing_primitives():
        record("platform", "FAIL", "LINUX_PRIMITIVES_REQUIRED")
        return result()

    def load():
        path = Path(filename).absolute()
        return validate_config(read_json_snapshot(str(path.parent), path.name,
                                                 max_bytes=65536, max_depth=6))

    config = attempt("configuration", load)
    if config is None:
        return result()

    if local_files:
        def private_configuration():
            path = Path(filename).absolute()
            fd = _open_directory(str(path.parent))
            try:
                info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
                    raise CheckRefused("OWNER_0600_REGULAR_FILE_REQUIRED")
            finally:
                os.close(fd)

        def directory(path, private=False):
            fd = _open_directory(path)
            try:
                info = os.fstat(fd)
                if private and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
                    raise CheckRefused("OWNER_0700_DIRECTORY_REQUIRED")
            finally:
                os.close(fd)

        attempt("configuration_permissions", private_configuration)
        attempt("state_directory", lambda: directory(config["state_directory"], private=True))
        # Compare actual secrets, not merely their paths. Never emit secrets or
        # their fingerprints, and do not retain them beyond this invocation.
        seen = set()
        for number, profile in enumerate(config["profiles"].values(), 1):
            for role in ("read", "write"):
                name = f"profile_{number}.{role}_token"
                path = profile[f"{role}_token_file"]
                if path is None:
                    record(name, "NOT_APPLICABLE", "WRITE_DISABLED")
                    continue

                def credential():
                    token = read_bridge_token(path)
                    if token in seen:
                        raise CheckRefused("CREDENTIAL_REUSED")
                    seen.add(token)

                attempt(name, credential)
            for root_number, path in enumerate(profile["file_roots"].values(), 1):
                attempt(f"profile_{number}.file_root_{root_number}", lambda: directory(path))
        if config.get("identity_config"):
            from .identity_runtime import load, engine
            from .identity_engines import verify_model
            identity = attempt("identity_configuration", lambda: load(config["identity_config"]))
            if identity is not None:
                import importlib.util
                for modality, cfg in identity["modalities"].items():
                    for role in ("model", "detector") if modality == "face" else ("model",):
                        def model():
                            info = engine(cfg, modality)
                            verify_model(cfg[role]["path"],cfg[role]["sha256"],name=info.name,preprocessing=info.preprocessing)
                        attempt("identity_"+modality+"_"+role,model)
                    for package in (("numpy","onnxruntime") if modality == "voice" else ("numpy","cv2")):
                        def dependency():
                            if importlib.util.find_spec(package) is None:
                                raise CheckRefused("OPTIONAL_DEPENDENCY_MISSING")
                        attempt("identity_dependency_"+package,dependency)
                record("identity_accuracy_and_calibration","NOT_RUN","REQUIRES_MACHINE_ACCEPTANCE")
    else:
        record("local_files", "NOT_RUN", "REQUIRES_LOCAL_FILES_OPTION")

    for check in ("existing_state_binding", "paired_clients", "memory_identity_and_permissions",
                  "network_services", "models_and_corpus", "file_contents_and_mount_rights",
                  "windows_and_hardware"):
        record(check, "NOT_RUN", "REQUIRES_MACHINE_ACCEPTANCE")
    return result()


def main(argv=None):
    parser = Parser(description="Eidolon Core — diagnostic hors ligne, sans lancement", allow_abbrev=False)
    parser.add_argument("--config", required=True, help="Configuration beta-runtime JSON")
    parser.add_argument("--local-files", action="store_true", help="Lire aussi les fichiers locaux sous le compte cible")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    try:
        args = parser.parse_args(argv)
    except UsageError:
        print(json.dumps({"schema": "eidolon-beta-preflight/1", "state": "USAGE_ERROR",
                          "code": "INVALID_ARGUMENTS", "beta_authorized": False}))
        return 64
    report, code = inspect(args.config, local_files=args.local_files)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        from .presentation import header, message
        print(header(title="Diagnostic avant lancement"))
        print(message("INFO", "Périmètre : " + report["scope"]))
        for row in report["checks"]:
            level = "OK" if row["status"] == "PASS" else "ERREUR" if row["status"] == "FAIL" else "ATTENTION"
            print(message(level, f"{row['check']} : {row['status']} ({row['code']})"))
        print(message("INFO", "Aucun service démarré. La recette sur machines reste nécessaire."))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
