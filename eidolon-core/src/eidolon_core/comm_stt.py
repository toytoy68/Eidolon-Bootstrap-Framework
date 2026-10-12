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
import re
import threading
import time

from .comm_contract import CommError, DeviceGate, read_wav

MAX_SEGMENTS = 200
SILENCE_RMS = 200          # 16-bit samples; below this the audio is treated as silence
# G164: Whisper's own rule for "no speech" segments (openai/whisper transcribe.py defaults).
NO_SPEECH_PROB, LOW_LOGPROB = 0.6, -1.0
# Texts Whisper invents on silence or noise (subtitle credits learnt from its training data).
HALLUCINATIONS = re.compile(
    r"^\W*(sous-titr\w*|merci d'avoir regard\w*|abonnez-vous|amara\.org|♪+|\.+)\b.*$|amara\.org",
    re.IGNORECASE)


def rms(pcm):
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class Vocabulary:
    """Controlled vocabulary (G164): a short glossary prompt biases the model towards the names; exact,
    unambiguous mishearings are then replaced, and every replacement is reported to the page.

    The prompt is never inserted in the text: a segment that only repeats it is dropped (see guard)."""
    TERM = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9' -]{0,39}")

    def __init__(self, terms=(), replacements=None):
        terms, replacements = list(terms), dict(replacements or {})
        if len(terms) > 32 or not all(isinstance(t, str) and self.TERM.fullmatch(t) for t in terms):
            raise CommError("INVALID_REQUEST", "vocabulary terms: up to 32 short words")
        if len(replacements) > 64 or not all(isinstance(k, str) and isinstance(v, str) and self.TERM.fullmatch(k)
                                             and self.TERM.fullmatch(v) for k, v in replacements.items()):
            raise CommError("INVALID_REQUEST", "vocabulary replacements: up to 64 short word pairs")
        self.terms = terms
        self.prompt = ("Glossaire : " + ", ".join(terms) + ".") if terms else None
        # Longest first, whole words only, case-insensitive.
        self._rules = [(re.compile(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", re.IGNORECASE), k, v)
                       for k, v in sorted(replacements.items(), key=lambda kv: -len(kv[0]))]

    def apply(self, text):
        corrections = []
        for pattern, source, target in self._rules:
            text, count = pattern.subn(target, text)
            if count:
                corrections.append({"from": source, "to": target, "count": count})
        return text, corrections

    def only_prompt(self, text):
        """True when a segment only repeats the glossary (a known Whisper failure on silence)."""
        if not self.terms:
            return False
        words = re.sub(r"[^\wÀ-ÿ' -]", " ", text.lower().replace("glossaire", " ")).split()
        vocabulary = {w for t in self.terms for w in t.lower().split()}
        return bool(words) and all(w in vocabulary for w in words)


# Suggested starting point for comm.json, to be compared on the VM (docs/COMMUNICATION.md §6, G164).
DEFAULT_VOCABULARY = {"terms": ["Eidolon", "toytoy"],
                      "replacements": {"toi-toi": "toytoy", "toi toi": "toytoy", "toy-toy": "toytoy",
                                       "toy toy": "toytoy", "toïtoï": "toytoy", "Eidolone": "Eidolon",
                                       "Eidolonne": "Eidolon", "Eydolon": "Eidolon", "Aïdolon": "Eidolon",
                                       "Idolon": "Eidolon"}}


def kept(segment, vocabulary=None):
    """False for a segment the engine produced without speech (G164 guard); never applied to real words
    with good confidence."""
    text = segment["text"].strip()
    if not text:
        return False
    no_speech, logprob = segment.get("no_speech_prob"), segment.get("avg_logprob")
    if no_speech is not None and logprob is not None and no_speech > NO_SPEECH_PROB and logprob < LOW_LOGPROB:
        return False
    if HALLUCINATIONS.search(text):
        return False
    # A glossary echo: the prompt itself, or only its words while the model doubts there was speech.
    # "Eidolon." clearly spoken is kept.
    if vocabulary is not None and vocabulary.only_prompt(text) and (
            "glossaire" in text.lower() or (no_speech is not None and no_speech > 0.3)):
        return False
    return True


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

    def __init__(self, model_dir, *, compute_type="int8", threads=2, beam_size=1, vad=False, bias="none",
                 vocabulary=None):
        if (not isinstance(model_dir, str) or not os.path.isabs(model_dir)
                or not os.path.isfile(os.path.join(model_dir, "model.bin"))):
            raise CommError("ENGINE_UNAVAILABLE", "a local CTranslate2 Whisper directory (model.bin) is required")
        if type(threads) is not int or not 1 <= threads <= 16 or type(beam_size) is not int or not 1 <= beam_size <= 5:
            raise CommError("INVALID_REQUEST", "threads 1-16, beam size 1-5")
        self.model_dir, self.compute_type = model_dir, compute_type
        if bias not in ("none", "prompt", "hotwords"):
            raise CommError("INVALID_REQUEST", "bias: none, prompt or hotwords")
        self.threads, self.beam_size, self.vad = threads, beam_size, bool(vad)
        self.bias, self.vocabulary = bias, vocabulary
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
        options = {}
        if self.vocabulary is not None and self.vocabulary.prompt and self.bias == "prompt":
            options["initial_prompt"] = self.vocabulary.prompt
        elif self.vocabulary is not None and self.vocabulary.terms and self.bias == "hotwords":
            options["hotwords"] = " ".join(self.vocabulary.terms)
        segments, _info = model.transcribe(audio, language="fr", beam_size=self.beam_size,
                                           vad_filter=self.vad, condition_on_previous_text=False, **options)
        out = []
        for segment in segments:                         # lazy generator: checked between segments
            if cancel.is_set():
                raise CommError("CANCELLED")
            if time.monotonic() > deadline:
                raise CommError("TIMEOUT", "transcription took too long")
            out.append({"start": round(segment.start, 2), "end": round(segment.end, 2), "text": segment.text.strip(),
                        "no_speech_prob": round(float(segment.no_speech_prob), 3),
                        "avg_logprob": round(float(segment.avg_logprob), 3)})
            if len(out) >= MAX_SEGMENTS:
                break
        return out


class SpeechToText:
    """One transcription per client at a time (DeviceGate), and one engine call at a time overall."""

    def __init__(self, engine, *, gate=None, time_budget=60.0, vocabulary=None, silence_rms=SILENCE_RMS, guard=True):
        self.engine, self.gate = engine, gate or DeviceGate()
        self.time_budget = time_budget
        self.vocabulary = vocabulary if vocabulary is not None else getattr(engine, "vocabulary", None)
        if type(silence_rms) not in (int, float) or not 0 <= silence_rms <= 5000:
            raise CommError("INVALID_REQUEST", "silence_rms 0-5000")
        self.silence_rms, self.guard = silence_rms, guard      # guard=False only for the "before" bench
        self._engine_lock = threading.Lock()

    def status(self):
        return {"engine": self.engine.engine, "model": self.engine.model,
                "state": "ready", "language": "fr", "limits": {"seconds": 30, "bytes": 1024 * 1024},
                "vocabulary_terms": len(self.vocabulary.terms) if self.vocabulary is not None else 0,
                "bias": getattr(self.engine, "bias", "none")}

    def transcribe(self, client_id, wav):
        with self.gate.hold(client_id, "microphone") as cancel:
            pcm, duration = read_wav(wav)
            if rms(pcm) < self.silence_rms:                 # G164: silence never reaches the model
                return self._result("", [], duration, 0.0, [], 0, silence=True)
            if not self._engine_lock.acquire(blocking=False):
                raise CommError("DEVICE_BUSY", "the transcription engine is busy")
            started = time.monotonic()
            try:
                segments = self.engine.transcribe(pcm, duration, cancel, started + self.time_budget)
            finally:
                self._engine_lock.release()
            good = [s for s in segments if kept(s, self.vocabulary)] if self.guard else [s for s in segments if s["text"]]
            text = " ".join(s["text"].strip() for s in good).strip()
            corrections = []
            if self.vocabulary is not None:
                text, corrections = self.vocabulary.apply(text)
            return self._result(text, good, duration, time.monotonic() - started, corrections,
                                len(segments) - len(good))

    def _result(self, text, segments, duration, elapsed, corrections, dropped, silence=False):
        return {"text": text, "empty": not text, "language": "fr", "duration_s": round(duration, 2),
                "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segments],
                "engine": self.engine.engine, "model": self.engine.model,
                "processing_s": round(elapsed, 3), "silence": silence, "dropped_segments": dropped,
                "corrections": corrections, "unverified": True, "authorizes_execution": False}

    def cancel(self, client_id):
        return self.gate.cancel(client_id, "microphone")
