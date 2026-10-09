# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_transfer.py
# Description : Transfert ComfyUI réel en loopback et coupures avant soumission
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

from eidolon_core.media_agents import MediaError, execute, inspect
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.media_backends import LocalMediaBackend, poll_job
from eidolon_core.media_transfer import ensure_source, raw_http

PNG = b"\x89PNG\r\n\x1a\nsynthetic transfer"
MP4 = b"\x00\x00\x00\x18ftypisomsynthetic transfer"


def workflow(video=False):
    bindings = {"prompt": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"], "source": ["1", "source"]}
    if video:
        bindings["duration_seconds"] = ["1", "seconds"]
    return {"prompt": {"1": {"class_type": "SyntheticFixture", "inputs": {"text": "", "width": 0, "height": 0, "seconds": 0, "source": ""}}},
            "bindings": bindings}


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store_path = self.root / "artifacts"; initialize(self.store_path)
        self.store = ArtifactStore(self.store_path)
        self.calls, self.inputs, self.phases = [], {}, []
        self.failure = None; self.current_job = None
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.calls.append(self.path)
                if owner.current_job:
                    owner.phases.append(inspect(owner.current_job).get("phase"))
                body = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/upload/image":
                    if owner.failure == "redirect":
                        self.send_response(302); self.send_header("Location", "/do-not-follow"); self.end_headers(); return
                    msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
                    fields, file = {}, None
                    for part in msg.iter_parts():
                        if part.get_param("name", header="content-disposition") == "image":
                            file = part
                        else:
                            fields[part.get_param("name", header="content-disposition")] = part.get_payload(decode=True).decode()
                    owner.assertEqual(fields, {"type": "input", "overwrite": "false"})
                    name = file.get_filename(); content = file.get_payload(decode=True)
                    owner.inputs[name] = (content, file.get_content_type())
                    if owner.failure == "lost-upload":
                        self.close_connection = True; return
                    receipt = {"name": name, "subfolder": "", "type": "input"}
                    if owner.failure == "wrong-name":
                        receipt["name"] = "renamed.png"
                    if owner.failure == "wrong-folder":
                        receipt["subfolder"] = "elsewhere"
                    if owner.failure == "wrong-type":
                        receipt["type"] = "output"
                    self.reply(receipt)
                elif self.path == "/prompt":
                    prompt = json.loads(body)["prompt"]
                    source = prompt["1"]["inputs"]["source"]
                    owner.assertIn(source, owner.inputs)
                    if owner.failure == "lost-queue":
                        self.close_connection = True; return
                    self.reply({"prompt_id": "fixture-id"})
                else:
                    self.send_response(404); self.end_headers()
            def do_GET(self):
                owner.calls.append(self.path)
                if owner.current_job:
                    owner.phases.append(inspect(owner.current_job).get("phase"))
                if self.path.startswith("/view?"):
                    q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)
                    owner.assertEqual(q["type"], ["input"]); owner.assertEqual(q["subfolder"], [""])
                    body, kind = owner.inputs[q["filename"][0]]
                    if owner.failure == "tampered-source":
                        body = body[:-1] + b"X"
                    self.send_response(200); self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(body) + (1_000_000 if owner.failure == "oversized" else 0)))
                    self.end_headers(); self.wfile.write(body)
                else:
                    self.reply({"fixture-id": {"status": {"completed": True, "status_str": "success"}, "outputs": {}}})
            def reply(self, value):
                body = json.dumps(value).encode(); self.send_response(200)
                self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def inputs_for(self, video=False):
        body, agent = (MP4, "video") if video else (PNG, "image")
        ref = self.store.import_bytes(body, display_name="private name." + ("mp4" if video else "png"))["reference"]
        req = {"agent": agent, "operation": "edit", "prompt": "Améliore le contraste", "format": "landscape", "artifact": ref}
        if video:
            req["duration_seconds"] = 5
        cfg = {"comfy_endpoint": self.url, "source_transfer": "upload-verified",
               "artifact_store": {"root": str(self.store_path), "store_id": self.store.store_id},
               "workflows": {agent + ".edit": workflow(video)}}
        return req, cfg

    def test_real_loopback_upload_exact_recheck_then_queue(self):
        req, cfg = self.inputs_for(); self.current_job = self.root / "job"
        record = execute(req, cfg, self.current_job)
        self.assertEqual(record["state"], "QUEUED")
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.calls[0], "/upload/image"); self.assertTrue(self.calls[1].startswith("/view?")); self.assertEqual(self.calls[2], "/prompt")
        self.assertEqual(self.phases, ["SOURCE_UPLOAD_STARTED", "SOURCE_VERIFYING", "QUEUE_SUBMITTING"])
        self.assertEqual(record["phase"], "QUEUE_ACKNOWLEDGED")
        self.assertIn("SOURCE_VERIFIED", [s["phase"] for s in record["stages"]])
        self.assertTrue(next(iter(self.inputs)).startswith("eidolon-"))
        self.assertNotIn("private name", json.dumps(record["backend"]))
        self.assertEqual(poll_job(record)["state"], "ENGINE_COMPLETED_UNVERIFIED")

    def test_video_bytes_use_same_bounded_transfer_protocol(self):
        req, cfg = self.inputs_for(video=True); self.current_job = self.root / "job"
        record = execute(req, cfg, self.current_job)
        name = record["backend"]["source_name"]
        self.assertTrue(name.endswith(".mp4")); self.assertEqual(self.inputs[name], (MP4, "video/mp4"))

    def test_wrong_upload_receipts_never_verify_or_queue(self):
        for failure in ("wrong-name", "wrong-folder", "wrong-type"):
            with self.subTest(failure=failure):
                self.calls.clear(); self.failure = failure; req, cfg = self.inputs_for()
                self.current_job = self.root / failure
                with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
                    execute(req, cfg, self.current_job)
                self.assertEqual(self.calls, ["/upload/image"])
                self.assertEqual(inspect(self.current_job)["failure_code"], "INVALID_UPLOAD_RECEIPT")

    def test_changed_or_oversized_remote_source_never_queues(self):
        for failure in ("tampered-source", "oversized"):
            self.calls.clear(); self.failure = failure; req, cfg = self.inputs_for(); self.current_job = self.root / failure
            with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
                execute(req, cfg, self.current_job)
            self.assertEqual(len(self.calls), 2); self.assertNotIn("/prompt", self.calls)
            self.assertEqual(inspect(self.current_job)["phase"], "SOURCE_VERIFYING")

    def test_lost_upload_or_queue_response_is_never_retried(self):
        for failure, count, phase in (("lost-upload", 1, "SOURCE_UPLOAD_STARTED"), ("lost-queue", 3, "QUEUE_SUBMITTING")):
            self.calls.clear(); self.failure = failure; req, cfg = self.inputs_for(); self.current_job = self.root / failure
            with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
                execute(req, cfg, self.current_job)
            self.assertEqual(len(self.calls), count)
            self.assertEqual(inspect(self.current_job)["phase"], phase)
            with self.assertRaises(FileExistsError):
                execute(req, cfg, self.current_job)
            self.assertEqual(len(self.calls), count)

    def test_staged_mapping_is_now_reverified_before_queue(self):
        req, cfg = self.inputs_for(); cfg["source_transfer"] = "verify-staged"
        cfg["staged_sources"] = {req["artifact"]["sha256"]: "staged.png"}
        self.inputs["staged.png"] = (PNG[:-1] + b"X", "image/png")
        self.current_job = self.root / "job"
        with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
            execute(req, cfg, self.current_job)
        self.assertEqual(len(self.calls), 1); self.assertTrue(self.calls[0].startswith("/view?"))
        self.assertEqual(inspect(self.current_job)["failure_code"], "STAGED_SOURCE_MISMATCH")

    def test_redirect_upload_is_not_followed(self):
        self.failure = "redirect"; req, cfg = self.inputs_for(); self.current_job = self.root / "job"
        with self.assertRaises(MediaError):
            execute(req, cfg, self.current_job)
        self.assertEqual(self.calls, ["/upload/image"])

    def test_foreign_or_pathlike_names_refused_without_network(self):
        for name in ("../a.png", "/tmp/a.png", "a\\b.png", "bad\r\nname", "a..png"):
            with self.assertRaises(MediaError):
                ensure_source(PNG, {"sha256": hashlib.sha256(PNG).hexdigest(), "size": len(PNG), "type": "image/png"},
                              {"endpoint": self.url, "source_name": name, "source_transfer": "upload-verified"},
                              transport=lambda *a: self.fail("network"))

    def test_crashes_keep_phase_and_do_not_resubmit(self):
        code = """
import json,os,sys
import eidolon_core.media_agents as m
original=m.write_record
def checkpoint(directory,record):
    original(directory,record)
    if record.get('phase')==sys.argv[4]: os._exit(37)
m.write_record=checkpoint
m.execute(json.load(open(sys.argv[1])),json.load(open(sys.argv[2])),sys.argv[3])
"""
        for phase, expected_count in (("SOURCE_UPLOAD_ACKNOWLEDGED", 1), ("SOURCE_VERIFIED", 2), ("QUEUE_ACKNOWLEDGED", 3)):
            with self.subTest(phase=phase):
                self.calls.clear(); req, cfg = self.inputs_for(); self.current_job = self.root / phase
                r = self.root / "request.json"; c = self.root / "config.json"
                r.write_text(json.dumps(req)); c.write_text(json.dumps(cfg))
                done = subprocess.run([sys.executable, "-c", code, str(r), str(c), str(self.current_job), phase], env=os.environ.copy(), timeout=15)
                self.assertEqual(done.returncode, 37); self.assertEqual(len(self.calls), expected_count)
                record = inspect(self.current_job)
                self.assertEqual(record["observed_state"], "REVIEW_REQUIRED"); self.assertEqual(record["phase"], phase)
                with self.assertRaises(FileExistsError):
                    execute(req, cfg, self.current_job)
                self.assertEqual(len(self.calls), expected_count)
                if phase == "QUEUE_ACKNOWLEDGED":
                    self.assertEqual(poll_job(record)["state"], "ENGINE_COMPLETED_UNVERIFIED")
                    self.assertEqual(inspect(self.current_job)["state"], "INTENT")
                else:
                    with self.assertRaisesRegex(MediaError, "JOB_NOT_QUEUED"):
                        poll_job(record)


if __name__ == "__main__":
    unittest.main()
