# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_tts.py
# Description : Synthèse vocale locale (Piper ou simulateur) phrase par phrase, arrêt immédiat, voix réellement présentes (G148)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Text to speech, on the server, one sentence chunk per request.

The page asks for chunk 0, plays it, then asks for the next one: the first sound comes after one
sentence, and stopping is simply not asking for the next chunk (plus DELETE for the one in progress).

- Voices are the Piper voices REALLY present in the operator's voice directory (<name>.onnx and
  <name>.onnx.json); nothing is downloaded. Operator preference (G140): French, female, warm, calm,
  slightly slower (default rate 0.9). No promise of reproducing another service's voice.
- PiperTTS runs the operator's Piper executable (absolute path) with an empty environment and a time
  limit; text goes through stdin, raw 16-bit PCM comes back through stdout.
- SimulatedTTS: deterministic tone, for tests and container recipes only.
"""
import array
import json
import os
import re
import stat
import subprocess
import threading
import time

from .comm_contract import CommError, DeviceGate, write_wav

MAX_TEXT = 2000
MAX_CHUNK = 300
# Names the French voice would misread, spelled for the ear (toytoy said like the English "toy" twice,
# not "toi-toi"; told by toytoy on 12/10/2026). Applied to the spoken chunk only, never to displayed text.
# The spelling is a best guess for Piper/espeak French: to be confirmed by listening (docs/COMMUNICATION.md §7).
DEFAULT_PRONUNCIATIONS = {"toytoy": "toï-toï"}
WORD = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{0,39}")


def pronunciation_rules(mapping):
    """Validated (pattern, spoken) list: whole words, case-insensitive, longest first."""
    if not isinstance(mapping, dict) or len(mapping) > 64 or not all(
            isinstance(k, str) and isinstance(v, str) and WORD.fullmatch(k) and WORD.fullmatch(v)
            for k, v in mapping.items()):
        raise CommError("INVALID_REQUEST", "pronunciations: up to 64 short word pairs")
    return [(re.compile(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", re.IGNORECASE), v)
            for k, v in sorted(mapping.items(), key=lambda kv: -len(kv[0]))]


def pronounce(text, rules):
    for pattern, spoken in rules:
        text = pattern.sub(spoken, text)
    return text
DEFAULT_RATE = 0.9
VOICE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def speakable(text):
    """What is read aloud: no control characters, no Markdown marks, links named rather than spelled."""
    if not isinstance(text, str) or not text.strip():
        raise CommError("INVALID_REQUEST", "text required")
    if len(text) > MAX_TEXT:
        raise CommError("PAYLOAD_TOO_LARGE", "text above 2000 characters")
    text = CONTROL.sub(" ", text)
    text = re.sub(r"https?://\S+", "lien", text)
    text = re.sub(r"[*_#`>|~]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def chunks(text):
    """Sentence chunks of at most 300 characters; a long sentence is split at commas, then at words."""
    out = []
    for sentence in re.split(r"(?<=[.!?…;:])\s+", speakable(text)):
        while len(sentence) > MAX_CHUNK:
            cut = sentence.rfind(", ", 0, MAX_CHUNK)
            cut = cut + 1 if cut > MAX_CHUNK // 3 else sentence.rfind(" ", 0, MAX_CHUNK)
            cut = cut if cut > 0 else MAX_CHUNK
            out.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            out.append(sentence)
    return out


def scale(pcm, volume):
    if volume == 1.0:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    return array.array("h", (max(-32768, min(32767, int(s * volume))) for s in samples)).tobytes()


def voices(directory):
    """{name: {language, sample_rate, quality}} for each <name>.onnx with a readable <name>.onnx.json."""
    found = {}
    if not directory or not os.path.isdir(directory):
        return found
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(".onnx") or not VOICE_NAME.fullmatch(entry[:-5]):
            continue
        model, config = os.path.join(directory, entry), os.path.join(directory, entry + ".json")
        if os.path.islink(model) or os.path.islink(config) or not os.path.isfile(config):
            continue
        try:
            with open(config, encoding="utf-8") as handle:
                data = json.load(handle)
            rate = int(data["audio"]["sample_rate"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        language = (data.get("language") or {}).get("code") or data.get("espeak", {}).get("voice") or ""
        found[entry[:-5]] = {"language": str(language)[:20], "sample_rate": rate,
                             "quality": str((data.get("audio") or {}).get("quality", ""))[:20]}
    return found


class SimulatedTTS:
    engine = "simulated"

    def __init__(self):
        self.catalog = {"simulated-fr": {"language": "fr_FR", "sample_rate": 22050, "quality": "simulated"}}

    def synthesize(self, chunk, voice, rate, cancel, deadline):
        if cancel.is_set():
            raise CommError("CANCELLED")
        seconds = max(0.2, len(chunk) * 0.06 / rate)
        frames = int(22050 * seconds)
        return array.array("h", (int(3000 * ((i // 50) % 2 * 2 - 1)) for i in range(frames))).tobytes(), 22050


class PiperTTS:
    """The operator's Piper executable and voice directory; one process per chunk, empty environment."""
    engine = "piper"

    def __init__(self, executable, voice_dir, *, timeout=30.0):
        if not isinstance(executable, str) or not os.path.isabs(executable):
            raise CommError("ENGINE_UNAVAILABLE", "an absolute path to the Piper executable is required")
        try:
            info = os.stat(executable)
        except OSError:
            raise CommError("ENGINE_UNAVAILABLE", "Piper executable not found") from None
        if not stat.S_ISREG(info.st_mode) or not os.access(executable, os.X_OK) or info.st_mode & 0o022:
            raise CommError("ENGINE_UNAVAILABLE", "Piper executable not safely installed")
        self.executable, self.voice_dir, self.timeout = executable, voice_dir, timeout
        self.catalog = voices(voice_dir)
        if not self.catalog:
            raise CommError("ENGINE_UNAVAILABLE", "no Piper voice (.onnx and .onnx.json) in the voice directory")

    def synthesize(self, chunk, voice, rate, cancel, deadline):
        model = os.path.join(self.voice_dir, voice + ".onnx")
        args = [self.executable, "--model", model, "--output_raw", "--length_scale", f"{1.0 / rate:.3f}"]
        try:
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, env={})
        except OSError:
            raise CommError("ENGINE_UNAVAILABLE", "Piper could not start") from None
        result = {}

        def run():
            try:
                result["out"] = process.communicate(chunk.encode("utf-8"), timeout=min(self.timeout, max(0.1, deadline - time.monotonic())))[0]
            except subprocess.TimeoutExpired:
                result["timeout"] = True
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        while worker.is_alive():
            worker.join(0.05)
            if cancel.is_set():
                self._reap(process, worker)
                raise CommError("CANCELLED")
        if result.get("timeout"):
            self._reap(process, worker)
            raise CommError("TIMEOUT", "synthesis took too long")
        if process.returncode != 0 or not result.get("out"):
            raise CommError("ENGINE_UNAVAILABLE", "Piper failed")
        return result["out"], self.catalog[voice]["sample_rate"]

    @staticmethod
    def _reap(process, worker):
        """Kill, then collect the process and close its pipes: no zombie, no open descriptor."""
        process.kill()
        worker.join(1)
        try:
            process.communicate(timeout=2)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass
        for stream in (process.stdin, process.stdout):
            if stream is not None and not stream.closed:
                stream.close()
        process.wait(timeout=2)


class TextToSpeech:
    """One synthesis per client at a time (DeviceGate on the speaker), and one engine call at a time."""

    def __init__(self, engine, *, default_voice=None, gate=None, time_budget=30.0, pronunciations=None):
        self.engine, self.gate, self.time_budget = engine, gate or DeviceGate(), time_budget
        self.pronunciations = DEFAULT_PRONUNCIATIONS if pronunciations is None else pronunciations
        self._rules = pronunciation_rules(self.pronunciations)
        if default_voice is not None and default_voice not in engine.catalog:
            raise CommError("ENGINE_UNAVAILABLE", "the configured default voice is not installed")
        self.default_voice = default_voice or sorted(engine.catalog)[0]
        self._engine_lock = threading.Lock()

    def status(self):
        return {"engine": self.engine.engine, "state": "ready", "default_voice": self.default_voice,
                "voices": self.engine.catalog, "default_rate": DEFAULT_RATE,
                "pronunciations": len(self.pronunciations),
                "limits": {"characters": MAX_TEXT, "chunk_characters": MAX_CHUNK}}

    def plan(self, text):
        return {"chunks": len(chunks(text))}

    def synthesize(self, client_id, text, *, index=0, voice=None, rate=DEFAULT_RATE, volume=1.0):
        voice = voice or self.default_voice
        if voice not in self.engine.catalog:
            raise CommError("ENGINE_UNAVAILABLE", "voice not installed")
        if type(rate) not in (int, float) or not 0.5 <= rate <= 1.5:
            raise CommError("INVALID_REQUEST", "rate between 0.5 and 1.5")
        if type(volume) not in (int, float) or not 0.0 <= volume <= 1.0:
            raise CommError("INVALID_REQUEST", "volume between 0 and 1")
        parts = chunks(text)
        if type(index) is not int or not 0 <= index < len(parts):
            raise CommError("INVALID_REQUEST", "chunk index out of range")
        with self.gate.hold(client_id, "speaker") as cancel:
            if not self._engine_lock.acquire(blocking=False):
                raise CommError("DEVICE_BUSY", "the synthesis engine is busy")
            started = time.monotonic()
            try:
                pcm, sample_rate = self.engine.synthesize(pronounce(parts[index], self._rules), voice, float(rate), cancel,
                                                          started + self.time_budget)
            finally:
                self._engine_lock.release()
            return {"wav": write_wav(scale(pcm, float(volume)), sample_rate), "index": index, "chunks": len(parts),
                    "last": index == len(parts) - 1, "voice": voice, "engine": self.engine.engine,
                    "processing_s": round(time.monotonic() - started, 3)}

    def stop(self, client_id):
        return self.gate.cancel(client_id, "speaker")
