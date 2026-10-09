# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : dialogue_profiles.py
# Description : Profils de dialogue nommés, choisis explicitement par l'opérateur, jamais par repli (C-TASK-G098)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Named dialogue profiles, configured by the operator in a private file.

The ACTIVE profile is not here: it is the explicit selection recorded in the conversation store
(ConversationStore.select_profile). When the selected profile is absent or cannot be loaded, the turn
is answered UNAVAILABLE: no other profile is ever chosen silently, nothing is downloaded, and the
private path of a model configuration never appears in a message.
"""
import json
import os
import stat

from .conversation import PROFILE_NAME
from .contracts import ContractError

SCHEMA = "eidolon-dialogue-profiles/1"
MAX_BYTES = 16 * 1024
MAX_PROFILES = 16


class DialogueProfiles:
    def __init__(self, factories):
        """factories: {name: callable returning a dialogue model}. Called at most once per name."""
        if not isinstance(factories, dict) or not 1 <= len(factories) <= MAX_PROFILES:
            raise ContractError("INVALID_DIALOGUE_PROFILES: 1 to 16 profiles required")
        for name, factory in factories.items():
            if not isinstance(name, str) or not PROFILE_NAME.fullmatch(name) or not callable(factory):
                raise ContractError("INVALID_DIALOGUE_PROFILES: invalid profile")
        self._factories, self._models = dict(factories), {}

    def names(self):
        return sorted(self._factories)

    def model(self, name):
        """The model of this configured profile, loaded on first use; never another profile's."""
        if name not in self._factories:
            raise ContractError("DIALOGUE_PROFILE_UNAVAILABLE: profile not configured")
        if name not in self._models:
            try:
                self._models[name] = self._factories[name]()
            except Exception:  # noqa: BLE001 - reported by code only: a config path or secret never leaks
                raise ContractError("DIALOGUE_PROFILE_UNAVAILABLE: profile cannot be loaded") from None
        return self._models[name]

    def timeout(self, name):
        """The adapter's own timeout for this profile, when it has one (wall budget, G088-R2)."""
        model = self._models.get(name)
        value = getattr(getattr(getattr(model, "adapter", None), "config", None), "timeout_seconds", None)
        return value if isinstance(value, (int, float)) else None

    @classmethod
    def load(cls, path, catalog):
        """Private profile file: {"schema", "profiles": {name: {"kind": "simulated"} |
        {"kind": "model_config", "path": <private model configuration>}}}."""
        from .dialogue import ChatDialogueModel, SimulatedDialogueModel
        from .model_config import load_model
        raw = _read_private(path)

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        except (ValueError, UnicodeError, RecursionError):
            raise ContractError("INVALID_DIALOGUE_PROFILES: invalid JSON") from None
        if (not isinstance(value, dict) or set(value) != {"schema", "profiles"} or value["schema"] != SCHEMA
                or not isinstance(value["profiles"], dict)):
            raise ContractError("INVALID_DIALOGUE_PROFILES: exact fields required")
        factories = {}
        for name, entry in value["profiles"].items():
            if entry == {"kind": "simulated"}:
                factories[name] = lambda: SimulatedDialogueModel(catalog)
            elif (isinstance(entry, dict) and set(entry) == {"kind", "path"} and entry["kind"] == "model_config"
                  and isinstance(entry["path"], str) and os.path.isabs(entry["path"])):
                factories[name] = (lambda p: lambda: ChatDialogueModel(load_model(p), catalog))(entry["path"])
            else:
                raise ContractError("INVALID_DIALOGUE_PROFILES: invalid profile entry")
        return cls(factories)


def _read_private(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ContractError("DIALOGUE_PROFILES_UNAVAILABLE: profile file unreadable") from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
                or info.st_size > MAX_BYTES):
            raise ContractError("DIALOGUE_PROFILES_UNAVAILABLE: a private regular file of bounded size is required")
        return os.read(fd, MAX_BYTES + 1)
    finally:
        os.close(fd)
