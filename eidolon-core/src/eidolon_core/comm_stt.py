# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_stt.py
# Description : Transcription locale (faster-whisper ou simulateur), bornée, annulable, sans permission (G147)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Speech to text, on the server, from a bounded WAV (comm_contract.read_wav).

The transcript is only TEXT: the page shows it, the user may correct it, then sends it as a normal
conversation turn. It grants nothing and never submits a mission. Audio is never stored.

Engines:
- FasterWhisperSTT: a CTranslate2 Whisper model already present in a LOCAL directory (model.bin).
  Never a model name, so nothing is ever downloaded (local_files_only). CPU, bounded threads.
- SimulatedSTT: deterministic stand-in for tests and container recipes; never presented as a model.
"""
import array
import hashlib
import math
import os
import threading
import time

from .comm_contract import CommError, DeviceGate, read_wav

MAX_SEGMENTS = 200
SILENCE_RMS = 200          # 16-bit samples; below this the audio is treated as silence


def rms(pcm):
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class SimulatedSTT:
    """Silence gives an empty transcript; known audio (by sha256) gives its scripted text."""
    engine, model = "simulated", "simulated-stt/1"

    def __init__(self, scripted=None):
        self.scripted = dict(scripted or {})

    def transcribe(self, pcm, duration, cancel, deadline):
        if cancel.is_set():
            raise CommError("CANCELLED")
        if rms(pcm) < SILENCE_RMS:
            return []
        text = self.scripted.get(hashlib.sha256(pcm).hexdigest(), f"[parole simulée, {duration:.1f} s]")
        return [{"start": 0.0, "end": round(duration, 2), "text": text}]


class FasterWhisperSTT:
    """faster-whisper on CPU, loaded once on first use from a local CTranslate2 directory."""
    engine = "faster-whisper"

    def __init__(self, model_dir, *, compute_type="int8", threads=2, beam_size=1, vad=False):
        if (not isinstance(model_dir, str) or not os.path.isabs(model_dir)
                or not os.path.isfile(os.path.join(model_dir, "model.bin"))):
            raise CommError("ENGINE_UNAVAILABLE", "a local CTranslate2 Whisper directory (model.bin) is required")
        if type(threads) is not int or not 1 <= threads <= 16 or type(beam_size) is not int or not 1 <= beam_size <= 5:
            raise CommError("INVALID_REQUEST", "threads 1-16, beam size 1-5")
        self.model_dir, self.compute_type = model_dir, compute_type
        self.threads, self.beam_size, self.vad = threads, beam_size, bool(vad)
        self.model = "faster-whisper:" + os.path.basename(os.path.normpath(model_dir))
        self._loaded, self._load_lock = None, threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._loaded is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    raise CommError("ENGINE_UNAVAILABLE", "faster-whisper is not installed") from None
                self._loaded = WhisperModel(self.model_dir, device="cpu", compute_type=self.compute_type,
                                            cpu_threads=self.threads, local_files_only=True)
            return self._loaded

    def transcribe(self, pcm, duration, cancel, deadline):
        model = self._load()                             # ENGINE_UNAVAILABLE if faster-whisper is absent
        import numpy                                     # installed with faster-whisper
        audio = numpy.frombuffer(pcm, dtype=numpy.int16).astype(numpy.float32) / 32768.0
        segments, _info = model.transcribe(audio, language="fr", beam_size=self.beam_size,
                                           vad_filter=self.vad, condition_on_previous_text=False)
        out = []
        for segment in segments:                         # lazy generator: checked between segments
            if cancel.is_set():
                raise CommError("CANCELLED")
            if time.monotonic() > deadline:
                raise CommError("TIMEOUT", "transcription took too long")
            out.append({"start": round(segment.start, 2), "end": round(segment.end, 2), "text": segment.text.strip()})
            if len(out) >= MAX_SEGMENTS:
                break
        return out


class SpeechToText:
    """One transcription per client at a time (DeviceGate), and one engine call at a time overall."""

    def __init__(self, engine, *, gate=None, time_budget=60.0):
        self.engine, self.gate = engine, gate or DeviceGate()
        self.time_budget = time_budget
        self._engine_lock = threading.Lock()

    def status(self):
        return {"engine": self.engine.engine, "model": self.engine.model,
                "state": "ready", "language": "fr", "limits": {"seconds": 30, "bytes": 1024 * 1024}}

    def transcribe(self, client_id, wav):
        with self.gate.hold(client_id, "microphone") as cancel:
            pcm, duration = read_wav(wav)
            if not self._engine_lock.acquire(blocking=False):
                raise CommError("DEVICE_BUSY", "the transcription engine is busy")
            started = time.monotonic()
            try:
                segments = self.engine.transcribe(pcm, duration, cancel, started + self.time_budget)
            finally:
                self._engine_lock.release()
            text = " ".join(s["text"] for s in segments if s["text"]).strip()
            return {"text": text, "empty": not text, "language": "fr", "duration_s": round(duration, 2),
                    "segments": segments, "engine": self.engine.engine, "model": self.engine.model,
                    "processing_s": round(time.monotonic() - started, 3),
                    "unverified": True, "authorizes_execution": False}

    def cancel(self, client_id):
        return self.gate.cancel(client_id, "microphone")
