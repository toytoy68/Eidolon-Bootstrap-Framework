# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_proposal.py
# Description : Proposition d'identité voix/visage (eidolon-identity-proposal/1) : états, calibration, fusion, sans aucun droit (G170-C/D)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Pure decision layer of G170-C/D (docs/G170-CD-ENGINES-AND-CONTRACT.md, precisions G172).

A proposal only SUGGESTS a profile. It never opens a session, changes a role, unlocks memory or authorizes
anything: ``grants`` is always empty and ``authorizes_execution`` always false. Profile ids come only from the
server-side enrolment registry of the modality, never from the browser or a model. A score is engine-specific,
not a probability; "known" is impossible without a calibration bound to the model SHA-256 and preprocessing
version ("uncalibrated" otherwise). Thresholds, minimum durations and the post-TTS pause are PARAMETERS to be
measured (G170-F), never constants presented as validated.

Nothing here touches a camera, a microphone, a file or a log: engine adapters hand an Observation in, this
module hands a JSON-able dict out. Vectors never appear in an output or a repr.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
import re

SCHEMA = "eidolon-identity-proposal/1"
MODALITIES = ("voice", "face")
STATES = ("known", "ambiguous", "unknown", "too_short", "silence", "several_people", "no_face", "stale",
          "unavailable", "not_enrolled", "uncalibrated")
PROFILE = re.compile(r"[a-z][a-z0-9-]{1,47}")
SHA256 = re.compile(r"[0-9a-f]{64}")
FUTURE_TOLERANCE = timedelta(seconds=5)
MAX_TEMPLATES = 16                                   # per profile and modality
MAX_PROFILES = 16


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _utc(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(name + " must be an aware UTC datetime")
    return value


@dataclass(frozen=True)
class Calibration:
    """Measured decision parameters, valid ONLY for one model file and one preprocessing version."""
    modality: str
    engine: str
    model_sha256: str
    preprocessing: str
    score_kind: str
    score_bounds: tuple            # engine-specific bounds of the score, e.g. (-1.0, 1.0) for a cosine
    threshold: float
    margin: float                  # minimum gap with the second profile
    threshold_id: str              # reference of the measurement campaign that produced the numbers
    validity_s: float = 30.0       # how long a proposal stays fresh
    min_speech_s: float = 1.5      # voice only: below, "too_short"
    max_duration_s: float = 30.0

    def __post_init__(self):
        if self.modality not in MODALITIES:
            raise ValueError("unknown modality")
        if not SHA256.fullmatch(self.model_sha256 or ""):
            raise ValueError("model_sha256 must be a SHA-256")
        for name in ("engine", "preprocessing", "score_kind", "threshold_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,80}", value):
                raise ValueError("invalid calibration " + name)
        lo, hi = self.score_bounds if isinstance(self.score_bounds, tuple) and len(self.score_bounds) == 2 else (None, None)
        if not (_finite(lo) and _finite(hi) and lo < hi):
            raise ValueError("invalid score bounds")
        if not (_finite(self.threshold) and lo <= self.threshold <= hi and _finite(self.margin) and 0 <= self.margin <= hi - lo):
            raise ValueError("threshold and margin must lie within the score bounds")
        for name in ("validity_s", "min_speech_s", "max_duration_s"):
            if not _finite(getattr(self, name)) or not 0 < getattr(self, name) <= 3600:
                raise ValueError("invalid calibration " + name)


@dataclass(frozen=True)
class EngineInfo:
    name: str
    model_sha256: str
    preprocessing: str


@dataclass(frozen=True)
class Observation:
    """What an engine adapter measured. ``embedding`` is never printed (repr=False)."""
    modality: str
    observed_at: datetime
    engine: EngineInfo
    duration_s: float = 0.0
    speech_s: float | None = None          # voice: speech actually detected (None = not measured)
    silence: bool = False                   # voice: energy heuristic (RMS), NOT a proof of silence
    overlap: bool | None = None             # voice: simultaneous speakers; None = NOT MEASURED
    faces: int | None = None                # face: detected faces
    embedding: tuple | None = field(default=None, repr=False)
    error: str | None = None                # engine failure code (generic)


class Registry:
    """Enrolled templates of ONE modality, built server-side from confirmed profiles (G170-A, Codex)."""

    def __init__(self, modality, templates, *, engine):
        if modality not in MODALITIES or not isinstance(engine, EngineInfo):
            raise ValueError("invalid registry")
        if not isinstance(templates, dict) or len(templates) > MAX_PROFILES:
            raise ValueError("invalid templates")
        clean = {}
        for profile, vectors in templates.items():
            if not isinstance(profile, str) or not PROFILE.fullmatch(profile):
                raise ValueError("invalid profile id")
            if not isinstance(vectors, (list, tuple)) or not 1 <= len(vectors) <= MAX_TEMPLATES:
                raise ValueError("invalid template list")
            clean[profile] = tuple(_unit(v) for v in vectors)
        dims = {len(v) for vs in clean.values() for v in vs}
        if len(dims) > 1:
            raise ValueError("templates of different dimensions")
        self.modality, self.engine, self._templates = modality, engine, clean

    def __repr__(self):                       # never print vectors
        return f"Registry({self.modality}, profiles={sorted(self._templates)})"

    def profiles(self):
        return sorted(self._templates)

    def scores(self, embedding):
        vector = _unit(embedding)
        out = {}
        for profile, templates in self._templates.items():
            if len(templates[0]) != len(vector):
                raise ValueError("embedding dimension mismatch")
            out[profile] = max(sum(a * b for a, b in zip(vector, t)) for t in templates)
        return out


def _unit(values):
    if not isinstance(values, (list, tuple)) or not 2 <= len(values) <= 4096 or not all(_finite(v) for v in values):
        raise ValueError("vector must contain finite numbers")
    norm = math.sqrt(sum(v * v for v in values))
    if not _finite(norm) or norm == 0:
        raise ValueError("vector must have a finite non-zero norm")
    return tuple(v / norm for v in values)


def _proposal(modality, state, *, observed_at=None, valid_until=None, profile_id=None, candidates=(),
              calibration=None, engine=None, reason=None, overlap_measured=None):
    value = {"schema": SCHEMA, "modality": modality, "state": state,
             "profile_id": profile_id if state == "known" else None,
             "candidates": [dict(c) for c in candidates],
             "score_kind": calibration.score_kind if calibration else None,
             "threshold_id": calibration.threshold_id if calibration else None,
             "observed_at": observed_at.isoformat() if observed_at else None,
             "valid_until": valid_until.isoformat() if valid_until else None,
             "engine": ({"name": engine.name, "model_sha256": engine.model_sha256, "preprocessing": engine.preprocessing}
                        if engine else None),
             "reason": reason, "grants": [], "authorizes_execution": False}
    if modality == "voice":
        value["overlap_measured"] = overlap_measured
    return value


def propose(observation, registry, calibration, *, now, speaking_until=None, ignore_after_tts_s=1.0):
    """One modality -> one eidolon-identity-proposal/1 dict. Never raises on engine data: bad data is a state."""
    _utc(now, "now")
    modality = getattr(observation, "modality", None)
    if modality not in MODALITIES:
        raise ValueError("unknown modality")
    if observation.error or observation.engine is None:
        return _proposal(modality, "unavailable", reason=observation.error or "engine_missing")
    try:
        observed = _utc(observation.observed_at, "observed_at")
    except ValueError:
        return _proposal(modality, "unavailable", reason="invalid_date")
    if observed > now + FUTURE_TOLERANCE:
        return _proposal(modality, "unavailable", reason="clock_skew")
    engine = observation.engine
    # Eidolon's own voice (TTS) must never be recognised as a person: ignored while speaking + a pause.
    if modality == "voice" and speaking_until is not None and observed <= _utc(speaking_until, "speaking_until") + timedelta(seconds=ignore_after_tts_s):
        return _proposal(modality, "unavailable", observed_at=observed, engine=engine, reason="eidolon_speaking")
    if (calibration is None or calibration.modality != modality or calibration.model_sha256 != engine.model_sha256
            or calibration.preprocessing != engine.preprocessing or calibration.engine != engine.name):
        return _proposal(modality, "uncalibrated", observed_at=observed, engine=engine, calibration=calibration)
    valid_until = observed + timedelta(seconds=calibration.validity_s)
    common = dict(observed_at=observed, valid_until=valid_until, engine=engine, calibration=calibration)
    overlap_measured = None if modality != "voice" else observation.overlap is not None
    if modality == "voice":
        common["overlap_measured"] = overlap_measured
    if now > valid_until:
        return _proposal(modality, "stale", **common)
    if not _finite(observation.duration_s) or not 0 <= observation.duration_s <= calibration.max_duration_s:
        return _proposal(modality, "unavailable", reason="invalid_duration", **common)
    if modality == "voice":
        if observation.silence:
            return _proposal(modality, "silence", reason="energy_heuristic", **common)
        if observation.overlap is True:                  # only a component that MEASURES overlap may say so
            return _proposal(modality, "several_people", **common)
        if observation.speech_s is None or not _finite(observation.speech_s) or observation.speech_s < calibration.min_speech_s:
            return _proposal(modality, "too_short", **common)
    else:
        if type(observation.faces) is not int or observation.faces < 0:
            return _proposal(modality, "unavailable", reason="faces_not_measured", **common)
        if observation.faces == 0:
            return _proposal(modality, "no_face", **common)
        if observation.faces > 1:
            return _proposal(modality, "several_people", **common)
    if registry is None or registry.modality != modality or not registry.profiles():
        return _proposal(modality, "not_enrolled", **common)
    if registry.engine != engine:
        return _proposal(modality, "uncalibrated", reason="registry_built_with_another_model", **common)
    try:
        scores = registry.scores(observation.embedding)
    except (ValueError, TypeError):
        return _proposal(modality, "unavailable", reason="invalid_embedding", **common)
    lo, hi = calibration.score_bounds
    if not all(_finite(s) and lo - 1e-9 <= s <= hi + 1e-9 for s in scores.values()):
        return _proposal(modality, "unavailable", reason="score_out_of_bounds", **common)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    candidates = [{"profile_id": p, "score": round(s, 4)} for p, s in ranked[:3]]
    best, best_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else lo
    if best_score < calibration.threshold:
        return _proposal(modality, "unknown", candidates=candidates, **common)
    if best_score - second < calibration.margin:
        return _proposal(modality, "ambiguous", candidates=candidates, **common)
    return _proposal(modality, "known", profile_id=best, candidates=candidates, **common)


_DOUBT = {"ambiguous", "several_people", "unknown"}      # a face/voice that contradicts or doubts
_SILENT = {"unavailable", "stale", "not_enrolled", "uncalibrated", "no_face", "too_short", "silence"}


def _fresh(proposal, now):
    """Recompute staleness at fusion time (G172 point 2): a proposal does not stay fresh by itself."""
    if proposal is None:
        return None
    if proposal.get("schema") != SCHEMA or proposal.get("grants") != [] or proposal.get("authorizes_execution") is not False:
        raise ValueError("not an identity proposal")
    until = proposal.get("valid_until")
    if until is not None and datetime.fromisoformat(until) < now and proposal["state"] not in _SILENT - {"stale"}:
        return dict(proposal, state="stale", profile_id=None)
    return proposal


def fuse(voice, face, *, now):
    """Voice + face -> one proposal. Disagreement is ambiguous; one sensor is enough; nothing grants rights."""
    _utc(now, "now")
    voice, face = _fresh(voice, now), _fresh(face, now)
    states = {m: (p["state"] if p else "unavailable") for m, p in (("voice", voice), ("face", face))}
    known = {m: p["profile_id"] for m, p in (("voice", voice), ("face", face)) if p and p["state"] == "known"}
    basis = sorted(m for m, s in states.items() if s not in _SILENT)
    if len(known) == 2:
        if known["voice"] == known["face"]:
            return _fused("known", known["voice"], ["face", "voice"], states)
        return _fused("ambiguous", None, ["face", "voice"], states, reason="voice_face_disagree")
    if len(known) == 1:
        (modality, profile), = known.items()
        other = states["face" if modality == "voice" else "voice"]
        if other in _DOUBT:                                # G172 point 3: known A + doubt = ambiguous
            return _fused("ambiguous", None, basis, states, reason="other_modality_" + other)
        return _fused("known", profile, [modality], states)
    for state in ("several_people", "ambiguous", "unknown"):
        if state in states.values():
            return _fused(state, None, basis, states)
    return _fused("unavailable", None, [], states)


def _fused(state, profile, basis, states, reason=None):
    return {"schema": SCHEMA, "modality": "fused", "state": state, "profile_id": profile if state == "known" else None,
            "basis": basis, "modalities": dict(states), "reason": reason, "grants": [], "authorizes_execution": False}


class EphemeralCapture:
    """Raw audio/image held in memory only while an engine needs it, wiped on exit, error or cancel (G172 point 5)."""

    def __init__(self, data):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("raw capture must be bytes")
        self._buffer = bytearray(data)

    def __enter__(self):
        return memoryview(self._buffer)

    def __exit__(self, *exc):
        self.wipe()
        return False

    def wipe(self):
        for i in range(len(self._buffer)):
            self._buffer[i] = 0
        self._buffer = bytearray()

    def __len__(self):
        return len(self._buffer)

    def __repr__(self):
        return f"EphemeralCapture({len(self._buffer)} bytes)"
