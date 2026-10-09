# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_setup.py
# Description : Configuration média hors ligne, périmètre choisi et absence d'effets
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError, prepare
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.media_backends import LocalMediaBackend
from eidolon_core.media_cli import main
from eidolon_core.media_setup import check_configuration, render_configuration
from eidolon_core.media_workflows import OPERATIONS


def workflow(agent, operation):
    fields = {"prompt": "text", "width": "width", "height": "height"}
    if agent == "video": fields["duration_seconds"] = "seconds"
    if operation == "edit": fields["source"] = "source"
    return {"prompt": {"1": {"class_type": "Fixture", "inputs": {v: "private-template" for v in fields.values()}}},
            "bindings": {k: ["1", v] for k, v in fields.items()}}


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ffmpeg = self.root / "ffmpeg"; self.ffmpeg.write_text("#!/bin/sh\nexit 91\n"); self.ffmpeg.chmod(0o700)
        self.config = {"ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "fixture:local",
                       "comfy_endpoint": "http://127.0.0.1:8188", "ffmpeg": str(self.ffmpeg),
                       "workflows": {a + "." + o: workflow(a, o) for a in ("image", "video") for o in ("create", "edit")}}

    def row(self, report, key):
        return next(row for row in report["operations"] if row["operation"] == key)

    def test_empty_configuration_is_incomplete_with_six_actionable_rows(self):
        report = check_configuration({})
        self.assertEqual(report["state"], "INCOMPLETE")
        self.assertEqual([r["operation"] for r in report["operations"]], list(OPERATIONS))
        self.assertTrue(all(r["state"] == "NOT_CONFIGURED" and r["issues"] for r in report["operations"]))
        self.assertTrue(all(i["action"] for r in report["operations"] for i in r["issues"]))

    def test_complete_configuration_has_no_source_network_process_or_mutation(self):
        before = copy.deepcopy(self.config)
        with patch("socket.socket", side_effect=AssertionError("socket")), patch(
                "subprocess.run", side_effect=AssertionError("process")), patch(
                "eidolon_core.media_agents.read_source", side_effect=AssertionError("source")):
            report = check_configuration(self.config)
        self.assertEqual(report["state"], "CONFIGURED_SCOPE")
        self.assertTrue(all(r["state"] == "CONFIGURED" for r in report["operations"]))
        self.assertEqual(self.config, before)
        self.assertEqual(list(self.root.iterdir()), [self.ffmpeg])
        self.assertNotIn("private-template", json.dumps(report))
        self.assertNotIn(str(self.root), json.dumps(report))
        for name in ("server_contacted", "source_content_read", "process_started", "job_created",
                     "execution_authorized", "hardware_qualified", "runtime_catalog_registered", "execution_from_home"):
            self.assertIs(report[name], False)

    def test_selected_analysis_does_not_require_generation_or_video_configuration(self):
        config = {"ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "fixture:local"}
        report = check_configuration(config, require=["image.analyze", "image.analyze"])
        self.assertEqual(report["state"], "CONFIGURED_SCOPE")
        self.assertEqual(report["required_operations"], ["image.analyze"])
        self.assertEqual(self.row(report, "video.analyze")["state"], "NOT_CONFIGURED")
        self.assertEqual(report["artifact_store"]["state"], "NOT_CONFIGURED")

    def test_invalid_scope_fails_before_artifact_marker_is_read(self):
        for require in ([], "image.analyze", [True], ["image.delete"]):
            with self.subTest(require=require), patch("eidolon_core.media_setup.ArtifactStore", side_effect=AssertionError("file access")):
                with self.assertRaisesRegex(MediaError, "INVALID_REQUIRED_OPERATIONS"):
                    check_configuration(self.config, require=require)

    def test_unknown_fields_workflows_and_malformed_common_settings_are_refused(self):
        with self.assertRaisesRegex(MediaError, "INVALID_MEDIA_CONFIG"):
            check_configuration(dict(self.config, token="private-token"))
        for mutate, code in ((lambda c: c["workflows"].update({"image.typo": {}}), "UNKNOWN_WORKFLOW_OPERATION"),
                             (lambda c: c.update(workflows=[]), "INVALID_WORKFLOW_CONFIG"),
                             (lambda c: c.update(staged_sources={"bad": "../private"}), "INVALID_STAGED_SOURCES")):
            config = copy.deepcopy(self.config); mutate(config)
            report = check_configuration(config, require=["image.analyze"])
            self.assertEqual(report["state"], "INVALID")
            self.assertIn(code, [e["code"] for e in report["issues"]])

    def test_invalid_unused_configuration_is_not_hidden_by_selected_scope(self):
        config = dict(self.config, comfy_endpoint="https://private.example:443")
        report = check_configuration(config, require=["image.analyze"])
        self.assertEqual(report["state"], "INVALID")
        self.assertEqual(self.row(report, "image.analyze")["state"], "CONFIGURED")
        self.assertNotIn("private.example", json.dumps(report))

    def test_workflow_binding_errors_match_actual_backend_validation(self):
        for mutate in (lambda w: w["bindings"].pop("height"),
                       lambda w: w["bindings"].update(height=["1", "width"]),
                       lambda w: w["bindings"].update(height=["1", "missing"])):
            config = copy.deepcopy(self.config); mutate(config["workflows"]["image.create"])
            report = check_configuration(config)
            row = self.row(report, "image.create")
            self.assertEqual(row["state"], "INVALID")
            request = prepare({"agent": "image", "operation": "create", "prompt": "fixture", "format": "square"})
            with self.assertRaises(MediaError) as caught:
                LocalMediaBackend(config).workflow(request, None)
            self.assertEqual(caught.exception.code, row["issues"][0]["code"])

    def test_edit_requires_source_binding_without_reading_any_source(self):
        config = copy.deepcopy(self.config)
        config["workflows"]["image.edit"]["bindings"].pop("source")
        row = self.row(check_configuration(config), "image.edit")
        self.assertEqual(row["state"], "INVALID")
        self.assertIn("WORKFLOW_BINDINGS_MISMATCH", [e["code"] for e in row["issues"]])

    def test_create_may_declare_source_but_no_source_evidence_is_fabricated(self):
        config = copy.deepcopy(self.config)
        config["workflows"]["image.create"] = workflow("image", "edit")
        report = check_configuration(config)
        self.assertTrue(self.row(report, "image.create")["source_required"])
        self.assertEqual(report["state"], "CONFIGURED_SCOPE")
        self.assertNotIn("source_evidence", report)
        self.assertEqual(report["staged_source_count"], 0)
        self.assertFalse(report["staged_sources_content_checked"])

    def test_ffmpeg_and_model_errors_are_local_and_do_not_echo_paths(self):
        self.ffmpeg.chmod(0o600)
        report = check_configuration(self.config)
        self.assertEqual(self.row(report, "video.analyze")["issues"][0]["code"], "FFMPEG_NOT_EXECUTABLE")
        report = check_configuration(dict(self.config, vision_model="private\nmodel"))
        self.assertIn("VISION_MODEL_NOT_CONFIGURED", [e["code"] for e in self.row(report, "image.analyze")["issues"]])
        self.assertNotIn("private", json.dumps(report))

    def test_empty_or_control_character_node_class_is_rejected(self):
        for name in ("", "bad\nnode", "a" * 161):
            config = copy.deepcopy(self.config)
            config["workflows"]["image.create"]["prompt"]["1"]["class_type"] = name
            row = self.row(check_configuration(config), "image.create")
            self.assertEqual(row["state"], "INVALID")
            self.assertEqual(row["issues"][0]["code"], "INVALID_WORKFLOW_NODE")

    def test_large_template_is_not_reported_as_configured(self):
        config = copy.deepcopy(self.config)
        config["workflows"]["image.create"]["prompt"]["1"]["inputs"]["fixed"] = "x" * 500_000
        row = self.row(check_configuration(config), "image.create")
        self.assertEqual(row["state"], "INVALID")
        self.assertIn("WORKFLOW_TOO_LARGE", [e["code"] for e in row["issues"]])

    def test_artifact_identity_check_does_not_read_inventory_or_payload(self):
        root = self.root / "artifacts"; marker = initialize(root)
        store = ArtifactStore(root)
        source = self.root / "fixture.png"; source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        ref = store.import_file(source)["reference"]
        (root / ref["artifact_id"] / "payload").write_bytes(b"changed")
        config = dict(self.config, artifact_store={"root": str(root), "store_id": marker["store_id"]})
        with patch.object(ArtifactStore, "inventory", side_effect=AssertionError("inventory")), patch.object(
                ArtifactStore, "read", side_effect=AssertionError("payload")):
            report = check_configuration(config)
        self.assertEqual(report["state"], "CONFIGURED_SCOPE")
        self.assertEqual(report["artifact_store"]["state"], "IDENTITY_OBSERVED")
        self.assertFalse(report["artifact_store"]["contents_checked"])

    def test_foreign_or_missing_artifact_store_is_invalid_without_creating_it(self):
        missing = self.root / "private-missing"
        config = dict(self.config, artifact_store={"root": str(missing), "store_id": "mas-" + "1" * 32})
        report = check_configuration(config)
        self.assertEqual(report["state"], "INVALID"); self.assertFalse(missing.exists())
        self.assertNotIn("private-missing", json.dumps(report))
        initialize(missing)
        report = check_configuration(config)
        self.assertIn("ARTIFACT_STORE_MISMATCH", [e["code"] for e in report["issues"]])

    def test_fingerprint_tracks_configuration_and_human_output_is_ect(self):
        report = check_configuration(self.config)
        other = check_configuration(dict(self.config, comfy_endpoint="http://127.0.0.1:8190"))
        self.assertNotEqual(report["configuration_sha256"], other["configuration_sha256"])
        text = render_configuration(report)
        self.assertIn("Eidolon Core Technologies (ECT)", text)
        self.assertIn("Local AI • Modular • Reliable • Reproducible", text)
        self.assertIn("configuration structurelle vérifiée", text)
        self.assertNotIn("private-template", text)

    def test_cli_json_human_and_errors_preserve_exit_status_and_channels(self):
        path = self.root / "config.json"; path.write_text(json.dumps(self.config))
        args = ["config-check", "--config", str(path)]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["state"], "CONFIGURED_SCOPE"); self.assertEqual(err.getvalue(), "")
        path.write_text("{}"); out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):self.assertEqual(main(args + ["--format", "human"]), 2)
        self.assertIn("configuration à compléter", out.getvalue())
        path.write_text('{"bad":"private-secret"}'); out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):self.assertEqual(main(args + ["--format", "human"]), 2)
        self.assertEqual(out.getvalue(), ""); self.assertIn("[ERREUR] INVALID_MEDIA_CONFIG", err.getvalue())
        self.assertNotIn("private-secret", err.getvalue())
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):self.assertEqual(main(args), 2)
        self.assertEqual(out.getvalue(), ""); self.assertEqual(json.loads(err.getvalue())["error"], "INVALID_MEDIA_CONFIG")

    def test_real_cli_audit_observes_no_network_process_database_or_write(self):
        path = self.root / "config.json"; path.write_text(json.dumps(self.config))
        original = (path.read_bytes(), path.stat().st_mtime_ns)
        script = r'''
import json,os,sys
from eidolon_core.media_cli import main
events=[]
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.posix_spawn','sqlite3.connect','os.mkdir','os.rename','os.remove','os.chmod'}:events.append(event)
 if event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or args[2] & (os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_RDWR)):events.append('write')
sys.addaudithook(audit)
status=main(['config-check','--config',sys.argv[1]])
print(json.dumps({'exit':status,'events':events}),file=sys.stderr)
'''
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-c", script, str(path)], env=env, capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stderr), {"exit": 0, "events": []})
        self.assertEqual(json.loads(result.stdout)["state"], "CONFIGURED_SCOPE")
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), original)


if __name__ == "__main__":unittest.main()
