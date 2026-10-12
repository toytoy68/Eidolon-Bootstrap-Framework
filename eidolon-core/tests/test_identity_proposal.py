# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_identity_proposal.py
# Description : Proposition d'identité voix/visage (G170-C/D) : états, calibration, fusion, aucun droit, données synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from eidolon_core import identity_engines as E
from eidolon_core import identity_proposal as P

NOW = datetime(2026, 10, 12, 14, 0, 0, tzinfo=timezone.utc)
SHA_V, SHA_F = "a" * 64, "b" * 64
VOICE = P.EngineInfo("wespeaker-fake", SHA_V, "fbank80/1")
FACE = P.EngineInfo("sface-fake", SHA_F, "align5/1")
# Synthetic profiles only: invented ids, invented 4-d vectors.
TEMPLATES = {"profil-alpha": [(1.0, 0.0, 0.0, 0.0)], "profil-beta": [(0.0, 1.0, 0.0, 0.0)]}


def calibration(modality="voice", **kw):
    engine = VOICE if modality == "voice" else FACE
    base = dict(modality=modality, engine=engine.name, model_sha256=engine.model_sha256,
                preprocessing=engine.preprocessing, score_kind="cosine/fake/1", score_bounds=(-1.0, 1.0),
                threshold=0.7, margin=0.1, threshold_id="synthetic-campaign-0")
    base.update(kw)
    return P.Calibration(**base)


def voice(embedding=(1.0, 0.05, 0.0, 0.0), *, at=NOW, **kw):
    base = dict(duration_s=3.0, speech_s=2.5, embedding=embedding)
    base.update(kw)
    return P.Observation("voice", at, VOICE, **base)


def face(embedding=(1.0, 0.05, 0.0, 0.0), *, at=NOW, faces=1, **kw):
    return P.Observation("face", at, FACE, faces=faces, embedding=embedding, **kw)


VREG = P.Registry("voice", TEMPLATES, engine=VOICE)
FREG = P.Registry("face", TEMPLATES, engine=FACE)


def propose_voice(obs, **kw):
    return P.propose(obs, kw.pop("registry", VREG), kw.pop("cal", calibration()), now=kw.pop("now", NOW), **kw)


def propose_face(obs, **kw):
    return P.propose(obs, kw.pop("registry", FREG), kw.pop("cal", calibration("face")), now=kw.pop("now", NOW), **kw)


class ProposalStates(unittest.TestCase):
    def test_known_ambiguous_unknown_follow_threshold_and_margin(self):
        known = propose_voice(voice())
        self.assertEqual((known["state"], known["profile_id"]), ("known", "profil-alpha"))
        self.assertEqual(known["candidates"][0]["profile_id"], "profil-alpha")
        self.assertEqual(known["threshold_id"], "synthetic-campaign-0")
        between = propose_voice(voice((1.0, 0.9, 0.0, 0.0)))         # both above threshold, gap < margin
        self.assertEqual((between["state"], between["profile_id"]), ("ambiguous", None))
        far = propose_voice(voice((0.0, 0.0, 1.0, 0.0)))
        self.assertEqual((far["state"], far["profile_id"]), ("unknown", None))
        self.assertLessEqual(len(far["candidates"]), 3)

    def test_no_known_without_a_calibration_of_the_same_model_and_preprocessing(self):
        for cal in (None, calibration(model_sha256="c" * 64), calibration(preprocessing="fbank80/2"),
                    calibration(engine="other"), calibration("face")):
            self.assertEqual(propose_voice(voice(), cal=cal)["state"], "uncalibrated")
        other = P.Registry("voice", TEMPLATES, engine=P.EngineInfo("wespeaker-fake", "c" * 64, "fbank80/1"))
        result = propose_voice(voice(), registry=other)
        self.assertEqual((result["state"], result["reason"]), ("uncalibrated", "registry_built_with_another_model"))

    def test_dates_are_utc_not_in_the_future_and_expire(self):
        self.assertEqual(propose_voice(voice(at=NOW + timedelta(minutes=5)))["reason"], "clock_skew")
        self.assertEqual(propose_voice(voice(at=NOW + timedelta(seconds=3)))["state"], "known")   # small tolerance
        self.assertEqual(propose_voice(voice(at=NOW.replace(tzinfo=None)))["reason"], "invalid_date")
        paris = timezone(timedelta(hours=2))
        self.assertEqual(propose_voice(voice(at=NOW.astimezone(paris)))["reason"], "invalid_date")
        old = propose_voice(voice(at=NOW - timedelta(seconds=31)))
        self.assertEqual((old["state"], old["profile_id"]), ("stale", None))
        with self.assertRaises(ValueError):
            propose_voice(voice(), now=NOW.replace(tzinfo=None))

    def test_voice_silence_short_and_overlap_only_when_measured(self):
        silent = propose_voice(voice(silence=True))
        self.assertEqual((silent["state"], silent["reason"]), ("silence", "energy_heuristic"))
        self.assertEqual(propose_voice(voice(speech_s=1.0))["state"], "too_short")
        self.assertEqual(propose_voice(voice(speech_s=None))["state"], "too_short")
        self.assertEqual(propose_voice(voice(duration_s=31.0))["reason"], "invalid_duration")
        unmeasured = propose_voice(voice())
        self.assertIs(unmeasured["overlap_measured"], False)
        self.assertEqual(propose_voice(voice(overlap=True))["state"], "several_people")
        measured = propose_voice(voice(overlap=False))
        self.assertEqual((measured["state"], measured["overlap_measured"]), ("known", True))

    def test_face_counts(self):
        self.assertEqual(propose_face(face())["state"], "known")
        self.assertEqual(propose_face(face(faces=0))["state"], "no_face")
        self.assertEqual(propose_face(face(faces=2))["state"], "several_people")
        self.assertEqual(propose_face(face(faces=None))["reason"], "faces_not_measured")
        self.assertNotIn("overlap_measured", propose_face(face()))

    def test_eidolon_own_voice_is_ignored_with_a_pause(self):
        speaking = propose_voice(voice(), speaking_until=NOW - timedelta(seconds=0.5))
        self.assertEqual((speaking["state"], speaking["reason"]), ("unavailable", "eidolon_speaking"))
        self.assertEqual(propose_voice(voice(), speaking_until=NOW - timedelta(seconds=2))["state"], "known")

    def test_bad_engine_data_is_a_state_not_a_crash(self):
        self.assertEqual(propose_voice(voice(error="engine_failed"))["state"], "unavailable")
        self.assertEqual(propose_voice(voice(embedding=None))["reason"], "invalid_embedding")
        self.assertEqual(propose_voice(voice((1.0, float("nan"), 0.0, 0.0)))["reason"], "invalid_embedding")
        self.assertEqual(propose_voice(voice((1.0, 0.0)))["reason"], "invalid_embedding")   # dimension mismatch
        narrow = calibration(score_bounds=(0.0, 1.0), threshold=0.7, margin=0.1)
        self.assertEqual(propose_voice(voice((-1.0, -0.5, 0.0, 0.0)), cal=narrow)["reason"], "score_out_of_bounds")

    def test_not_enrolled(self):
        self.assertEqual(propose_voice(voice(), registry=None)["state"], "not_enrolled")
        self.assertEqual(propose_voice(voice(), registry=FREG)["state"], "not_enrolled")
        self.assertEqual(propose_voice(voice(), registry=P.Registry("voice", {}, engine=VOICE))["state"], "not_enrolled")

    def test_every_state_grants_nothing_and_never_shows_a_vector(self):
        outputs = [propose_voice(voice()), propose_voice(voice(silence=True)), propose_face(face(faces=2)),
                   propose_voice(voice(), cal=None), P.fuse(propose_voice(voice()), propose_face(face()), now=NOW)]
        for out in outputs:
            self.assertEqual(out["schema"], P.SCHEMA)
            self.assertEqual((out["grants"], out["authorizes_execution"]), ([], False))
            text = json.dumps(out)                              # JSON-able
            self.assertNotIn("embedding", text)
            self.assertNotIn("0.05", text)
        self.assertNotIn("0.05", repr(voice()))
        self.assertNotIn("1.0", repr(VREG))
        self.assertIn("profil-alpha", repr(VREG))

    def test_calibration_and_registry_validate_their_inputs(self):
        for bad in (dict(model_sha256="x"), dict(threshold=2.0), dict(score_bounds=(1.0, -1.0)),
                    dict(margin=-0.1), dict(validity_s=0), dict(threshold_id="a b"), dict(modality="iris")):
            with self.assertRaises(ValueError):
                calibration(**bad)
        for bad in ({"Alpha": [(1.0, 0.0)]}, {"profil-a": []}, {"profil-a": [(0.0, 0.0)]},
                    {"profil-a": [(1.0, 0.0)], "profil-b": [(1.0, 0.0, 0.0)]}):
            with self.assertRaises(ValueError):
                P.Registry("voice", bad, engine=VOICE)


class Fusion(unittest.TestCase):
    def fuse(self, v, f, now=NOW):
        return P.fuse(v, f, now=now)

    def test_agreement_disagreement_and_doubt_are_symmetric(self):
        alpha_v, alpha_f = propose_voice(voice()), propose_face(face())
        beta_f = propose_face(face((0.0, 1.0, 0.0, 0.0)))
        both = self.fuse(alpha_v, alpha_f)
        self.assertEqual((both["state"], both["profile_id"], both["basis"]), ("known", "profil-alpha", ["face", "voice"]))
        self.assertEqual(self.fuse(alpha_v, beta_f)["reason"], "voice_face_disagree")
        beta_v = propose_voice(voice((0.0, 1.0, 0.0, 0.0)))
        self.assertEqual(self.fuse(beta_v, alpha_f)["state"], "ambiguous")
        for doubt_f in (propose_face(face(faces=2)), propose_face(face((1.0, 0.9, 0.0, 0.0))),
                        propose_face(face((0.0, 0.0, 1.0, 0.0)))):
            self.assertEqual(self.fuse(alpha_v, doubt_f)["state"], "ambiguous")
        for doubt_v in (propose_voice(voice(overlap=True)), propose_voice(voice((0.0, 0.0, 1.0, 0.0)))):
            self.assertEqual(self.fuse(doubt_v, alpha_f)["state"], "ambiguous")

    def test_one_modality_is_enough_when_the_other_is_silent(self):
        alone = self.fuse(propose_voice(voice()), None)
        self.assertEqual((alone["state"], alone["basis"]), ("known", ["voice"]))
        no_face = self.fuse(propose_voice(voice()), propose_face(face(faces=0)))
        self.assertEqual((no_face["state"], no_face["basis"]), ("known", ["voice"]))
        self.assertEqual(self.fuse(None, None)["state"], "unavailable")
        self.assertEqual(self.fuse(propose_voice(voice(silence=True)), propose_face(face(faces=2)))["state"], "several_people")

    def test_staleness_is_recomputed_at_fusion_time(self):
        later = NOW + timedelta(seconds=40)
        result = self.fuse(propose_voice(voice()), propose_face(face()), now=later)
        self.assertEqual((result["state"], result["profile_id"]), ("unavailable", None))
        self.assertEqual(result["modalities"], {"voice": "stale", "face": "stale"})

    def test_fusion_refuses_anything_that_is_not_a_proposal(self):
        forged = dict(propose_voice(voice()), grants=["admin"])
        with self.assertRaises(ValueError):
            self.fuse(forged, None)


class EphemeralCaptureTests(unittest.TestCase):
    def test_buffer_is_wiped_on_exit_and_on_error(self):
        capture = P.EphemeralCapture(b"secret-audio")
        with capture as view:
            kept = view
            self.assertEqual(bytes(view), b"secret-audio")
        self.assertEqual(bytes(kept), b"\x00" * 12)
        self.assertEqual(len(capture), 0)
        failing = P.EphemeralCapture(b"secret-image")
        with self.assertRaises(RuntimeError):
            with failing as view:
                kept = view
                raise RuntimeError("cancel")
        self.assertEqual(bytes(kept), b"\x00" * 12)
        self.assertNotIn("secret", repr(failing))


def pcm(seconds, amplitude):
    count = int(seconds * E.SAMPLE_RATE)
    return struct.pack("<%dh" % count, *([amplitude, -amplitude] * (count // 2)))


class Adapters(unittest.TestCase):
    clock = staticmethod(lambda: NOW)

    def test_model_is_accepted_only_with_its_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "model.onnx"
            model.write_bytes(b"synthetic model bytes")
            digest = hashlib.sha256(b"synthetic model bytes").hexdigest()
            info = E.verify_model(model, digest, name="wespeaker-fake", preprocessing="fbank80/1")
            self.assertEqual(info.model_sha256, digest)
            with self.assertRaises(E.ModelRejected):
                E.verify_model(model, "0" * 64, name="x", preprocessing="y")
            with self.assertRaises(E.ModelRejected):
                E.verify_model(Path(tmp) / "absent.onnx", digest, name="x", preprocessing="y")
            link = Path(tmp) / "link.onnx"
            link.symlink_to(model)
            with self.assertRaises(E.ModelRejected):
                E.verify_model(link, digest, name="x", preprocessing="y")

    def test_voice_adapter_measures_speech_and_wipes_the_capture(self):
        seen = []
        adapter = E.VoiceAdapter(lambda samples, rate: (seen.append(samples), (1.0, 0.0, 0.0, 0.0))[1], VOICE,
                                 clock=self.clock)
        obs = adapter.observe(pcm(2.0, 3000))
        self.assertEqual((obs.speech_s, obs.overlap, obs.silence), (2.0, None, False))
        self.assertEqual(propose_voice(obs)["state"], "known")
        self.assertEqual(set(seen[0].tolist()), {0})                  # the runner's view was zeroed afterwards
        quiet = adapter.observe(pcm(2.0, 10))
        self.assertEqual(propose_voice(quiet)["state"], "silence")
        self.assertEqual(adapter.observe(b"\x00").error, "invalid_capture")

    def test_engine_failure_is_a_generic_code(self):
        def broken(samples, rate):
            raise RuntimeError("/models/secret/path.onnx failed")
        obs = E.VoiceAdapter(broken, VOICE, clock=self.clock).observe(pcm(2.0, 3000))
        self.assertEqual((obs.error, obs.embedding), ("engine_failed", None))
        self.assertNotIn("secret", repr(obs))

    def test_face_adapter_embeds_only_a_single_face(self):
        calls = []
        def embedder(image, box):
            calls.append(box)
            return (1.0, 0.0, 0.0, 0.0)
        for boxes, state in (([], "no_face"), ([1, 2], "several_people"), ([1], "known")):
            obs = E.FaceAdapter(lambda image: boxes, embedder, FACE, clock=self.clock).observe(b"\x89PNGfake")
            self.assertEqual(propose_face(obs)["state"], state)
        self.assertEqual(calls, [1])
