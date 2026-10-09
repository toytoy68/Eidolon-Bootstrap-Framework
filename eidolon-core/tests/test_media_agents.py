# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_agents.py
# Description : Contrats média, effets incertains et moteurs HTTP locaux simulés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import base64
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import (MediaError, catalog, execute, identify, inspect,
                                      load_json, prepare, read_regular, write_record)
from eidolon_core.media_backends import LocalMediaBackend, endpoint, json_http, poll_job


PNG = b"\x89PNG\r\n\x1a\nsynthetic-fixture"


def request(agent="image", operation="create", source=None):
    return {"agent": agent, "operation": operation, "prompt": "Un atelier de robotique",
            "source": source, "format": None if operation == "analyze" else "landscape",
            "duration_seconds": 5 if agent == "video" and operation != "analyze" else None}


def config():
    workflows = {}
    for agent in ("image", "video"):
        for op in ("create", "edit"):
            bindings = {"prompt": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"]}
            if agent == "video":
                bindings["duration_seconds"] = ["1", "seconds"]
            if op == "edit":
                bindings["source"] = ["1", "source"]
            workflows[agent + "." + op] = {
                "prompt": {"1": {"class_type": "SyntheticTestNode", "inputs": {
                    "text": "", "width": 0, "height": 0, "seconds": 0, "source": ""}}}, "bindings": bindings}
    return {"comfy_endpoint": "http://127.0.0.1:8188", "workflows": workflows,
            "ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "test-vision:local"}


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "source.png"
        self.image.write_bytes(PNG)

    def test_catalog_installed_not_configured(self):
        for agent in catalog()["agents"]:
            self.assertTrue(agent["installed"])
            self.assertEqual(agent["operations"], ["create", "edit", "analyze"])
            self.assertFalse(agent["execution_from_home"])
            self.assertEqual(agent["engine"], "NOT_CONFIGURED")

    def test_six_operations_and_pure_prepare(self):
        for agent in ("image", "video"):
            for op in ("create", "edit", "analyze"):
                value = request(agent, op, "/not/read/by/prepare" if op != "create" else None)
                self.assertEqual(prepare(value), value)

    def test_reject_invalid_drafts(self):
        cases = [dict(request(), agent="audio"), dict(request(), operation="shell"),
                 dict(request(), prompt=" "), dict(request(), prompt="x" * 4001),
                 dict(request(), prompt="\ud800"), dict(request(), command="rm"),
                 request(operation="edit"), dict(request(), format="huge"),
                 dict(request("video"), duration_seconds=True),
                 dict(request(operation="analyze", source="a"), format="square")]
        for value in cases:
            with self.subTest(value=str(value)[:80]), self.assertRaises(MediaError):
                prepare(value)

    def test_refuse_json_duplicates_and_nonfinite(self):
        for data in (b'{"agent":1,"agent":2}', b'{"x":NaN}', b'[] trailing'):
            p = self.root / "bad.json"; p.write_bytes(data)
            with self.assertRaises(MediaError):
                load_json(p)

    def test_refuse_symlink_fifo_size_and_media_type(self):
        import os
        link = self.root / "link"; link.symlink_to(self.image)
        with self.assertRaises(OSError):
            read_regular(link, 100)
        fifo = self.root / "fifo"; os.mkfifo(fifo)
        with self.assertRaises(MediaError):
            read_regular(fifo, 100)
        with self.assertRaises(MediaError):
            read_regular(self.image, 1)
        with self.assertRaises(MediaError):
            identify(b'<svg onload="bad"/>')

    def test_loopback_only_no_credentials_query_or_redirect_destination(self):
        for value in ("http://localhost:80", "http://192.168.1.135:8188", "https://example.com", "http://127.0.0.1:80/path",
                      "http://u:p@127.0.0.1:80", "http://127.0.0.1:80?", "http://127.0.0.1:80#", "file:///tmp/a"):
            with self.subTest(value=value), self.assertRaises(MediaError):
                endpoint(value)
        self.assertEqual(endpoint("http://[::1]:8188/"), "http://[::1]:8188")

    def test_missing_workflow_blocks_before_job_or_network(self):
        with self.assertRaisesRegex(MediaError, "WORKFLOW_NOT_CONFIGURED"):
            execute(request(), {}, self.root / "job")
        self.assertFalse((self.root / "job").exists())

    def test_generation_binds_prompt_and_size_without_changing_config(self):
        cfg = config(); original = copy.deepcopy(cfg)
        engine = LocalMediaBackend(cfg, transport=lambda *a: {"prompt_id": "synthetic-123"})
        req = prepare(request()); flow = engine.workflow(req, None)
        self.assertEqual(flow["1"]["inputs"]["text"], req["prompt"])
        self.assertEqual(flow["1"]["inputs"]["width"], 1024)
        self.assertEqual(cfg, original)
        record = execute(req, cfg, self.root / "job", backend=engine)
        self.assertEqual(record["state"], "QUEUED")
        self.assertFalse(record["verified"])
        self.assertEqual(inspect(self.root / "job")["result"]["prompt_id"], "synthetic-123")
        self.assertEqual((self.root / "job").stat().st_mode & 0o777, 0o700)

    def test_existing_job_never_resubmitted(self):
        calls = []
        engine = LocalMediaBackend(config(), transport=lambda *a: calls.append(a) or {"prompt_id": "p"})
        execute(request(), config(), self.root / "job", backend=engine)
        with self.assertRaises(FileExistsError):
            execute(request(), config(), self.root / "job", backend=engine)
        self.assertEqual(len(calls), 1)

    def test_timeout_is_uncertain_without_retry(self):
        calls = []
        def lost(*args):
            calls.append(args)
            raise TimeoutError()
        with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
            execute(request(), config(), self.root / "job", backend=LocalMediaBackend(config(), transport=lost))
        record = inspect(self.root / "job")
        self.assertEqual(record["state"], "REVIEW_REQUIRED")
        self.assertEqual(len(calls), 1)

    def test_intent_durable_before_first_backend_call(self):
        def backend_call(*args):
            record = inspect(self.root / "job")
            self.assertEqual(record["state"], "INTENT")
            self.assertEqual(record["observed_state"], "REVIEW_REQUIRED")
            return {"prompt_id": "id"}
        execute(request(), config(), self.root / "job", backend=LocalMediaBackend(config(), transport=backend_call))

    def test_bad_comfy_receipt_never_success(self):
        for i, value in enumerate(({"prompt_id": "../escape"}, {"prompt_id": "id", "node_errors": {"1": "error"}}, {})):
            with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
                execute(request(), config(), self.root / str(i), backend=LocalMediaBackend(config(), transport=lambda *_, v=value: v))

    def test_edit_requires_hash_bound_staged_source(self):
        import hashlib
        cfg = config(); req = request(operation="edit", source=str(self.image))
        with self.assertRaisesRegex(MediaError, "SOURCE_NOT_STAGED"):
            execute(req, cfg, self.root / "no-stage")
        cfg["staged_sources"] = {hashlib.sha256(PNG).hexdigest(): "fixture.png"}
        calls = []
        engine = LocalMediaBackend(cfg, transport=lambda *a: calls.append(a) or {"prompt_id": "edit"},
                                   raw_transport=lambda *a: ("image/png", PNG))
        execute(req, cfg, self.root / "staged", backend=engine)
        self.assertEqual(calls[0][2]["prompt"]["1"]["inputs"]["source"], "fixture.png")

    def test_analysis_payload_and_unverified_result(self):
        calls = []
        def transport(*args):
            calls.append(args)
            return {"model": "test-vision:local", "done": True, "done_reason": "stop", "response": "Une image de test."}
        record = execute(request(operation="analyze", source=str(self.image)), config(), self.root / "job",
                         backend=LocalMediaBackend(config(), transport=transport))
        self.assertEqual(record["state"], "RESULT_UNVERIFIED")
        self.assertFalse(record["verified"])
        self.assertEqual(base64.b64decode(calls[0][2]["images"][0]), PNG)
        self.assertFalse(calls[0][2]["stream"])
        self.assertEqual(calls[0][2]["keep_alive"], 0)

    def test_truncated_wrong_model_and_error_analysis_rejected(self):
        for i, change in enumerate(({"done": False}, {"done_reason": "length"}, {"model": "wrong"}, {"error": "bad"}, {"response": ""})):
            value = {"model": "test-vision:local", "done": True, "done_reason": "stop", "response": "text"}; value.update(change)
            with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
                execute(request(operation="analyze", source=str(self.image)), config(), self.root / str(i),
                        backend=LocalMediaBackend(config(), transport=lambda *_, v=value: v))

    def test_poll_missing_history_not_permission_to_retry(self):
        rec = execute(request(), config(), self.root / "job", backend=LocalMediaBackend(config(), transport=lambda *a: {"prompt_id": "p"}))
        calls = []
        self.assertEqual(poll_job(rec, transport=lambda *a: calls.append(a) or {})["state"], "NOT_OBSERVED_IN_HISTORY")
        self.assertEqual(calls[0][0], "GET")
        self.assertIsNone(calls[0][2])
        result = poll_job(rec, transport=lambda *a: {"p": {"status": {"completed": True, "status_str": "success"}, "outputs": {"1": {"images": []}}}})
        self.assertEqual(result["state"], "ENGINE_COMPLETED_UNVERIFIED")
        self.assertFalse(result["output_verified"])

    def test_poll_corrupted_record_and_unknown_job_never_posts(self):
        for record in ({"schema": "media-job/1", "state": "QUEUED", "backend": []},
                       {"schema": "media-job/1", "state": "INTENT"}):
            with self.assertRaises(MediaError):
                poll_job(record, transport=lambda *args: self.fail("unexpected network call"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg unavailable")
    def test_video_real_decode_is_partial_and_without_audio(self):
        clip = self.root / "synthetic.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=2",
                        "-t", "1", "-an", "-c:v", "mpeg4", str(clip)], check=True, timeout=20)
        cfg = config(); cfg["ffmpeg"] = shutil.which("ffmpeg")
        calls = []
        def transport(*args):
            calls.append(args)
            return {"model": "test-vision:local", "done": True, "done_reason": "stop", "response": "Échantillon bleu."}
        result = execute(request("video", "analyze", str(clip)), cfg, self.root / "video",
                         backend=LocalMediaBackend(cfg, transport=transport))["result"]
        self.assertTrue(1 <= result["frames_analyzed"] <= 8)
        self.assertEqual(result["coverage"], "first_40s_up_to_8_frames_no_audio")
        self.assertFalse(result["audio_analyzed"])
        self.assertEqual(len(calls), 1)


class HttpTests(unittest.TestCase):
    def test_real_http_framing_redirect_refusal_and_no_retry(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append(self.path)
                payload = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/redirect":
                    self.send_response(302); self.send_header("Location", "/should-not-call"); self.end_headers(); return
                body = json.dumps({"prompt_id": "loopback", "received": json.loads(payload)}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = "http://127.0.0.1:" + str(server.server_port)
            self.assertEqual(json_http("POST", base + "/prompt", {"prompt": {}})["prompt_id"], "loopback")
            with self.assertRaises(MediaError):
                json_http("POST", base + "/redirect", {})
            self.assertEqual(calls, ["/prompt", "/redirect"])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
