# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : model_config.py
# Description : Configuration opérateur privée du planificateur local optionnel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit CLI configuration, never obtained from a model or memory source.

Loading config sends nothing. Execution sends the mission request and recalled
context to the literal loopback endpoint. No remote opt-out or secret is accepted.
"""
import json
import os
import stat
from urllib.parse import urlsplit

from .contracts import ContractError
from .ollama_model import OllamaConfig, OllamaModel

MAX_CONFIG_BYTES = 16384
REQUIRED = {"version", "provider", "endpoint", "model", "options"}
OPTIONAL = {"timeout_seconds", "max_prompt_bytes", "max_response_bytes", "max_output_bytes"}


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
        if (type(value) is not dict or not REQUIRED <= set(value) or not set(value) <= REQUIRED | OPTIONAL
                or type(value["version"]) is not int or value["version"] != 1
                or value["provider"] != "ollama" or type(value["endpoint"]) is not str
                or any(ord(c) <= 32 or ord(c) == 127 for c in value["endpoint"])):
            raise ValueError()
        url = urlsplit(value["endpoint"])
        if url.hostname not in {"127.0.0.1", "::1"} or url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError()
        options = value["options"]
        if (type(options) is not dict or type(options.get("num_predict")) is not int
                or not 1 <= options["num_predict"] <= 8192):
            raise ValueError()
        for field in ("num_ctx", "top_k", "seed"):
            if field in options and (type(options[field]) is not int or not 0 <= options[field] <= 2**31 - 1):
                raise ValueError()
        if "num_ctx" in options and not 256 <= options["num_ctx"] <= 262144:
            raise ValueError()
        if "temperature" in options and not 0 <= options["temperature"] <= 2:
            raise ValueError()
        if "top_p" in options and not 0 < options["top_p"] <= 1:
            raise ValueError()
        config = OllamaConfig(**{key: child for key, child in value.items() if key not in {"version", "provider"}})
        # Validate complete UTF-8 serialization before a configuration is used.
        json.dumps(config.manifest(), ensure_ascii=False, allow_nan=False).encode("utf-8")
        return OllamaModel(config)
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
