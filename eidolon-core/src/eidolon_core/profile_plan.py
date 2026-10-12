# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : profile_plan.py
# Description : Validation pure du plan privé des profils, sans activation G170-A
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Preparation only: does not create sessions, credentials, roles or memory access."""
from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata

from .contracts import ContractError

SCHEMA = "eidolon-user-profile-plan/1"
PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
POLICY = {
    "speaker_recognition": "planned", "face_recognition": "planned",
    "biometric_enrollment": "not_started", "biometric_authorization": False,
    "capture_enabled": False, "memory_scope_default": "private_per_profile",
    "casual_admin_permissions": False,
}


class ProfilePlanError(ContractError):
    pass


def _require(condition, code):
    if not condition:
        raise ProfilePlanError(code)


def _name(value):
    _require(isinstance(value, str) and 1 <= len(value) <= 80
             and value == value.strip()
             and not any(unicodedata.category(c).startswith("C") for c in value),
             "PROFILE_NAME_INVALID")
    return value


def _key(value):
    return unicodedata.normalize("NFKC", value).casefold()


@dataclass(frozen=True)
class PlannedProfile:
    profile_id: str
    display_name: str
    given_name: str | None
    aliases: tuple[str, ...]
    role: str


@dataclass(frozen=True)
class ProfilePlan:
    profiles: tuple[PlannedProfile, ...]
    created_at: str

    def summary(self):
        # Names are private. This summary is safe for installation diagnostics.
        return {"schema": SCHEMA, "status": "PLANNED_NOT_ACTIVE",
                "profiles": len(self.profiles),
                "admins": sum(p.role == "admin" for p in self.profiles),
                "casual": sum(p.role == "casual" for p in self.profiles),
                "runtime_active": False, "biometric_enrollment": "not_started"}


def validate_profile_plan(value):
    """Validate data already read by trusted local code; no I/O or permission grant.

    This v1 bootstrap plan describes exactly one administrator and two casual
    profiles. A later active account schema and authenticated import are separate.
    Alias matching here only detects enrollment collisions; it never authenticates.
    """
    fields = {"schema", "status", "created_at", "source", "runtime_importer_implemented",
              "profiles", "policy"}
    _require(type(value) is dict and set(value) == fields, "PROFILE_PLAN_FIELDS")
    _require(value["schema"] == SCHEMA and value["status"] == "PLANNED_NOT_ACTIVE"
             and value["runtime_importer_implemented"] is False, "PROFILE_PLAN_STATE")
    _require(type(value["source"]) is str and 1 <= len(value["source"]) <= 200,
             "PROFILE_PLAN_SOURCE")
    try:
        stamp = datetime.fromisoformat(value["created_at"])
        _require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
                 "PROFILE_PLAN_DATE")
    except (ValueError, TypeError):
        raise ProfilePlanError("PROFILE_PLAN_DATE") from None
    policy = value["policy"]
    _require(type(policy) is dict and set(policy) == set(POLICY)
             and all(type(policy[k]) is type(v) and policy[k] == v
                     for k, v in POLICY.items()), "PROFILE_PLAN_POLICY")
    rows = value["profiles"]
    _require(type(rows) is list and len(rows) == 3, "PROFILE_PLAN_COUNT")
    profiles, ids, identities = [], set(), {}
    for row in rows:
        _require(type(row) is dict
                 and {"profile_id", "display_name", "role"} <= set(row)
                 and set(row) <= {"profile_id", "display_name", "role", "given_name", "aliases"},
                 "PROFILE_FIELDS")
        pid = row["profile_id"]
        _require(type(pid) is str and PROFILE_ID.fullmatch(pid),
                 "PROFILE_ID_INVALID")
        _require(pid not in ids, "PROFILE_ID_DUPLICATE")
        ids.add(pid)
        _require(type(row["role"]) is str and row["role"] in ("admin", "casual"),
                 "PROFILE_ROLE_INVALID")
        display = _name(row["display_name"])
        given = _name(row["given_name"]) if "given_name" in row else None
        aliases = row.get("aliases", [])
        _require(type(aliases) is list and len(aliases) <= 16, "PROFILE_ALIASES_INVALID")
        aliases = tuple(_name(a) for a in aliases)
        keys = [_key(a) for a in aliases]
        _require(len(keys) == len(set(keys)), "PROFILE_ALIAS_DUPLICATE")
        for label in (display,) + ((given,) if given else ()) + aliases:
            key = _key(label)
            _require(key not in identities or identities[key] == pid, "PROFILE_IDENTITY_COLLISION")
            identities[key] = pid
        profiles.append(PlannedProfile(pid, display, given, aliases, row["role"]))
    _require(sum(p.role == "admin" for p in profiles) == 1, "PROFILE_ADMIN_COUNT")
    return ProfilePlan(tuple(profiles), value["created_at"])
