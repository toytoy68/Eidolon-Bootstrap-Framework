# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_video_sampling.py
# Description : Recette FFmpeg réelle des bornes vidéo, sans modèle ni GPU
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with an installed package, no PYTHONPATH; temporary synthetic media only."""
import base64
import io
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image
from eidolon_core.media_agents import MediaError, execute, inspect
from eidolon_core.media_backends import LocalMediaBackend


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-video-bound-") as directory:
        root = Path(directory)
        source = root / "red40-blue5-with-audio.mp4"
        command = ["/usr/bin/ffmpeg", "-nostdin", "-v", "error",
                   "-f", "lavfi", "-i", "color=c=red:s=1280x720:r=1:d=40",
                   "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=1:d=5",
                   "-f", "lavfi", "-i", "sine=frequency=440:duration=45",
                   "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                   "-map", "[v]", "-map", "2:a", "-t", "45",
                   "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast",
                   "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, timeout=45)
        probe = json.loads(subprocess.check_output([
            "/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)], timeout=10))
        assert float(probe["format"]["duration"]) >= 45
        assert {s["codec_type"] for s in probe["streams"]} == {"video", "audio"}
        calls = []
        config = {"ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "synthetic:vision", "ffmpeg": "/usr/bin/ffmpeg"}

        def model_stub(method, url, payload, **kwargs):
            calls.append({"method": method, "route": url.split(":11434")[-1], "keys": sorted(payload)})
            assert method == "POST" and url.endswith("/api/generate")
            assert len(payload["images"]) == 8
            sizes, colors = [], []
            for encoded in payload["images"]:
                raw = base64.b64decode(encoded, validate=True)
                assert raw.startswith(b"\x89PNG\r\n\x1a\n")
                with Image.open(io.BytesIO(raw)) as image:
                    image.load(); sizes.append(list(image.size))
                    assert max(image.size) <= 512
                    r, g, b = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
                    assert r > 200 and g < 50 and b < 50, "blue frames after 40 seconds must not be sent"
                    colors.append("red")
            assert not any("audio" in key.lower() for key in payload)
            evidence.update(frames=len(sizes), sizes=sizes, sampled_colors=colors,
                            image_payloads_only=True, late_blue_frames_sent=False)
            return {"model": "synthetic:vision", "done": True, "done_reason": "stop", "response": "synthetic response"}

        evidence = {}
        runner = LocalMediaBackend(config, transport=model_stub)
        request = {"agent": "video", "operation": "analyze", "source": str(source), "prompt": "Describe this synthetic clip"}
        result = execute(request, config, root / "valid-job", backend=runner)
        assert result["state"] == "RESULT_UNVERIFIED" and len(calls) == 1
        bad = root / "invalid.mp4"; bad.write_bytes(b"\x00\x00\x00\x18ftypisomcorrupt-video")
        request["source"] = str(bad)
        try:
            execute(request, config, root / "invalid-job", backend=runner)
        except MediaError as exc:
            assert exc.code == "REVIEW_REQUIRED"
        else:
            raise AssertionError("corrupt video accepted")
        refused = inspect(root / "invalid-job")
        assert refused["state"] == "REVIEW_REQUIRED" and refused["failure_code"] == "VIDEO_DECODE_FAILED"
        assert len(calls) == 1, "invalid video must not reach the model"
        version = subprocess.check_output(["/usr/bin/ffmpeg", "-version"], text=True, timeout=5).splitlines()[0]
        print(json.dumps({"status": "PASS", "ffmpeg": version, "fixture_seconds": 45,
                          "fixture_has_audio": True, "fixture_video_size": [1280, 720],
                          **evidence, "model_calls": calls, "corrupt_video_refused_before_model": True,
                          "real_ffmpeg": True, "real_model": False, "hardware_qualified": False}, indent=2))


if __name__ == "__main__":
    main()
