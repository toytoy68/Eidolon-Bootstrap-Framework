# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_stt.py
# Description : Transcription bornée, annulable, une requête par micro ; moteur réel absent = indisponible (G147)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import array
import hashlib
import io
import math
import os
import tempfile
import threading
import unittest
import wave

from eidolon_core.comm_contract import CommError, DeviceGate, read_wav, write_wav
from eidolon_core.comm_stt import FasterWhisperSTT, SimulatedSTT, SpeechToText


def tone(seconds, freq=440.0, amplitude=8000, rate=16000):
    samples = array.array("h", (int(amplitude * math.sin(2 * math.pi * freq * i / rate)) for i in range(int(seconds * rate))))
    return samples.tobytes()


def wav(pcm, channels=1, width=2, rate=16000):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)
    return out.getvalue()


class AudioContractTests(unittest.TestCase):
    def test_valid_audio_is_read(self):
        pcm, duration = read_wav(wav(tone(1.5)))
        self.assertEqual((len(pcm), duration), (48000, 1.5))

    def test_refused_formats_and_sizes(self):
        cases = {"stereo": (wav(tone(1) * 2, channels=2), "AUDIO_FORMAT_UNSUPPORTED"),
                 "44.1 kHz": (wav(tone(1), rate=44100), "AUDIO_FORMAT_UNSUPPORTED"),
                 "8-bit": (wav(b"\x80" * 16000, width=1), "AUDIO_FORMAT_UNSUPPORTED"),
                 "not wav": (b"ID3 mp3 data here", "AUDIO_FORMAT_UNSUPPORTED"),
                 "empty": (b"", "AUDIO_FORMAT_UNSUPPORTED"),
                 "too long": (wav(b"\0\0" * 16000 * 31), "PAYLOAD_TOO_LARGE"),
                 "too big": (b"RIFF" + b"\0" * (1024 * 1024), "PAYLOAD_TOO_LARGE")}
        for name, (data, code) in cases.items():
            with self.subTest(name):
                with self.assertRaises(CommError) as caught:
                    read_wav(data)
                self.assertEqual(caught.exception.code, code)

    def test_truncated_audio_is_refused(self):
        data = wav(tone(1))
        with self.assertRaises(CommError):
            read_wav(data[: len(data) - 1000])

    def test_write_wav_round_trip(self):
        self.assertEqual(read_wav(write_wav(tone(0.5)))[0], tone(0.5))


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.speech = tone(2.0)
        scripted = {hashlib.sha256(self.speech).hexdigest(): "Diagnostique le NAS."}
        self.stt = SpeechToText(SimulatedSTT(scripted))

    def test_a_transcript_is_unverified_text_that_authorizes_nothing(self):
        result = self.stt.transcribe("pc-toytoy", wav(self.speech))
        self.assertEqual((result["text"], result["empty"], result["language"], result["duration_s"]),
                         ("Diagnostique le NAS.", False, "fr", 2.0))
        self.assertEqual((result["unverified"], result["authorizes_execution"]), (True, False))
        self.assertNotIn("proposal", result)                     # never a mission, never a submission

    def test_silence_gives_an_empty_transcript(self):
        result = self.stt.transcribe("pc-toytoy", wav(b"\0\0" * 16000))
        self.assertEqual((result["text"], result["empty"], result["segments"]), ("", True, []))

    def test_low_noise_is_treated_as_silence(self):
        noise = array.array("h", ((i * 37) % 101 - 50 for i in range(16000))).tobytes()
        self.assertTrue(self.stt.transcribe("pc-toytoy", wav(noise))["empty"])

    def test_one_active_request_per_microphone_and_cancel(self):
        started, release = threading.Event(), threading.Event()

        class Slow(SimulatedSTT):
            def transcribe(self, pcm, duration, cancel, deadline):
                started.set()
                release.wait(5)
                if cancel.is_set():
                    raise CommError("CANCELLED")
                return super().transcribe(pcm, duration, cancel, deadline)
        stt = SpeechToText(Slow())
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.setdefault("first", self._catch(stt, "pc-a")))
        worker.start()
        started.wait(5)
        self.assertEqual(self._catch(stt, "pc-a"), "DEVICE_BUSY")      # same client: refused, not queued
        self.assertEqual(self._catch(stt, "pc-b"), "DEVICE_BUSY")      # engine busy for everyone
        self.assertTrue(stt.cancel("pc-a"))
        release.set()
        worker.join(5)
        self.assertEqual(outcome["first"], "CANCELLED")
        self.assertFalse(stt.cancel("pc-a"))                           # nothing active any more
        self.assertFalse(self._catch(stt, "pc-a").startswith("DEVICE_BUSY"))

    def _catch(self, stt, client):
        try:
            stt.transcribe(client, wav(self.speech))
            return "OK"
        except CommError as exc:
            return exc.code

    def test_gate_refuses_unknown_device_kind(self):
        with self.assertRaises(CommError):
            with DeviceGate().hold("pc", "printer"):
                pass


class RealEngineTests(unittest.TestCase):
    def test_a_model_name_is_refused_so_nothing_is_downloaded(self):
        for value in ("small", "Systran/faster-whisper-small", "relative/dir"):
            with self.subTest(value):
                with self.assertRaises(CommError) as caught:
                    FasterWhisperSTT(value)
                self.assertEqual(caught.exception.code, "ENGINE_UNAVAILABLE")

    def test_a_missing_library_is_reported_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            open(os.path.join(folder, "model.bin"), "wb").close()
            engine = FasterWhisperSTT(folder)
            try:
                import faster_whisper  # noqa: F401
                self.skipTest("faster-whisper installed here: covered by the hardware recipe")
            except ImportError:
                pass
            with self.assertRaises(CommError) as caught:
                SpeechToText(engine).transcribe("pc", wav(tone(1)))
            self.assertEqual(caught.exception.code, "ENGINE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
