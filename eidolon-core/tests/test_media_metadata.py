# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_metadata.py
# Description : FFprobe réel, résultats techniques et bornes du sous-processus
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.media_cli import main
from eidolon_core.media_metadata import MAX_OUTPUT, _metadata, _output, probe, render_metadata


def observed():
    return {"streams": [{"codec_name": "mpeg4", "codec_type": "video", "width": 80, "height": 48,
                          "avg_frame_rate": "4/1", "duration": "1.000000"}],
            "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "1.000000"}}


class Boundaries(unittest.TestCase):
    def test_output_bound_and_deadline_reap_the_worker(self):
        with self.assertRaisesRegex(MediaError, "MEDIA_PROBE_OUTPUT_TOO_LARGE"):
            _output([sys.executable, "-c", f"import os;os.write(1,b'x'*{MAX_OUTPUT + 1})"])
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / "pid"
            script = "import os,time,sys;open(sys.argv[1],'w').write(str(os.getpid()));time.sleep(30)"
            start = time.monotonic()
            with self.assertRaisesRegex(MediaError, "MEDIA_PROBE_TIMEOUT"):
                _output([sys.executable, "-c", script, str(pidfile)], timeout=0.5)
            self.assertLess(time.monotonic() - start, 3)
            self.assertTrue(pidfile.exists())
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_stderr_and_failed_process_are_not_reflected(self):
        with self.assertRaisesRegex(MediaError, "^MEDIA_PROBE_FAILED$"):
            _output([sys.executable, "-c", "import sys;sys.stderr.write('PRIVATE_SENTINEL');sys.exit(3)"])
        self.assertEqual(_output([sys.executable, "-c", "import os;os.write(1,b'{}')"]), b"{}")

    def test_memory_exhaustion_is_confined_to_worker(self):
        with self.assertRaisesRegex(MediaError, "MEDIA_PROBE_FAILED"):
            _output([sys.executable, "-c", "x=bytearray(2*1024*1024*1024)"])

    def test_metadata_has_strict_types_bounds_and_printable_labels(self):
        value = observed()
        self.assertEqual(_metadata(json.dumps(value).encode(), "video/mp4")["duration_seconds"], 1.0)
        changes = [("stream", "width", True), ("stream", "width", 0), ("stream", "height", 65537),
                   ("stream", "codec_type", "audio"), ("stream", "codec_name", "\x1b[31m"),
                   ("stream", "avg_frame_rate", "1/0"), ("stream", "avg_frame_rate", "1/" + "1" * 20),
                   ("format", "duration", "nan"), ("format", "duration", "inf"),
                   ("format", "duration", True), ("format", "duration", -1),
                   ("format", "duration", "1e1000"), ("format", "format_name", "<script>")]
        for where, key, replacement in changes:
            item = copy.deepcopy(value)
            (item["streams"][0] if where == "stream" else item["format"])[key] = replacement
            with self.subTest(key=key, value=replacement), self.assertRaises(MediaError):
                _metadata(json.dumps(item).encode(), "video/mp4")
        for invalid in ({}, [], {"streams": [], "format": {}}, b'{"streams":[],"streams":[]}'):
            raw = invalid if type(invalid) is bytes else json.dumps(invalid).encode()
            with self.assertRaises(MediaError):
                _metadata(raw, "video/mp4")

    def test_unknown_duration_is_not_fabricated_and_still_images_have_no_duration(self):
        value = observed()
        value["format"].pop("duration"); value["streams"][0].pop("duration")
        value["streams"][0]["avg_frame_rate"] = "0/0"
        result = _metadata(json.dumps(value).encode(), "video/mp4")
        self.assertIsNone(result["duration_seconds"])
        self.assertIsNone(result["frame_rate"])
        with self.assertRaisesRegex(MediaError, "MEDIA_METADATA_TYPE_MISMATCH"):
            _metadata(json.dumps(value).encode(), "image/png")
        value["streams"][0]["codec_name"] = "png"
        value["streams"][0]["duration"] = "1"
        result = _metadata(json.dumps(value).encode(), "image/png")
        self.assertIsNone(result["duration_seconds"])
        self.assertIsNone(result["frame_rate"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "local FFmpeg/FFprobe not installed")
class RealProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store_root = self.root / "artifacts"
        self.marker = initialize(self.store_root)
        self.store = ArtifactStore(self.store_root, expected_store_id=self.marker["store_id"])
        self.ffprobe = str(Path(shutil.which("ffprobe")).absolute())
        self.ffmpeg = str(Path(shutil.which("ffmpeg")).absolute())

    def fixture(self, suffix):
        dest = self.root / ("fixture." + suffix)
        command = [self.ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=80x48:r=4",
                   "-threads", "1"]
        if suffix in {"png", "jpg", "webp"}:
            command += ["-frames:v", "1"]
        else:
            command += ["-t", "1", "-c:v", "mpeg4" if suffix == "mp4" else "libvpx"]
        subprocess.run([*command, str(dest)], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
        imported = self.store.import_file(dest)
        dest.unlink()
        return imported["reference"]

    def test_five_formats_real_probe_originals_removed_store_unchanged(self):
        for suffix, codec in (("png", "png"), ("jpg", "mjpeg"), ("webp", "webp"),
                              ("mp4", "mpeg4"), ("webm", "vp8")):
            with self.subTest(suffix=suffix):
                ref = self.fixture(suffix)
                before = {str(p.relative_to(self.store_root)): p.read_bytes()
                          for p in self.store_root.rglob("*") if p.is_file()}
                with patch("socket.socket", side_effect=AssertionError("network")):
                    result = probe(self.store_root, self.marker["store_id"], ref, ffprobe=self.ffprobe)
                self.assertEqual(result["state"], "METADATA_OBSERVED")
                self.assertEqual((result["observed"]["width"], result["observed"]["height"]), (80, 48))
                self.assertEqual(result["observed"]["codec"], codec)
                self.assertTrue(result["content_hash_checked"])
                for field in ("full_file_decoded", "semantic_content_verified", "engine_contacted", "artifact_modified",
                              "audio_inspected", "execution_authorized"):
                    self.assertFalse(result[field], field)
                if suffix in {"mp4", "webm"}:
                    self.assertAlmostEqual(result["observed"]["duration_seconds"], 1.0, places=2)
                else:
                    self.assertIsNone(result["observed"]["duration_seconds"])
                self.assertEqual(before, {str(p.relative_to(self.store_root)): p.read_bytes()
                                         for p in self.store_root.rglob("*") if p.is_file()})
                text = render_metadata(result)
                self.assertIn("80 × 48", text)
                self.assertIn("n'a pas été décodé intégralement", text)
                self.assertNotIn("SUCCEEDED", text)

    def test_hash_mismatch_refuses_before_any_process(self):
        ref = self.fixture("png")
        ref["sha256"] = "0" * 64
        with patch("eidolon_core.media_metadata.subprocess.Popen", side_effect=AssertionError("process")):
            with self.assertRaises(MediaError):
                probe(self.store_root, self.marker["store_id"], ref, ffprobe=self.ffprobe)

    def test_truncated_header_is_not_promoted_to_a_valid_output(self):
        source = self.root / "broken.png"; source.write_bytes(b"\x89PNG\r\n\x1a\nonly-a-header")
        ref = self.store.import_file(source)["reference"]
        with self.assertRaises(MediaError):
            probe(self.store_root, self.marker["store_id"], ref, ffprobe=self.ffprobe)
        self.assertEqual(len(self.store.inventory()["artifacts"]), 1)

    def test_cli_json_human_and_sanitized_failure(self):
        ref = self.fixture("mp4")
        path = self.root / "reference.json"; path.write_text(json.dumps({"reference": ref}))
        args = ["artifact-probe", "--root", str(self.store_root), "--store-id", self.marker["store_id"],
                "--reference", str(path), "--ffprobe", self.ffprobe]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["state"], "METADATA_OBSERVED")
        self.assertEqual(err.getvalue(), "")
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main([*args, "--format", "human"]), 0)
        self.assertIn("1.000 secondes", out.getvalue())
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main([*args[:-1], "/missing-PRIVATE-path", "--format", "human"]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("FFPROBE_NOT_CONFIGURED", err.getvalue())
        self.assertNotIn("PRIVATE", err.getvalue())


if __name__ == "__main__":
    unittest.main()
