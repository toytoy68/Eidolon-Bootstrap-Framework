# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_tts.py
# Description : Synthèse phrase par phrase, voix présentes seulement, arrêt immédiat, Piper simulé par un exécutable local (G148)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
import sys
import tempfile
import threading
import time
import unittest

from eidolon_core.comm_contract import CommError, read_wav
from eidolon_core.comm_tts import (DEFAULT_RATE, PiperTTS, SimulatedTTS, TextToSpeech, chunks, scale,
                                   speakable, voices)

FAKE_PIPER = f"""#!{sys.executable}
import sys, time
args = sys.argv
text = sys.stdin.read()
if "lent" in text:
    time.sleep(5)
scale = float(args[args.index("--length_scale") + 1])
sys.stdout.buffer.write(b"\\x10\\x00" * int(len(text) * 200 * scale))
"""


class TextTests(unittest.TestCase):
    def test_speakable_text(self):
        self.assertEqual(speakable("**Bonjour** `toytoy`, voir https://exemple.fr/x\x07 !"),
                         "Bonjour toytoy , voir lien !")
        for bad in ("", "   ", None, "x" * 2001):
            with self.subTest(repr(bad)[:20]):
                with self.assertRaises(CommError):
                    speakable(bad)

    def test_sentence_chunks(self):
        self.assertEqual(chunks("Bonjour. Le NAS va bien ! Tu veux un diagnostic ?"),
                         ["Bonjour.", "Le NAS va bien !", "Tu veux un diagnostic ?"])
        long = "mot " * 200
        parts = chunks(long)
        self.assertTrue(all(len(p) <= 300 for p in parts))
        self.assertEqual(" ".join(parts).split(), long.split())             # nothing lost or duplicated

    def test_volume_scaling(self):
        pcm = b"\x00\x40" * 4                                               # 16384
        self.assertEqual(scale(pcm, 0.5), b"\x00\x20" * 4)
        self.assertEqual(scale(pcm, 1.0), pcm)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tts = TextToSpeech(SimulatedTTS())

    def test_chunk_by_chunk_with_the_slightly_slower_default(self):
        text = "Bonjour toytoy. Tout va bien."
        self.assertEqual(self.tts.plan(text), {"chunks": 2})
        first = self.tts.synthesize("pc", text, index=0)
        self.assertEqual((first["index"], first["chunks"], first["last"], first["voice"]), (0, 2, False, "simulated-fr"))
        self.assertTrue(self.tts.synthesize("pc", text, index=1)["last"])
        self.assertEqual(DEFAULT_RATE, 0.9)
        self.assertEqual(self.tts.status()["default_rate"], 0.9)

    def test_refusals(self):
        for kwargs, code in (({"voice": "inconnue"}, "ENGINE_UNAVAILABLE"), ({"rate": 3}, "INVALID_REQUEST"),
                             ({"volume": 2}, "INVALID_REQUEST"), ({"index": 5}, "INVALID_REQUEST")):
            with self.subTest(kwargs):
                with self.assertRaises(CommError) as caught:
                    self.tts.synthesize("pc", "Bonjour.", **kwargs)
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(CommError):
            TextToSpeech(SimulatedTTS(), default_voice="fr_FR-absente")


class PiperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.voices = os.path.join(self.tmp.name, "voices"); os.mkdir(self.voices)
        for name, rate in (("fr_FR-siwis-medium", 22050), ("fr_FR-upmc-medium", 22050)):
            open(os.path.join(self.voices, name + ".onnx"), "wb").close()
            with open(os.path.join(self.voices, name + ".onnx.json"), "w") as handle:
                json.dump({"audio": {"sample_rate": rate, "quality": "medium"}, "language": {"code": "fr_FR"}}, handle)
        open(os.path.join(self.voices, "orpheline.onnx"), "wb").close()             # no config: ignored
        self.piper = os.path.join(self.tmp.name, "piper")
        with open(self.piper, "w") as handle:
            handle.write(FAKE_PIPER)
        os.chmod(self.piper, 0o755)

    def test_only_installed_voices_are_offered(self):
        self.assertEqual(sorted(voices(self.voices)), ["fr_FR-siwis-medium", "fr_FR-upmc-medium"])
        self.assertEqual(voices(os.path.join(self.tmp.name, "absent")), {})

    def test_piper_runs_with_rate_and_returns_wav(self):
        tts = TextToSpeech(PiperTTS(self.piper, self.voices), default_voice="fr_FR-siwis-medium")
        normal = tts.synthesize("pc", "Bonjour toytoy.", rate=1.0)
        slower = tts.synthesize("pc", "Bonjour toytoy.", rate=0.5)
        self.assertGreater(len(slower["wav"]), len(normal["wav"]))         # length_scale = 1 / rate
        self.assertEqual(normal["engine"], "piper")

    def test_stop_kills_the_synthesis_at_once(self):
        tts = TextToSpeech(PiperTTS(self.piper, self.voices))
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.setdefault("r", self._catch(tts, "Réponse lente.")))
        worker.start()
        time.sleep(0.4)
        started = time.monotonic()
        self.assertTrue(tts.stop("pc"))
        worker.join(5)
        self.assertEqual(outcome["r"], "CANCELLED")
        self.assertLess(time.monotonic() - started, 2)

    def test_timeout_and_busy(self):
        tts = TextToSpeech(PiperTTS(self.piper, self.voices, timeout=0.5))
        self.assertEqual(self._catch(tts, "Réponse lente."), "TIMEOUT")

    def test_unsafe_or_missing_engine(self):
        with self.assertRaises(CommError):
            PiperTTS("piper", self.voices)                                     # not absolute
        with self.assertRaises(CommError):
            PiperTTS(os.path.join(self.tmp.name, "absent"), self.voices)
        os.chmod(self.piper, 0o777)
        with self.assertRaises(CommError):
            PiperTTS(self.piper, self.voices)                                  # writable by others
        os.chmod(self.piper, 0o755)
        with self.assertRaises(CommError):
            PiperTTS(self.piper, os.path.join(self.tmp.name, "absent"))        # no voice

    @staticmethod
    def _catch(tts, text):
        try:
            tts.synthesize("pc", text)
            return "OK"
        except CommError as exc:
            return exc.code


if __name__ == "__main__":
    unittest.main()


class PronunciationTests(unittest.TestCase):
    """toytoy is said like the English "toy" twice (toytoy, 12/10/2026), never "toi-toi"."""

    def setUp(self):
        from eidolon_core.comm_tts import SimulatedTTS, TextToSpeech
        self.heard = []
        test = self

        class Recording(SimulatedTTS):
            def synthesize(self, chunk, voice, rate, cancel, deadline):
                test.heard.append(chunk)
                return super().synthesize(chunk, voice, rate, cancel, deadline)
        self.make = lambda **kw: TextToSpeech(Recording(), **kw)

    def test_name_spelled_for_the_ear_in_the_spoken_chunk_only(self):
        from eidolon_core.comm_tts import chunks
        tts = self.make()
        text = "Bonjour toytoy, Toytoy est là. Les toytoys et toytoy-x restent tels quels."
        for index in range(len(chunks(text))):
            tts.synthesize("pc", text, index=index)
        heard = " ".join(self.heard)
        self.assertIn("Bonjour toï-toï, toï-toï est là.", heard)
        self.assertIn("Les toytoys et toytoy-x", heard)               # whole words only
        self.assertEqual(tts.plan(text), {"chunks": len(chunks(text))})

    def test_configurable_and_validated(self):
        tts = self.make(pronunciations={"toytoy": "toye-toye", "Eidolon": "Aïdolone"})
        tts.synthesize("pc", "Eidolon salue toytoy.")
        self.assertEqual(self.heard[-1], "Aïdolone salue toye-toye.")
        self.make(pronunciations={}).synthesize("pc", "toytoy")
        self.assertEqual(self.heard[-1], "toytoy")                    # empty map: no change
        for bad in ({"toytoy": "<x>"}, {"a\\n": "b"}, ["toytoy"], {f"k{i}": "v" for i in range(65)}):
            with self.assertRaises(CommError, msg=bad):
                self.make(pronunciations=bad)
