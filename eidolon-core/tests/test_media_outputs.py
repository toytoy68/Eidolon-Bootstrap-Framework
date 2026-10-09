# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_outputs.py
# Description : Historique moteur lié, sorties bornées et import partiel explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError, write_record
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.media_outputs import collect, descriptors, inspect_collection

PNG = b"\x89PNG\r\n\x1a\nsynthetic output"


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.artifacts = self.root / "artifacts"
        initialize(self.artifacts); self.store = ArtifactStore(self.artifacts)
        self.job = self.root / "job"; self.job.mkdir(mode=0o700)
        self.flow = {"1": {"class_type": "SyntheticSave", "inputs": {"text": "fixture"}}}
        digest = hashlib.sha256(json.dumps(self.flow, sort_keys=True).encode()).hexdigest()
        self.record = {"schema": "media-job/1", "id": "media-" + "a" * 32, "agent": "image", "operation": "create",
                       "state": "QUEUED", "backend": {"adapter": "comfyui-prompt/2", "endpoint": "http://127.0.0.1:8188", "workflow_sha256": digest},
                       "result": {"prompt_id": "fixture-id"}}
        write_record(self.job, self.record)
        self.ref = {"filename": "result.png", "subfolder": "run-1", "type": "output"}
        self.history = {"fixture-id": {"status": {"completed": True, "status_str": "success"},
                                       "prompt": [1, "fixture-id", self.flow, {}, ["1"]],
                                       "outputs": {"1": {"images": [self.ref]}}}}
        self.calls = []

    def run_collect(self, name="collection", *, binary=None):
        def transport(*args):
            self.calls.append(args); return copy.deepcopy(self.history)
        def raw(*args):
            self.calls.append(args); return "image/png", PNG
        return collect(self.job, self.artifacts, self.store.store_id, self.root / name,
                       transport=transport, binary_transport=binary or raw)

    def test_collect_exact_bytes_with_provenance_not_semantic_success(self):
        original = (self.job / "job.json").read_bytes()
        record = self.run_collect()
        self.assertEqual(record["state"], "OUTPUTS_IMPORTED_UNVERIFIED")
        self.assertFalse(record["semantic_content_verified"])
        self.assertEqual([c[0] for c in self.calls], ["GET", "GET"])
        self.assertIn("type=output", self.calls[-1][1])
        artifact = record["artifacts"][0]
        self.assertEqual(self.store.read(artifact["reference"])[0], PNG)
        self.assertEqual(artifact["provenance"]["job_id"], self.record["id"])
        self.assertEqual(artifact["provenance"]["collection_id"], record["id"])
        self.assertEqual((self.job / "job.json").read_bytes(), original)
        self.assertEqual(inspect_collection(self.root / "collection")["state"], record["state"])

    def test_duplicate_collection_does_not_repeat_downloads(self):
        self.run_collect(); self.calls.clear()
        with self.assertRaises(FileExistsError):
            self.run_collect()
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.store.inventory()["artifacts"]), 1)

    def test_incomplete_or_wrong_workflow_blocks_all_binary_reads(self):
        cases = []
        for mutate in (lambda h: h["fixture-id"]["status"].update(completed=False),
                       lambda h: h["fixture-id"]["status"].update(status_str="error"),
                       lambda h: h["fixture-id"].pop("prompt"),
                       lambda h: h["fixture-id"]["prompt"].__setitem__(1, "another"),
                       lambda h: h["fixture-id"]["prompt"][2]["1"]["inputs"].update(text="other")):
            h = copy.deepcopy(self.history); mutate(h); cases.append(h)
        for n, h in enumerate(cases):
            self.history = h
            with self.assertRaisesRegex(MediaError, "COLLECTION_INCOMPLETE"):
                self.run_collect(str(n), binary=lambda *a: self.fail("binary read"))
            self.assertEqual(inspect_collection(self.root / str(n))["artifacts"], [])

    def test_paths_foreign_nodes_temporary_and_duplicate_refs_rejected(self):
        for value in (dict(self.ref, filename="../secret.png"), dict(self.ref, subfolder="../../input"),
                      dict(self.ref, filename="https://evil/image.png"), dict(self.ref, type="input"),
                      dict(self.ref, type="temp"), dict(self.ref, filename="preview.svg"), dict(self.ref, subfolder="/abs")):
            h = copy.deepcopy(self.history); h["fixture-id"]["outputs"]["1"]["images"] = [value]
            with self.assertRaises(MediaError):
                descriptors(h, self.record)
        h = copy.deepcopy(self.history); h["fixture-id"]["outputs"]["2"] = h["fixture-id"]["outputs"]["1"]
        with self.assertRaisesRegex(MediaError, "INVALID_OUTPUT_NODE"):
            descriptors(h, self.record)
        h = copy.deepcopy(self.history); h["fixture-id"]["outputs"]["1"]["images"].append(dict(self.ref))
        with self.assertRaisesRegex(MediaError, "DUPLICATE_OUTPUT_REFERENCE"):
            descriptors(h, self.record)

    def test_count_and_total_byte_limits(self):
        h = copy.deepcopy(self.history)
        h["fixture-id"]["outputs"]["1"]["images"] = [dict(self.ref, filename=f"a{i}.png") for i in range(17)]
        with self.assertRaises(MediaError):
            descriptors(h, self.record)
        with patch("eidolon_core.media_outputs.MAX_COLLECTION_BYTES", len(PNG) - 1), self.assertRaises(MediaError):
            self.run_collect()
        self.assertEqual(self.store.inventory()["artifacts"], [])

    def test_mime_header_or_payload_mismatch_is_not_imported(self):
        for n, response in enumerate((("image/png", b"<html>bad</html>"), ("text/html", PNG), ("image/png", b""))):
            with self.assertRaises(MediaError):
                self.run_collect(str(n), binary=lambda *a, r=response: r)
        self.assertEqual(self.store.inventory()["artifacts"], [])

    def test_partial_collection_keeps_first_artifact_and_stops(self):
        self.history["fixture-id"]["outputs"]["1"]["images"].append(dict(self.ref, filename="second.png"))
        reads = []
        def binary(*args):
            reads.append(args)
            if len(reads) == 2:
                raise TimeoutError()
            return "image/png", PNG
        with self.assertRaisesRegex(MediaError, "COLLECTION_INCOMPLETE"):
            self.run_collect(binary=binary)
        record = inspect_collection(self.root / "collection")
        self.assertEqual(len(record["artifacts"]), 1)
        self.assertEqual(record["output_index"], 1)
        self.assertEqual(self.store.read(record["artifacts"][0]["reference"])[0], PNG)
        self.assertEqual(len(reads), 2)

    def test_crash_after_import_is_traceable_without_automatic_retry(self):
        original = ArtifactStore.import_bytes
        class Crash(BaseException):
            pass
        def interrupted(store, body, **kwargs):
            original(store, body, **kwargs)
            raise Crash()
        with patch.object(ArtifactStore, "import_bytes", interrupted), self.assertRaises(Crash):
            self.run_collect()
        record = inspect_collection(self.root / "collection")
        self.assertEqual(record["observed_state"], "COLLECTION_INCOMPLETE")
        self.assertEqual(record["phase"], "OUTPUT_IMPORTING")
        self.assertEqual(record["pending_import"]["sha256"], hashlib.sha256(PNG).hexdigest())
        artifact = self.store.inventory()["artifacts"][0]
        self.assertEqual(artifact["provenance"]["collection_id"], record["id"])
        self.assertEqual(artifact["provenance"], record["pending_import"]["provenance"])
        self.calls.clear()
        with self.assertRaises(FileExistsError):
            self.run_collect()
        self.assertEqual(self.calls, [])

    def test_acknowledged_before_crash_can_be_collected_without_changing_job(self):
        self.record["state"] = "INTENT"; self.record["phase"] = "QUEUE_ACKNOWLEDGED"
        self.record["phase_evidence"] = self.record.pop("result"); write_record(self.job, self.record)
        result = self.run_collect()
        self.assertEqual(result["state"], "OUTPUTS_IMPORTED_UNVERIFIED")
        self.assertEqual(json.loads((self.job / "job.json").read_text())["state"], "INTENT")

    def test_video_output_is_not_an_image_result(self):
        h = copy.deepcopy(self.history); h["fixture-id"]["outputs"]["1"]["images"][0]["filename"] = "result.mp4"
        with self.assertRaisesRegex(MediaError, "OUTPUT_TYPE_MISMATCH"):
            descriptors(h, self.record)
        record = dict(self.record, agent="video")
        self.assertEqual(descriptors(h, record)[0]["media_type"], "video/mp4")

    def test_empty_history_or_no_saved_outputs_never_marks_completion(self):
        for h in ({}, {"fixture-id": dict(self.history["fixture-id"], outputs={})}):
            with self.assertRaises(MediaError):
                descriptors(h, self.record)


if __name__ == "__main__":
    unittest.main()
