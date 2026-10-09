# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_preflight.py
# Description : Précontrôle sans effets, sondes bornées et métadonnées non fiables
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.media_cli import main
from eidolon_core.media_preflight import preflight, render_preflight

PNG = b"\x89PNG\r\n\x1a\nprivate-source-content"


def configured(operation="create"):
    fields = {"prompt": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"]}
    inputs = {"text": "", "width": 0, "height": 0, "checkpoint": "fixture.safetensors"}
    if operation == "edit":
        fields["source"] = ["1", "image"]; inputs["image"] = ""
    return {"comfy_endpoint": "http://127.0.0.1:8188", "source_transfer": "upload-verified",
            "ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "fixture:local",
            "workflows": {"image." + operation: {"prompt": {"1": {"class_type": "FixtureNode", "inputs": inputs}}, "bindings": fields}}}


def metadata():
    return {"FixtureNode": {"name": "FixtureNode", "input": {"required": {
        "text": ["STRING", {}], "width": ["INT", {}], "height": ["INT", {}],
        "checkpoint": [["fixture.safetensors"], {}]}}}}


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"; self.source.write_bytes(PNG)
        self.req = {"agent": "image", "operation": "create", "prompt": "private-prompt-canary", "format": "square"}

    def test_offline_never_opens_socket_starts_process_or_writes_job(self):
        req = dict(self.req, operation="edit", source=str(self.source))
        cfg = configured("edit"); original = copy.deepcopy(cfg)
        with patch("socket.create_connection", side_effect=AssertionError("network")), patch(
                "subprocess.run", side_effect=AssertionError("subprocess")):
            r = preflight(req, cfg, transport=lambda *a, **k: self.fail("transport"))
        self.assertEqual(r["state"], "LOCAL_INPUTS_VALID")
        self.assertEqual(r["probe_calls"], [])
        self.assertEqual([c["route"] for c in r["future_run_calls"]], ["/upload/image", "/view", "/prompt"])
        self.assertEqual(cfg, original)
        self.assertEqual(list(self.root.iterdir()), [self.source])
        self.assertNotIn("private-prompt-canary", json.dumps(r))
        self.assertNotIn("private-source-content", json.dumps(r))
        for field in ("submitted", "execution_authorized", "plan_reusable", "hardware_qualified"):
            self.assertFalse(r[field])

    def test_source_evidence_is_pinned_to_artifact_and_corruption_blocks_probe(self):
        root = self.root / "artifacts"; initialize(root); store = ArtifactStore(root)
        ref = store.import_file(self.source)["reference"]; self.source.unlink()
        cfg = configured("edit"); cfg["artifact_store"] = {"root": str(root), "store_id": store.store_id}
        req = dict(self.req, operation="edit", artifact=ref)
        r = preflight(req, cfg)
        self.assertEqual(r["source_evidence"]["artifact"], ref)
        (root / ref["artifact_id"] / "payload").write_bytes(PNG[:-1] + b"x")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_CONTENT_MISMATCH"):
            preflight(req, cfg, probe_local=True, transport=lambda *a, **k: self.fail("network"))

    def test_local_validation_fails_before_any_probe(self):
        for cfg in ({}, dict(configured(), comfy_endpoint="https://example.com:443")):
            with self.assertRaises(MediaError):
                preflight(self.req, cfg, probe_local=True, transport=lambda *a, **k: self.fail("network"))

    def test_fingerprints_change_with_input_and_configuration(self):
        a = preflight(self.req, configured())
        b = preflight(dict(self.req, prompt="another"), configured())
        self.assertNotEqual(a["request_sha256"], b["request_sha256"])
        self.assertEqual(a["configuration_sha256"], b["configuration_sha256"])
        c = preflight(self.req, dict(configured(), comfy_endpoint="http://127.0.0.1:9191"))
        self.assertNotEqual(a["configuration_sha256"], c["configuration_sha256"])

    def test_comfy_probe_reads_only_requested_node_metadata(self):
        calls = []
        def transport(*args, **kwargs): calls.append((args, kwargs)); return metadata()
        r = preflight(self.req, configured(), probe_local=True, transport=transport)
        self.assertEqual(r["state"], "PREREQUISITES_OBSERVED")
        self.assertEqual(calls, [(("GET", "http://127.0.0.1:8188/object_info/FixtureNode", None), {"timeout": 5})])
        self.assertEqual(r["checks"][0]["literal_choices_checked"], 1)
        self.assertFalse(r["hardware_qualified"])
        self.assertNotIn(self.req["prompt"], json.dumps(calls))

    def test_planned_upload_is_not_required_in_remote_input_file_list(self):
        cfg = configured("edit"); data = metadata()
        data["FixtureNode"]["input"]["required"]["image"] = [["already-there.png"], {}]
        r = preflight(dict(self.req, operation="edit", source=str(self.source)), cfg, probe_local=True,
                      transport=lambda *a, **k: data)
        self.assertEqual(r["state"], "PREREQUISITES_OBSERVED")
        self.assertEqual([c["method"] for c in r["probe_calls"]], ["GET"])

    def test_missing_checkpoint_or_required_input_is_detected(self):
        for code, mutate in (
            ("WORKFLOW_CHOICE_UNAVAILABLE", lambda v: v["FixtureNode"]["input"]["required"].update(checkpoint=[["other"], {}])),
            ("WORKFLOW_REQUIRED_INPUT_MISSING", lambda v: v["FixtureNode"]["input"]["required"].update(missing=["INT", {}]))):
            data = metadata(); mutate(data)
            r = preflight(self.req, configured(), probe_local=True, transport=lambda *a, **k: data)
            self.assertEqual(r["state"], "PROBE_INCOMPLETE"); self.assertEqual(r["failure_code"], code)

    def test_remote_or_wrong_node_metadata_is_not_treated_as_ready(self):
        for data, code in (({}, "NODE_METADATA_UNAVAILABLE"),
                           ({"FixtureNode": dict(metadata()["FixtureNode"], name="other")}, "NODE_METADATA_UNAVAILABLE"),
                           ({"FixtureNode": dict(metadata()["FixtureNode"], api_node=True)}, "REMOTE_NODE_DECLARED")):
            r = preflight(self.req, configured(), probe_local=True, transport=lambda *a, **k: data)
            self.assertEqual(r["failure_code"], code)

    def test_duplicate_node_classes_are_probed_once(self):
        cfg = configured(); flow = cfg["workflows"]["image.create"]["prompt"]
        flow["2"] = copy.deepcopy(flow["1"])
        r = preflight(self.req, cfg, probe_local=True, transport=lambda *a, **k: metadata())
        self.assertEqual(len(r["probe_calls"]), 1); self.assertEqual(r["checks"][0]["nodes"], ["1", "2"])

    def test_class_count_and_unsafe_routes_fail_before_any_contact(self):
        cfg = configured(); flow = cfg["workflows"]["image.create"]["prompt"]
        for i in range(2, 34): flow[str(i)] = {"class_type": "Class" + str(i), "inputs": {}}
        with self.assertRaisesRegex(MediaError, "PROBE_NODE_LIMIT"):
            preflight(self.req, cfg, probe_local=True, transport=lambda *a, **k: self.fail("network"))
        for name in ("../interrupt", "x?bad", "x%2fqueue", "bad\nnode"):
            cfg = configured(); cfg["workflows"]["image.create"]["prompt"]["1"]["class_type"] = name
            with self.assertRaisesRegex(MediaError, "INVALID_PROBE_NODE_CLASS"):
                preflight(self.req, cfg, probe_local=True, transport=lambda *a, **k: self.fail("network"))

    def test_first_failure_stops_without_retry_or_private_error_text(self):
        cfg = configured(); cfg["workflows"]["image.create"]["prompt"]["2"] = {"class_type": "NeverQueried", "inputs": {}}
        calls = []
        def fail(*args, **kwargs): calls.append(args); raise TimeoutError("private-secret")
        r = preflight(self.req, cfg, probe_local=True, transport=fail)
        self.assertEqual(len(calls), 1); self.assertEqual(r["failure_code"], "PROBE_FAILED")
        self.assertNotIn("private-secret", json.dumps(r))

    def test_ollama_probe_sends_model_name_without_prompt_or_image(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(args)
            return {"capabilities": ["completion", "vision"], "template": "private-template", "license": "private-license"}
        req = {"agent": "image", "operation": "analyze", "source": str(self.source), "prompt": self.req["prompt"]}
        r = preflight(req, configured(), probe_local=True, transport=transport)
        self.assertEqual(calls, [("POST", "http://127.0.0.1:11434/api/show", {"model": "fixture:local", "verbose": False})])
        self.assertEqual(r["state"], "PREREQUISITES_OBSERVED")
        self.assertNotIn("private-", json.dumps(r))
        self.assertNotIn("private-", json.dumps(calls))

    def test_model_capabilities_missing_wrong_or_remote_stay_unqualified(self):
        req = {"agent": "image", "operation": "analyze", "source": str(self.source), "prompt": "Describe"}
        for data, code in (({}, "MODEL_CAPABILITIES_UNAVAILABLE"), ({"capabilities": ["completion"]}, "VISION_NOT_ADVERTISED"),
                           ({"capabilities": ["vision"], "error": "private-failure"}, "MODEL_METADATA_ERROR"),
                           ({"capabilities": ["vision"], "remote_host": "private-host"}, "REMOTE_MODEL_DECLARED")):
            r = preflight(req, configured(), probe_local=True, transport=lambda *a, **k: data)
            self.assertEqual(r["failure_code"], code)
            self.assertFalse(r["hardware_qualified"])
            self.assertNotIn("private-host", json.dumps(r))

    def test_video_preflight_does_not_execute_a_configured_program(self):
        exe = self.root / "ffmpeg"; exe.write_text("#!/bin/sh\nexit 1\n"); exe.chmod(0o600)
        video = self.root / "video.mp4"; video.write_bytes(b"\x00\x00\x00\x18ftypisomfixture")
        req = {"agent": "video", "operation": "analyze", "source": str(video), "prompt": "Describe"}
        cfg = dict(configured(), ffmpeg=str(exe))
        with self.assertRaisesRegex(MediaError, "FFMPEG_NOT_EXECUTABLE"):
            preflight(req, cfg)
        exe.chmod(0o700)
        with patch("subprocess.run", side_effect=AssertionError("program executed")):
            r = preflight(req, cfg)
        self.assertEqual(r["state"], "LOCAL_INPUTS_VALID")
        self.assertFalse(r["hardware_qualified"])

    def test_cli_exit_status_distinguishes_local_failure_and_probe_incomplete(self):
        req = self.root / "request.json"; req.write_text(json.dumps(self.req))
        cfg = self.root / "config.json"; cfg.write_text(json.dumps(configured()))
        args = ["preflight", "--request", str(req), "--config", str(cfg)]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err): self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["state"], "LOCAL_INPUTS_VALID")
        out = io.StringIO()
        with patch("eidolon_core.media_preflight.json_http", return_value={}), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(args + ["--probe-local"]), 3)
        self.assertEqual(json.loads(out.getvalue())["state"], "PROBE_INCOMPLETE")
        cfg.write_text("{}"); out = io.StringIO(); err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err): self.assertEqual(main(args), 2)
        self.assertEqual(out.getvalue(), ""); self.assertIn("error", json.loads(err.getvalue()))

    def test_human_rendering_uses_ect_and_does_not_promise_execution(self):
        report = preflight(self.req, configured())
        text = render_preflight(report)
        self.assertIn("Eidolon Core Technologies (ECT)", text)
        self.assertIn("Local AI • Modular • Reliable • Reproducible", text)
        self.assertIn("Moteur non contacté", text)
        self.assertNotIn("private-prompt", text)


class RealHTTPProbeTests(unittest.TestCase):
    def test_only_metadata_routes_are_contacted_and_malformed_transport_is_refused(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            mode = "valid"
            def do_GET(self):
                calls.append((self.command, self.path))
                assert self.path == "/object_info/FixtureNode"
                if self.mode == "redirect":
                    self.send_response(302); self.send_header("Location", "/prompt"); self.end_headers(); return
                body = json.dumps(metadata()).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if self.mode == "duplicate_length": self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                calls.append((self.command, self.path))
                self.send_error(500)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            cfg = configured(); cfg["comfy_endpoint"] = "http://127.0.0.1:" + str(server.server_port)
            req = {"agent": "image", "operation": "create", "prompt": "private-prompt", "format": "square"}
            for mode, state in (("valid", "PREREQUISITES_OBSERVED"), ("redirect", "PROBE_INCOMPLETE"),
                                ("duplicate_length", "PROBE_INCOMPLETE")):
                Handler.mode = mode; calls.clear()
                result = preflight(req, cfg, probe_local=True)
                self.assertEqual(result["state"], state)
                self.assertEqual(calls, [("GET", "/object_info/FixtureNode")])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
