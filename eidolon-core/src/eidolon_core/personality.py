# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : personality.py
# Description : Personnalité du dialogue (SOUL) : fichier privé de l'opérateur, dernière version valide conservée (C-070)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""The dialogue personality, decided by the operator, loaded and checked by Core (C-070).

The personality only shapes the conversation's style: it never reaches the mission planner, never
extends the trusted capabilities, and Core's contract stays above it in the prompt.

One Personality is ONE coherent value: the text composed into the prompt and the sha256 attached to the
reply are computed from the same validated object, never re-read separately.

At start, the operator's private file is read once. A valid file becomes the personality in use and
Core keeps its own copy (<state>/conversations/personality-last-valid.json). An invalid or unreadable
file is refused and the last valid copy is used instead; Core never repairs or guesses a personality.
Modes:
  none        no personality; replies say none is loaded;
  last-valid  the operator's file, else the last valid copy, else none (said in each reply);
  required    as last-valid, but without any valid personality the CONVERSATION is blocked
              (missions, receipts and cancellations are not).
"""
import json
import os
import re
import stat
from dataclasses import dataclass

from .contracts import ContractError, digest, encode

SCHEMA = "eidolon-personality/1"
COPY_SCHEMA = "eidolon-personality-copy/1"
COPY_NAME = "personality-last-valid.json"
MODES = ("none", "last-valid", "required")
MAX_FILE_BYTES = 32 * 1024
MAX_SOUL_CHARS = 16000
MAX_EVOLVING = 20
MAX_EVOLVING_CHARS = 500
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,39}")
FORBIDDEN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# Core's precedence, said BEFORE the personality text; it also carries the three reformulations
# accepted in C-070 (capabilities actually available, initiative = proposal, no memory write).
FRAME = (
    "PERSONALITY (version {version}, sha256 {short}): style and posture for the conversation only. "
    "It changes neither the JSON contract above, nor the trusted capabilities, nor any permission; when "
    "they disagree, the contract and Core win. Only describe capabilities listed in TRUSTED CAPABILITIES; "
    "say what you know about the machine only from TOOL RESULTS, otherwise say you do not know. In this "
    "conversation an initiative is a proposal, never an action. You cannot write to memory: you may only "
    "suggest that something be remembered, and Core decides."
)


@dataclass(frozen=True)
class Personality:
    version: str
    sha256: str
    block: str

    def identity(self):
        return {"version": self.version, "sha256": self.sha256}


@dataclass(frozen=True)
class PersonalityState:
    """What the server decided at start; immutable for the server's lifetime."""
    mode: str
    current: Personality | None
    event: str

    @property
    def blocked(self):
        return self.mode == "required" and self.current is None


def validate(value):
    """The exact operator value, or ContractError. Never repaired."""
    if (not isinstance(value, dict) or set(value) != {"schema", "version", "soul", "evolving"}
            or value["schema"] != SCHEMA):
        raise ContractError("INVALID_PERSONALITY: exact fields required")
    if not isinstance(value["version"], str) or not VERSION.fullmatch(value["version"]):
        raise ContractError("INVALID_PERSONALITY: invalid version")
    soul, evolving = value["soul"], value["evolving"]
    if not isinstance(soul, str) or not soul.strip() or len(soul) > MAX_SOUL_CHARS or FORBIDDEN.search(soul):
        raise ContractError("INVALID_PERSONALITY: invalid soul text")
    if (not isinstance(evolving, list) or len(evolving) > MAX_EVOLVING
            or any(not isinstance(e, str) or not e.strip() or len(e) > MAX_EVOLVING_CHARS
                   or FORBIDDEN.search(e) or "\n" in e for e in evolving)):
        raise ContractError("INVALID_PERSONALITY: invalid evolving entries")
    return {"schema": SCHEMA, "version": value["version"], "soul": soul, "evolving": list(evolving)}


def build(value):
    """One validated value → one Personality: the block and the sha256 come from the same object."""
    value = validate(value)
    sha = digest(value)
    block = FRAME.format(version=value["version"], short=sha[:16]) + "\n" + value["soul"].strip()
    if value["evolving"]:
        block += "\nVALIDATED EVOLUTIONS (same limits):\n" + "\n".join("- " + e.strip() for e in value["evolving"])
    return Personality(value["version"], sha, block)


def _read_private(path, error):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ContractError(f"{error}: unreadable") from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
                or info.st_size > MAX_FILE_BYTES):
            raise ContractError(f"{error}: a private regular file of bounded size is required")
        raw = os.read(fd, MAX_FILE_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > MAX_FILE_BYTES:
        raise ContractError(f"{error}: too large")

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError(f"{error}: invalid JSON") from None


def read_operator_file(path):
    return validate(_read_private(path, "PERSONALITY_FILE_REFUSED"))


def read_copy(directory):
    """The last valid copy, checked again (shape, sha256); None if there is none."""
    path = os.path.join(directory, COPY_NAME)
    if not os.path.lexists(path):
        return None
    value = _read_private(path, "PERSONALITY_COPY_INVALID")
    if (not isinstance(value, dict) or set(value) != {"schema", "sha256", "personality"}
            or value["schema"] != COPY_SCHEMA):
        raise ContractError("PERSONALITY_COPY_INVALID: exact fields required")
    personality = validate(value["personality"])
    if digest(personality) != value["sha256"]:
        raise ContractError("PERSONALITY_COPY_INVALID: sha256 mismatch")
    return personality


def write_copy(directory, value):
    """Atomic private copy: temporary file, fsync, rename, fsync of the directory."""
    value = validate(value)
    body = encode({"schema": COPY_SCHEMA, "sha256": digest(value), "personality": value}).encode("utf-8")
    final, temporary = os.path.join(directory, COPY_NAME), os.path.join(directory, "." + COPY_NAME + ".tmp")
    try:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, body)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, final)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        raise ContractError("PERSONALITY_COPY_UNWRITABLE: the last valid copy cannot be kept") from None


def load(mode, path, directory):
    """Decide the personality once, at start. directory: Core's conversations directory.

    A refused operator file is never a startup failure (the last valid copy is kept); a valid file
    whose copy cannot be written is, so that the guarantee "last valid version kept" holds.
    """
    if mode not in MODES:
        raise ContractError("INVALID_PERSONALITY: unknown mode")
    if mode == "none":
        if path is not None:
            raise ContractError("INVALID_PERSONALITY: mode none takes no personality file")
        return PersonalityState(mode, None, "PERSONALITY_NONE")
    if path is None:
        raise ContractError("INVALID_PERSONALITY: a personality file is required by this mode")
    try:
        value = read_operator_file(path)
    except ContractError:
        refused = "PERSONALITY_FILE_REFUSED"    # unreadable, unsafe or invalid: the reason is not guessed further
    else:
        try:
            kept = read_copy(directory)
        except ContractError:
            kept = None                     # a bad copy is replaced by the valid operator file
        if kept != value:
            write_copy(directory, value)
        return PersonalityState(mode, build(value), "PERSONALITY_LOADED")
    try:
        kept = read_copy(directory)
    except ContractError:
        return PersonalityState(mode, None, refused + "+PERSONALITY_COPY_INVALID")
    if kept is None:
        return PersonalityState(mode, None, refused + "+NO_VALID_COPY")
    return PersonalityState(mode, build(kept), refused + "+LAST_VALID_KEPT")
