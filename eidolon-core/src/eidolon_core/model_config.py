# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : model_config.py
# Description : Configuration opérateur privée du planificateur local optionnel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit CLI configuration, never obtained from a model or memory source.

Loading config sends nothing. Execution sends the mission request and recalled
context to the literal loopback endpoint. No remote opt-out or inline secret is
accepted; llama-server may name a credential environment variable for call time.
"""
import json
import os
import stat
from urllib.parse import urlsplit

from .contracts import ContractError
from .ollama_model import OllamaConfig, OllamaModel
from .openai_chat_model import OpenAIChatConfig, OpenAIChatModel

MAX_CONFIG_BYTES = 16384
REQUIRED = {"version", "provider", "endpoint", "model", "options"}
OPTIONAL = {"timeout_seconds", "max_prompt_bytes", "max_response_bytes", "max_output_bytes"}
PROVIDERS = {"ollama", "llama-server"}


class ModelConfigError(ContractError):
    pass


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError()

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
        if (type(value) is not dict or not REQUIRED <= set(value)
                or type(value["version"]) is not int or value["version"] != 1
                or type(value["provider"]) is not str or value["provider"] not in PROVIDERS
                or type(value["endpoint"]) is not str
                or any(ord(c) <= 32 or ord(c) == 127 for c in value["endpoint"])):
            raise ValueError()
        provider = value["provider"]
        optional = OPTIONAL | ({"context_tokens", "api_key_env"} if provider == "llama-server" else set())
        if not set(value) <= REQUIRED | optional:
            raise ValueError()
        url = urlsplit(value["endpoint"])
        if (url.hostname not in {"127.0.0.1", "::1"} or url.port is not None and not 1 <= url.port <= 65535
                or url.username is not None or url.password is not None
                or "?" in value["endpoint"] or "#" in value["endpoint"]):
            raise ValueError()
        options = value["options"]
        token_option = "num_predict" if provider == "ollama" else "max_tokens"
        if (type(options) is not dict or type(options.get(token_option)) is not int
                or not 1 <= options[token_option] <= 8192):
            raise ValueError()
        # The adapter owns scalar domains, shared with direct Python callers.
        # This loader additionally requires an explicit output-token budget.
        config_type, model_type = ((OllamaConfig, OllamaModel) if provider == "ollama"
                                   else (OpenAIChatConfig, OpenAIChatModel))
        config = config_type(**{key: child for key, child in value.items() if key not in {"version", "provider"}})
        # Validate complete UTF-8 serialization before a configuration is used.
        json.dumps(config.manifest(), ensure_ascii=False, allow_nan=False).encode("utf-8")
        return model_type(config)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        raise ModelConfigError("INVALID_MODEL_CONFIG") from None


def load_model(path):
    handle = None
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        initial = os.fstat(handle)
        if (not stat.S_ISREG(initial.st_mode) or initial.st_uid != os.getuid()
                or initial.st_mode & 0o077 or initial.st_size > MAX_CONFIG_BYTES):
            raise ModelConfigError("MODEL_CONFIG_NOT_PRIVATE_OR_TOO_LARGE")
        with os.fdopen(handle, "rb") as stream:
            handle = None
            raw = stream.read(MAX_CONFIG_BYTES + 1)
            final = os.fstat(stream.fileno())
        current = os.stat(path, follow_symlinks=False)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if len(raw) > MAX_CONFIG_BYTES or signature(initial) != signature(final) or signature(initial) != signature(current):
            raise ModelConfigError("MODEL_CONFIG_CHANGED_OR_TOO_LARGE")
        return _decode(raw)
    except OSError:
        raise ModelConfigError("MODEL_CONFIG_UNAVAILABLE") from None
    finally:
        if handle is not None:
            os.close(handle)


def inspect_model_config(path):
    """Validate the explicit local CLI policy, without checking server or secret."""
    model = load_model(path)
    return {"schema": "eidolon-model-config-check/1", "status": "VALID_CONFIG",
            "model_id": model.model_id, "manifest": model.config.manifest(),
            "server_contacted": False, "secret_value_read": False,
            "model_available": None, "authorizes_execution": False,
            "limits": ["Configuration syntax and local CLI policy only.",
                       "Server availability, credentials and model quality are not checked."]}


def render_model_config(result):
    from .contracts import encode
    from .presentation import header, message
    return "\n".join((header(title="Configuration du planificateur"),
                      message("OK", "Configuration conforme au contrat local de la CLI."),
                      message("INFO", "Identifiant : " + result["model_id"]),
                      message("INFO", "Manifeste : " + encode(result["manifest"])),
                      message("ATTENTION", "Serveur non contacté, valeur de clé non lue ; disponibilité et qualité du modèle non vérifiées.")))
