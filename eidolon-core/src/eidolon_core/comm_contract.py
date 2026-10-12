# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_contract.py
# Description : Contrat commun voix/caméra/vision : erreurs, états, audio borné, une requête par périphérique (G146)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Shared rules of the communication subsystem (docs/COMMUNICATION.md §2).

Everything here is in memory: audio and images are checked, used, then dropped. Nothing is written,
logged as content, or sent outside the loopback service. Results are unverified observations.
"""
import io
import threading
import wave
from contextlib import contextmanager

from .contracts import ContractError

STATES = ("unavailable", "permission_denied", "disabled", "ready", "capturing", "processing", "busy", "stopped")
KINDS = ("microphone", "speaker", "camera")

AUDIO_RATE = 16000
AUDIO_MAX_SECONDS = 30
AUDIO_MAX_BYTES = 1024 * 1024


class CommError(ContractError):
    """code: COMM_DISABLED, DEVICE_BUSY, PAYLOAD_TOO_LARGE, AUDIO_FORMAT_UNSUPPORTED, ENGINE_UNAVAILABLE,
    TIMEOUT, CANCELLED, INVALID_REQUEST (docs/COMMUNICATION.md §2.4)."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def read_wav(data):
    """Mono 16-bit PCM at 16 kHz, at most 30 s and 1 MiB: (pcm bytes, duration in seconds). Never repaired."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise CommError("AUDIO_FORMAT_UNSUPPORTED", "WAV bytes required")
    if len(data) > AUDIO_MAX_BYTES:
        raise CommError("PAYLOAD_TOO_LARGE", "audio above 1 MiB")
    try:
        with wave.open(io.BytesIO(bytes(data)), "rb") as audio:
            channels, width, rate, frames = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                                             audio.getnframes())
            if audio.getcomptype() != "NONE":
                raise CommError("AUDIO_FORMAT_UNSUPPORTED", "uncompressed PCM required")
            pcm = audio.readframes(frames)
    except (wave.Error, EOFError):
        raise CommError("AUDIO_FORMAT_UNSUPPORTED", "not a readable WAV file") from None
    if (channels, width, rate) != (1, 2, AUDIO_RATE):
        raise CommError("AUDIO_FORMAT_UNSUPPORTED", "mono, 16-bit, 16 kHz required")
    if len(pcm) != frames * 2:
        raise CommError("AUDIO_FORMAT_UNSUPPORTED", "truncated audio")
    duration = frames / AUDIO_RATE
    if duration > AUDIO_MAX_SECONDS:
        raise CommError("PAYLOAD_TOO_LARGE", "audio above 30 seconds")
    return pcm, duration


def write_wav(pcm, rate=AUDIO_RATE):
    """Mono 16-bit PCM bytes → WAV bytes (for synthesis output and tests)."""
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return out.getvalue()


class DeviceGate:
    """At most one active request per (client, device kind); a second one is refused, never queued."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = {}

    @contextmanager
    def hold(self, client_id, kind):
        if kind not in KINDS or not isinstance(client_id, str) or not client_id:
            raise CommError("INVALID_REQUEST", "client and device kind required")
        key = (client_id, kind)
        cancel = threading.Event()
        with self._lock:
            if key in self._active:
                raise CommError("DEVICE_BUSY", f"a {kind} request is already active")
            self._active[key] = cancel
        try:
            yield cancel
        finally:
            with self._lock:
                self._active.pop(key, None)

    def cancel(self, client_id, kind):
        """Stop the active request of this client for this device, if any. True if one was signalled."""
        with self._lock:
            event = self._active.get((client_id, kind))
        if event is None:
            return False
        event.set()
        return True

    def active(self, client_id, kind):
        with self._lock:
            return (client_id, kind) in self._active
