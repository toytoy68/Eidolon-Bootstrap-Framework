# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_engines.py
# Description : Adaptateurs isolés voix/visage (G170-C/D) : modèle vérifié par SHA-256, exécuteurs injectés, capture effacée
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Isolated engine adapters for G170-C/D. They turn a raw capture into an ``identity_proposal.Observation``.

Nothing here is wired to a route, a service or a sensor, and nothing is downloaded: the real ONNX runners
(WeSpeaker for the voice, YuNet + SFace for the face) are INJECTED callables, to be written and measured in
G170-F once agreed. An adapter only accepts a model file whose SHA-256 matches the expected one, wipes the raw
capture on exit, error or cancel, and reports engine failures as a generic code (never a message, a path or a
vector). The silence flag is an energy heuristic (RMS), not a proof; overlap stays None (= not measured) unless
an injected component really measures it.
"""
from datetime import datetime, timezone
import hashlib
import math
import os
import stat

from .identity_proposal import SHA256, EngineInfo, EphemeralCapture, Observation

MAX_MODEL_BYTES = 512 * 1024 * 1024
MAX_AUDIO_BYTES = 16000 * 2 * 30                    # 30 s of 16 kHz mono PCM16
MAX_IMAGE_BYTES = 8 * 1024 * 1024
SAMPLE_RATE = 16000


class ModelRejected(ValueError):
    """The model file is missing, not a regular file, too large, or not the expected one."""


def verify_model(path, expected_sha256, *, name, preprocessing):
    """Hash a local model file (never fetched) and bind it to an EngineInfo. Symlinks are refused."""
    if not SHA256.fullmatch(expected_sha256 or ""):
        raise ModelRejected("expected_sha256 must be a SHA-256")
    try:
        info = os.lstat(path)
    except OSError:
        raise ModelRejected("model_missing") from None
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_MODEL_BYTES:
        raise ModelRejected("model_not_a_regular_file")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ModelRejected("model_sha256_mismatch")
    return EngineInfo(name=name, model_sha256=expected_sha256, preprocessing=preprocessing)


def _now(clock):
    value = clock()
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("clock must return an aware datetime")
    return value.astimezone(timezone.utc)


def _vector(value):
    out = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in out):
        raise ValueError("non-finite embedding")
    return out


def pcm16_rms(view, frame=320):
    """Per-frame RMS (20 ms at 16 kHz) of little-endian mono PCM16, without copying the capture elsewhere."""
    samples = view.cast("h") if len(view) % 2 == 0 else None
    if samples is None:
        raise ValueError("PCM16 needs an even byte count")
    out = []
    for start in range(0, len(samples), frame):
        part = samples[start:start + frame]
        out.append(math.sqrt(sum(s * s for s in part) / len(part)) if len(part) else 0.0)
    return out


class VoiceAdapter:
    """Voice capture -> Observation. ``runner(samples, rate) -> vector`` is the injected speaker-embedding model."""

    def __init__(self, runner, engine, *, speech_rms=500.0, clock=lambda: datetime.now(timezone.utc), overlap=None):
        if not callable(runner) or not isinstance(engine, EngineInfo):
            raise ValueError("invalid voice adapter")
        if overlap is not None and not callable(overlap):
            raise ValueError("overlap must be a measuring component or None")
        self._runner, self.engine, self._speech_rms, self._clock, self._overlap = runner, engine, speech_rms, clock, overlap

    def observe(self, pcm16):
        observed_at = _now(self._clock)
        if not isinstance(pcm16, (bytes, bytearray)) or len(pcm16) > MAX_AUDIO_BYTES or len(pcm16) % 2:
            return Observation("voice", observed_at, self.engine, error="invalid_capture")
        with EphemeralCapture(pcm16) as view:
            try:
                rms = pcm16_rms(view)
                duration = len(view) / 2 / SAMPLE_RATE
                speech_s = sum(1 for r in rms if r >= self._speech_rms) * 0.02
                if speech_s == 0:
                    return Observation("voice", observed_at, self.engine, duration_s=duration, speech_s=0.0, silence=True)
                overlap = None if self._overlap is None else bool(self._overlap(view.cast("h"), SAMPLE_RATE))
                embedding = _vector(self._runner(view.cast("h"), SAMPLE_RATE))
            except Exception:                                  # engine failure: generic code, nothing else kept
                return Observation("voice", observed_at, self.engine, error="engine_failed")
        return Observation("voice", observed_at, self.engine, duration_s=duration, speech_s=round(speech_s, 2),
                           overlap=overlap, embedding=embedding)


class FaceAdapter:
    """Image -> Observation. ``detector(image) -> [box, ...]`` (YuNet), ``embedder(image, box) -> vector`` (SFace)."""

    def __init__(self, detector, embedder, engine, *, clock=lambda: datetime.now(timezone.utc)):
        if not callable(detector) or not callable(embedder) or not isinstance(engine, EngineInfo):
            raise ValueError("invalid face adapter")
        self._detector, self._embedder, self.engine, self._clock = detector, embedder, engine, clock

    def observe(self, image):
        observed_at = _now(self._clock)
        if not isinstance(image, (bytes, bytearray)) or not 0 < len(image) <= MAX_IMAGE_BYTES:
            return Observation("face", observed_at, self.engine, error="invalid_capture")
        with EphemeralCapture(image) as view:
            try:
                boxes = list(self._detector(view))
                if len(boxes) != 1:                             # 0 = no_face, >1 = several_people: no embedding
                    return Observation("face", observed_at, self.engine, faces=len(boxes))
                embedding = _vector(self._embedder(view, boxes[0]))
            except Exception:
                return Observation("face", observed_at, self.engine, error="engine_failed")
        return Observation("face", observed_at, self.engine, faces=1, embedding=embedding)
