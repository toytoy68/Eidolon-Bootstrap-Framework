# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : targets.py
# Description : Catalogue pur de cibles et de capacités déclarées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Configured targets and declared capabilities. Pure data, no I/O.

A declared capability is neither a permission nor proof of availability.
Destinations and scopes are operator intentions recorded for review; nothing
here resolves a name, opens a socket, mounts a share or reads a file.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .contracts import ContractError, digest, encode, snapshot

SCHEMA = "targets/1"
KINDS = ("web_public", "lan_service", "nas_storage", "windows_session")
# Ordered from harmless to dangerous; the reconciliation rules will depend on it.
EFFECT_CLASSES = ("none", "local_read", "egress_read", "mutation")

MAX_TARGETS = 64
MAX_ALIASES = 16
MAX_CAPABILITIES = 32
MAX_SECRET_REFS = 8
MAX_TEXT = 200
MAX_REFERENCE = 200
MAX_SCOPE = 4000

TARGET_ID = re.compile(r"[a-z][a-z0-9-]{0,62}")
CAPABILITY_NAME = re.compile(r"[a-z][a-z0-9_]{0,30}(\.[a-z][a-z0-9_]{0,30}){1,3}")
# A secret reference is a name resolved later by the worker, never a value:
# no separators that could carry "user:password", URLs or paths.
SECRET_NAME = re.compile(r"[a-z][a-z0-9_-]{0,62}")

TARGET_KEYS = {"id", "name", "kind", "aliases", "destination", "capabilities", "secret_refs"}
CAPABILITY_KEYS = {"name", "effect", "scope"}


def _text(value, label, limit=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContractError(f"{label} must be a non-empty string of at most {limit} characters")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value):
        raise ContractError(f"{label} contains control or invisible characters")
    return value


def normalize(reference):
    """Matching form of a target reference: NFKC, case-folded, trimmed."""
    return unicodedata.normalize("NFKC", reference).casefold().strip()


@dataclass(frozen=True)
class Capability:
    name: str
    effect: str
    scope: dict  # Declared intention (folders, endpoints); not enforcement.

    def manifest(self):
        return {"name": self.name, "effect": self.effect, "scope": self.scope}


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    kind: str
    aliases: tuple[str, ...]
    destination: str | None  # Declared, never resolved or contacted here.
    capabilities: tuple[Capability, ...]
    secret_refs: tuple[tuple[str, str], ...]  # (purpose, secret name)

    def capability(self, name):
        return next((c for c in self.capabilities if c.name == name), None)

    def manifest(self):
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "aliases": list(self.aliases), "destination": self.destination,
                "capabilities": [c.manifest() for c in self.capabilities],
                "secret_refs": dict(self.secret_refs)}


@dataclass(frozen=True)
class Lookup:
    """Outcome of a lookup. Only FOUND carries a target; nothing is guessed."""
    status: str  # FOUND, TARGET_ABSENT, TARGET_AMBIGUOUS, CAPABILITY_ABSENT
    reference: str
    target: Target | None = None
    capability: Capability | None = None
    candidates: tuple[str, ...] = ()


def _capability(raw, target_id):
    if not isinstance(raw, dict) or set(raw) - CAPABILITY_KEYS or not {"name", "effect"} <= set(raw):
        raise ContractError(f"{target_id}: capability needs name, effect and optional scope only")
    name = raw["name"]
    if not isinstance(name, str) or not CAPABILITY_NAME.fullmatch(name):
        raise ContractError(f"{target_id}: invalid capability name")
    if raw["effect"] not in EFFECT_CLASSES:
        raise ContractError(f"{target_id}/{name}: effect must be one of {', '.join(EFFECT_CLASSES)}")
    scope = raw.get("scope", {})
    if not isinstance(scope, dict):
        raise ContractError(f"{target_id}/{name}: scope must be an object")
    if len(encode(scope)) > MAX_SCOPE:
        raise ContractError(f"{target_id}/{name}: scope too large")
    return Capability(name, raw["effect"], snapshot(scope))


def _target(raw):
    if not isinstance(raw, dict) or set(raw) - TARGET_KEYS or not {"id", "name", "kind"} <= set(raw):
        raise ContractError("target needs id, name, kind and only known fields")
    identity = raw["id"]
    if not isinstance(identity, str) or not TARGET_ID.fullmatch(identity):
        raise ContractError("target id must match [a-z][a-z0-9-]{0,62}")
    name = _text(raw["name"], f"{identity}: name")
    if raw["kind"] not in KINDS:
        raise ContractError(f"{identity}: kind must be one of {', '.join(KINDS)}")
    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list) or len(aliases) > MAX_ALIASES:
        raise ContractError(f"{identity}: at most {MAX_ALIASES} aliases")
    aliases = sorted({normalize(_text(a, f"{identity}: alias")) for a in aliases} - {identity})
    destination = raw.get("destination")
    if destination is not None:
        destination = _text(destination, f"{identity}: destination", 500)
    capabilities = raw.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) > MAX_CAPABILITIES:
        raise ContractError(f"{identity}: at most {MAX_CAPABILITIES} capabilities")
    capabilities = [_capability(c, identity) for c in capabilities]
    if len({c.name for c in capabilities}) != len(capabilities):
        raise ContractError(f"{identity}: duplicate capability")
    secrets = raw.get("secret_refs", {})
    if not isinstance(secrets, dict) or len(secrets) > MAX_SECRET_REFS:
        raise ContractError(f"{identity}: secret_refs must map at most {MAX_SECRET_REFS} purposes to names")
    for purpose, secret in secrets.items():
        if not SECRET_NAME.fullmatch(purpose) or not isinstance(secret, str) or not SECRET_NAME.fullmatch(secret):
            raise ContractError(f"{identity}: secret references are names, never values")
    return Target(identity, name, raw["kind"], tuple(aliases), destination,
                  tuple(sorted(capabilities, key=lambda c: c.name)), tuple(sorted(secrets.items())))


class Catalog:
    """Immutable, validated catalog. Order of the configuration is irrelevant."""

    def __init__(self, targets):
        self._targets = {t.id: t for t in sorted(targets, key=lambda t: t.id)}
        self._names = {}
        for target in self._targets.values():
            for key in {target.id, *target.aliases}:
                self._names.setdefault(key, set()).add(target.id)

    @classmethod
    def from_config(cls, config):
        config = snapshot(config)
        if not isinstance(config, dict) or set(config) != {"schema", "targets"}:
            raise ContractError("catalog needs schema and targets only")
        if config["schema"] != SCHEMA:
            raise ContractError(f"unsupported catalog schema, expected {SCHEMA}")
        raw = config["targets"]
        if not isinstance(raw, list) or len(raw) > MAX_TARGETS:
            raise ContractError(f"catalog holds at most {MAX_TARGETS} targets")
        targets = [_target(t) for t in raw]
        ids = [t.id for t in targets]
        if len(set(ids)) != len(ids):
            raise ContractError("duplicate target id")
        for target in targets:
            # An alias equal to another target's id would make that id ambiguous.
            clash = set(target.aliases) & (set(ids) - {target.id})
            if clash:
                raise ContractError(f"{target.id}: alias equals another target id: {sorted(clash)[0]}")
        return cls(targets)

    def manifest(self):
        return {"schema": SCHEMA, "targets": [t.manifest() for t in self._targets.values()]}

    def fingerprint(self):
        return digest(self.manifest())

    def get(self, identity):
        return self._targets.get(identity)

    def resolve(self, reference):
        """Resolve an id or alias; an ambiguous alias never picks a candidate."""
        reference = _text(reference, "target reference", MAX_REFERENCE)
        matches = sorted(self._names.get(normalize(reference), ()))
        if not matches:
            return Lookup("TARGET_ABSENT", reference)
        if len(matches) > 1:
            return Lookup("TARGET_AMBIGUOUS", reference, candidates=tuple(matches))
        return Lookup("FOUND", reference, target=self._targets[matches[0]])

    def lookup(self, reference, capability):
        """Resolve a target and one of its declared capabilities."""
        found = self.resolve(reference)
        if found.status != "FOUND":
            return found
        if not isinstance(capability, str) or len(capability) > MAX_TEXT:
            raise ContractError("capability reference must be a bounded string")
        declared = found.target.capability(capability)
        if declared is None:
            return Lookup("CAPABILITY_ABSENT", found.reference, target=found.target)
        return Lookup("FOUND", found.reference, target=found.target, capability=declared)
