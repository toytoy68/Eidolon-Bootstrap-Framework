# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_identity_runners.py
# Description : Exécuteurs réels facultatifs G170-C/D : fbank, ONNX sur octets vérifiés, YuNet + SFace ; sans visage ni voix réels
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Optional: skipped unless numpy / onnxruntime / OpenCV are installed. The real face models are used only when
EIDOLON_IDENTITY_MODELS points to a folder holding the files of docs/identity-models.json (never in Git).
No real face or voice is used: images are blank or noise, audio is synthetic tones."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from eidolon_core import identity_engines as E
from eidolon_core import identity_proposal as P

HAVE = {name: importlib.util.find_spec(name) is not None
        for name in ("numpy", "onnxruntime", "cv2", "onnx", "kaldi_native_fbank")}
MANIFEST = json.loads((Path(__file__).resolve().parents[1] / "docs" / "identity-models.json").read_text())
MODELS = Path(os.environ["EIDOLON_IDENTITY_MODELS"]) if os.environ.get("EIDOLON_IDENTITY_MODELS") else None
NOW = datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)


def tone(seconds=2.0, rate=16000):
    import numpy as np
    t = np.arange(int(seconds * rate)) / rate
    return (3000 * np.sin(2 * np.pi * 220 * t) + 800 * np.sin(2 * np.pi * 3100 * t)).astype("<i2")


@unittest.skipUnless(HAVE["numpy"], "numpy not installed")
class Fbank(unittest.TestCase):
    def test_shape_cmn_and_bounds(self):
        from eidolon_core import identity_runners as R
        feats = R.fbank(tone(1.0).tolist())
        self.assertEqual(feats.shape, (98, 80))                       # snip_edges: 1 + (16000 - 400) // 160
        self.assertLess(float(abs(feats.mean(axis=0)).max()), 1e-4)  # CMN
        with self.assertRaises(ValueError):
            R.fbank([0] * 399)

    @unittest.skipUnless(HAVE["kaldi_native_fbank"], "reference kaldi-native-fbank not installed")
    def test_parity_with_kaldi_native_fbank(self):
        import kaldi_native_fbank as knf
        import numpy as np
        from eidolon_core import identity_runners as R
        samples = tone(3.0)
        opts = knf.FbankOptions()
        opts.frame_opts.dither, opts.frame_opts.window_type = 0.0, "hamming"
        opts.mel_opts.num_bins, opts.use_energy = 80, False
        online = knf.OnlineFbank(opts)
        online.accept_waveform(16000, samples.astype(np.float32).tolist())
        online.input_finished()
        ref = np.array([online.get_frame(i) for i in range(online.num_frames_ready)])
        ref = ref - ref.mean(axis=0)
        self.assertLess(float(np.abs(R.fbank(samples.tolist()) - ref).max()), 0.01)


def synthetic_speaker_model():
    """Tiny ONNX with WeSpeaker's signature (feats [1, T, 80] -> embs [1, 4]); NOT a speaker model."""
    import numpy as np
    import onnx
    from onnx import helper, numpy_helper, TensorProto
    weights = numpy_helper.from_array(np.random.default_rng(0).normal(size=(80, 4)).astype(np.float32), "w")
    graph = helper.make_graph(
        [helper.make_node("ReduceMean", ["feats"], ["pooled"], axes=[1], keepdims=0),
         helper.make_node("MatMul", ["pooled", "w"], ["embs"])],
        "synthetic", [helper.make_tensor_value_info("feats", TensorProto.FLOAT, [1, "T", 80])],
        [helper.make_tensor_value_info("embs", TensorProto.FLOAT, [1, 4])], [weights])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    return model.SerializeToString()


@unittest.skipUnless(HAVE["numpy"] and HAVE["onnxruntime"] and HAVE["onnx"], "onnxruntime/onnx not installed")
class WeSpeakerRunnerTests(unittest.TestCase):
    def verified(self, data, preprocessing=None):
        from eidolon_core import identity_runners as R
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "speaker.onnx"
            path.write_bytes(data)
            return E.verify_model(path, hashlib.sha256(data).hexdigest(), name="synthetic-speaker",
                                  preprocessing=preprocessing or R.VOICE_PREPROCESSING)

    def test_runner_loads_the_verified_bytes_and_feeds_the_voice_adapter(self):
        from eidolon_core import identity_runners as R
        verified = self.verified(synthetic_speaker_model())        # file already deleted: bytes only
        runner = R.WeSpeakerRunner(verified)
        adapter = E.VoiceAdapter(runner, verified.engine, clock=lambda: NOW)
        obs = adapter.observe(bytearray(tone().tobytes()))
        self.assertIsNone(obs.error)
        self.assertEqual(len(obs.embedding), 4)
        self.assertEqual(obs.embedding, adapter.observe(tone().tobytes()).embedding)   # deterministic
        cal = P.Calibration(modality="voice", engine="synthetic-speaker", model_sha256=verified.engine.model_sha256,
                            preprocessing=R.VOICE_PREPROCESSING, score_kind="cosine/synthetic/1",
                            score_bounds=(-1.0, 1.0), threshold=0.9, margin=0.05, threshold_id="synthetic-0")
        registry = P.Registry("voice", {"profil-alpha": [obs.embedding]}, engine=verified.engine)
        self.assertEqual(P.propose(obs, registry, cal, now=NOW)["state"], "known")

    def test_wrong_preprocessing_or_signature_is_refused(self):
        from eidolon_core import identity_runners as R
        with self.assertRaises(ValueError):
            R.WeSpeakerRunner(self.verified(synthetic_speaker_model(), "other/1"))
        with self.assertRaises(ValueError):
            R.WeSpeakerRunner(self.verified(synthetic_speaker_model())).__call__(tone().tolist(), 8000)


def manifest_model(model_id):
    entry = next(m for m in MANIFEST["models"] if m["id"] == model_id)
    return E.verify_model(MODELS / entry["file"], entry["sha256_computed"], name=model_id,
                          preprocessing=entry["preprocessing"])


@unittest.skipUnless(HAVE["numpy"] and HAVE["cv2"] and MODELS is not None,
                     "OpenCV or EIDOLON_IDENTITY_MODELS (YuNet/SFace files) not available")
class YuNetSFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from eidolon_core import identity_runners as R
        cls.detector, cls.encoder = manifest_model("yunet-2023mar"), manifest_model("sface-2021dec")
        cls.pipeline = R.YuNetSFace(cls.detector, cls.encoder)

    def png(self, image):
        import cv2
        ok, data = cv2.imencode(".png", image)
        self.assertTrue(ok)
        return bytearray(data.tobytes())

    def test_published_hashes_match_the_files(self):
        for entry in MANIFEST["models"][:2]:
            self.assertEqual(entry["sha256_published"], entry["sha256_computed"])
            self.assertEqual(hashlib.sha256((MODELS / entry["file"]).read_bytes()).hexdigest(), entry["sha256_computed"])

    def test_a_blank_image_has_no_face_and_the_capture_is_wiped(self):
        import numpy as np
        engine = P.EngineInfo("yunet-2023mar+sface-2021dec", self.encoder.engine.model_sha256,
                              self.encoder.engine.preprocessing)
        adapter = E.FaceAdapter(self.pipeline.detector, self.pipeline.embedder, engine, clock=lambda: NOW)
        capture = self.png(np.full((240, 320, 3), 128, np.uint8))
        self.assertEqual(adapter.observe(capture).faces, 0)
        self.assertEqual(set(capture), {0})
        self.assertEqual(adapter.observe(b"not an image").error, "engine_failed")

    def test_encoder_gives_a_finite_128_vector_and_wipes_the_decoded_image(self):
        import numpy as np
        from eidolon_core import identity_runners as R
        noise = np.random.default_rng(1).integers(0, 255, (200, 200, 3), dtype=np.uint8)
        image = self.pipeline.decode(memoryview(self.png(noise)))
        row = np.array([50, 50, 100, 100, 80, 90, 120, 90, 100, 110, 85, 130, 115, 130, 0.99], np.float32)
        face = R.Face(row, image)                                      # synthetic box: no real face involved
        vector = self.pipeline.embedder(None, face)
        self.assertEqual(len(vector), 128)
        self.assertTrue(all(np.isfinite(vector)))
        face.wipe()
        self.assertEqual(int(image.max()), 0)
