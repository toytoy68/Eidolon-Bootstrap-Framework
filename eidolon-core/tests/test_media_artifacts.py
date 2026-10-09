# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_artifacts.py
# Description : Références, intégrité, quotas, concurrence et coupures des artefacts
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError, execute, prepare
from eidolon_core.media_artifacts import ArtifactStore, initialize, validate_reference
from eidolon_core.media_backends import LocalMediaBackend

PNG = b"\x89PNG\r\n\x1a\nsynthetic artifact"


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / "artifacts"
        self.marker = initialize(self.root)
        self.store = ArtifactStore(self.root)

    def imported(self):
        return self.store.import_bytes(PNG, display_name="photo.png")

    def test_new_private_store_no_reinitialization(self):
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / "store.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            initialize(self.root)
        self.assertEqual(ArtifactStore(self.root).store_id, self.marker["store_id"])
        self.assertFalse(self.store.inventory()["content_hashes_checked"])

    def test_import_and_read_opaque_reference_and_content(self):
        manifest = self.imported(); ref = manifest["reference"]
        self.assertNotIn("path", ref)
        self.assertEqual(ref["sha256"], hashlib.sha256(PNG).hexdigest())
        body, read = self.store.read(ref)
        self.assertEqual(body, PNG); self.assertEqual(read, manifest)
        inv = self.store.inventory()
        self.assertEqual(inv["bytes"], len(PNG)); self.assertEqual(inv["pending_review"], [])
        self.assertEqual(inv["artifacts"], [manifest])

    def test_duplicate_names_do_not_replace_artifact(self):
        first = self.imported(); second = self.imported()
        self.assertNotEqual(first["reference"]["artifact_id"], second["reference"]["artifact_id"])
        self.assertEqual(len(self.store.inventory()["artifacts"]), 2)
        self.assertEqual(self.store.read(first["reference"])[0], PNG)

    def test_bad_reference_never_becomes_a_path(self):
        ref = self.imported()["reference"]
        for changed in (dict(ref, artifact_id="../secret"), dict(ref, sha256="0"), dict(ref, path="/tmp/x"),
                        dict(ref, store_id=True), dict(ref, schema="future")):
            with self.assertRaises(MediaError):
                validate_reference(changed)

    def test_other_store_or_hash_is_refused(self):
        ref = self.imported()["reference"]
        other = self.base / "other"; initialize(other)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_STORE_MISMATCH"):
            ArtifactStore(other).read(ref)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_REFERENCE_MISMATCH"):
            self.store.read(dict(ref, sha256="0" * 64))

    def test_root_replacement_detected_by_live_store_and_config(self):
        ref = self.imported()["reference"]
        self.root.rename(self.base / "old"); initialize(self.root)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_STORE_CHANGED"):
            self.store.read(ref)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_STORE_MISMATCH"):
            ArtifactStore(self.root, expected_store_id=ref["store_id"])

    def test_same_size_mutation_detected_before_returning_content(self):
        ref = self.imported()["reference"]
        payload = self.root / ref["artifact_id"] / "payload"
        payload.write_bytes(PNG[:-1] + b"X")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_CONTENT_MISMATCH"):
            self.store.read(ref)

    def test_truncation_and_unexpected_files_block_inventory(self):
        ref = self.imported()["reference"]
        payload = self.root / ref["artifact_id"] / "payload"; payload.write_bytes(b"bad")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_CHANGED"):
            self.store.inventory()
        payload.write_bytes(PNG)
        (self.root / "unexpected").write_text("x")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_UNEXPECTED_ENTRY"):
            self.store.import_bytes(PNG, display_name="new.png")

    def test_no_links_in_private_artifacts(self):
        ref = self.imported()["reference"]; payload = self.root / ref["artifact_id"] / "payload"
        backup = self.base / "saved"; payload.rename(backup); payload.symlink_to(backup)
        with self.assertRaises((MediaError, OSError)):
            self.store.read(ref)
        payload.unlink(); os.link(backup, payload)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_PERMISSIONS"):
            self.store.read(ref)
        alias = self.base / "alias"; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            ArtifactStore(alias)

    def test_permissions_refused_and_not_repaired_implicitly(self):
        ref = self.imported()["reference"]; payload = self.root / ref["artifact_id"] / "payload"
        payload.chmod(0o644)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_PERMISSIONS"):
            self.store.read(ref)
        self.assertEqual(payload.stat().st_mode & 0o777, 0o644)

    def test_import_source_symlink_and_fifo_never_block(self):
        source = self.base / "source"; source.write_bytes(PNG)
        alias = self.base / "alias"; alias.symlink_to(source)
        with self.assertRaises(OSError):
            self.store.import_file(alias)
        fifo = self.base / "fifo"; os.mkfifo(fifo)
        with self.assertRaises(MediaError):
            self.store.import_file(fifo)

    def test_image_and_store_byte_limits_before_publication(self):
        with patch("eidolon_core.media_artifacts.MAX_IMAGE", 10), self.assertRaisesRegex(MediaError, "IMAGE_TOO_LARGE"):
            self.imported()
        small = self.base / "small"; initialize(small, max_bytes=len(PNG) - 1)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_QUOTA_EXCEEDED"):
            ArtifactStore(small).import_bytes(PNG, display_name="small.png")
        self.assertEqual(ArtifactStore(small).inventory()["artifacts"], [])

    def test_count_limit_and_bytes_are_cumulative(self):
        root = self.base / "quota"; initialize(root, max_artifacts=1, max_bytes=2 * len(PNG))
        store = ArtifactStore(root); first = store.import_bytes(PNG, display_name="1.png")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_QUOTA_EXCEEDED"):
            store.import_bytes(PNG, display_name="2.png")
        self.assertEqual(store.read(first["reference"])[0], PNG)

    def test_writer_contention_refused_without_creating_staging(self):
        with (self.root / "writer.lock").open("rb") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(MediaError, "ARTIFACT_STORE_BUSY"):
                self.imported()
        self.assertEqual(self.store.inventory()["pending_review"], [])
        self.imported()

    def test_malformed_manifest_and_marker_are_not_adopted(self):
        manifest = self.imported(); folder = self.root / manifest["reference"]["artifact_id"]
        path = folder / "manifest.json"; manifest["media_type"] = []
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(MediaError, "INVALID_ARTIFACT_MANIFEST"):
            self.store.inventory()
        marker = dict(self.marker, max_artifacts=True)
        (self.root / "store.json").write_text(json.dumps(marker))
        with self.assertRaisesRegex(MediaError, "INVALID_ARTIFACT_STORE"):
            ArtifactStore(self.root)

    def test_display_name_is_metadata_not_a_path(self):
        for name in ("../x", "/tmp/x", "a\\b", "bad\nname", "", "\ud800"):
            with self.assertRaises(MediaError):
                self.store.import_bytes(PNG, display_name=name)
        self.assertEqual(self.store.inventory()["artifacts"], [])

    def test_process_death_at_four_publication_boundaries(self):
        code = """
import os,sys
from eidolon_core.media_artifacts import ArtifactStore
store=ArtifactStore(sys.argv[1])
store._checkpoint=lambda stage: os._exit(31) if stage==sys.argv[2] else None
store.import_bytes(b'\\x89PNG\\r\\n\\x1a\\nsynthetic artifact', display_name='test.png')
"""
        for stage in ("staging-created", "payload-durable", "manifest-durable", "renamed"):
            with self.subTest(stage=stage):
                root = self.base / stage; initialize(root)
                completed = subprocess.run([sys.executable, "-c", code, str(root), stage], env=os.environ.copy(), timeout=10)
                self.assertEqual(completed.returncode, 31)
                store = ArtifactStore(root); inv = store.inventory()
                if stage != "renamed":
                    self.assertEqual(len(inv["pending_review"]), 1); self.assertEqual(inv["artifacts"], [])
                    with self.assertRaisesRegex(MediaError, "ARTIFACT_RECOVERY_REQUIRED"):
                        store.import_bytes(PNG, display_name="next.png")
                else:
                    self.assertEqual(inv["pending_review"], [])
                    self.assertEqual(len(inv["artifacts"]), 1)
                    self.assertEqual(store.read(inv["artifacts"][0]["reference"])[0], PNG)

    def test_analysis_uses_frozen_artifact_not_original_source(self):
        source = self.base / "source.png"; source.write_bytes(PNG)
        ref = self.store.import_file(source)["reference"]; source.unlink()
        request = {"agent": "image", "operation": "analyze", "prompt": "Décris", "artifact": ref}
        cfg = {"artifact_store": {"root": str(self.root), "store_id": self.store.store_id},
               "ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "test:local"}
        calls = []
        backend = LocalMediaBackend(cfg, transport=lambda *a: calls.append(a) or {
            "model": "test:local", "done": True, "done_reason": "stop", "response": "test"})
        result = execute(request, cfg, self.base / "job", backend=backend)
        self.assertEqual(result["state"], "RESULT_UNVERIFIED")
        self.assertEqual(result["source_evidence"]["artifact"], ref)
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(MediaError, "SOURCE_AND_ARTIFACT_CONFLICT"):
            prepare(dict(request, source=str(source)))

    def test_corrupt_artifact_never_contacts_engine_or_creates_job(self):
        ref = self.imported()["reference"]
        (self.root / ref["artifact_id"] / "payload").write_bytes(PNG[:-1] + b"X")
        cfg = {"artifact_store": {"root": str(self.root), "store_id": self.store.store_id},
               "ollama_endpoint": "http://127.0.0.1:11434", "vision_model": "test:local"}
        with self.assertRaises(MediaError):
            execute({"agent": "image", "operation": "analyze", "prompt": "Décris", "artifact": ref},
                    cfg, self.base / "job", backend=LocalMediaBackend(cfg, transport=lambda *a: self.fail("engine called")))
        self.assertFalse((self.base / "job").exists())

    def pending(self, stage="manifest-durable"):
        class Cut(BaseException):
            pass
        def checkpoint(current):
            if current == stage:
                raise Cut()
        with patch.object(self.store, "_checkpoint", checkpoint), self.assertRaises(Cut):
            self.imported()
        return self.store.inventory()["pending_review"][0]

    def test_complete_pending_requires_exact_reviewed_reference(self):
        name = self.pending(); before = self.store.inspect_pending(name)
        self.assertTrue(before["publishable"])
        ref = before["artifact"]["reference"]
        with self.assertRaisesRegex(MediaError, "ARTIFACT_REFERENCE_MISMATCH"):
            self.store.publish_pending(name, dict(ref, sha256="0" * 64))
        self.assertEqual(self.store.inspect_pending(name), before)
        result = self.store.publish_pending(name, ref)
        self.assertTrue(result["recovered"]); self.assertFalse(result["semantic_content_verified"])
        self.assertEqual(self.store.read(ref)[0], PNG)
        self.assertEqual(self.store.inventory()["pending_review"], [])
        with self.assertRaisesRegex(MediaError, "ARTIFACT_RECOVERY_SCOPE"):
            self.store.publish_pending(name, ref)

    def test_partial_pending_is_never_published_or_deleted(self):
        name = self.pending("payload-durable")
        result = self.store.inspect_pending(name)
        self.assertFalse(result["publishable"])
        ref = {"schema": "media-artifact-ref/1", "store_id": self.store.store_id,
               "artifact_id": "ma-" + "0" * 32, "sha256": hashlib.sha256(PNG).hexdigest()}
        with self.assertRaisesRegex(MediaError, "ARTIFACT_INCOMPLETE"):
            self.store.publish_pending(name, ref)
        self.assertEqual((self.root / name / "payload").read_bytes(), PNG)
        self.assertEqual(self.store.inventory()["artifacts"], [])

    def test_corruption_after_pending_review_is_refused(self):
        name = self.pending(); ref = self.store.inspect_pending(name)["artifact"]["reference"]
        (self.root / name / "payload").write_bytes(PNG[:-1] + b"X")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_CONTENT_MISMATCH"):
            self.store.publish_pending(name, ref)
        self.assertTrue((self.root / name).exists())

    def test_pending_publication_respects_count_quota_and_scope(self):
        manifest = self.imported(); name = self.pending()
        ref = self.store.inspect_pending(name)["artifact"]["reference"]
        marker = dict(self.marker, max_artifacts=1)
        (self.root / "store.json").write_text(json.dumps(marker))
        store = ArtifactStore(self.root)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_QUOTA_EXCEEDED"):
            store.publish_pending(name, ref)
        extra = self.root / ("pending-" + "0" * 32); extra.mkdir(mode=0o700)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_RECOVERY_SCOPE"):
            store.publish_pending(name, ref)
        self.assertEqual(store.read(manifest["reference"])[0], PNG)

    def test_unexpected_bundle_entries_and_pending_paths_refused(self):
        name = self.pending()
        for bad in ("../outside", "ma-" + "0" * 32, "pending-../x"):
            with self.assertRaisesRegex(MediaError, "INVALID_PENDING_ARTIFACT"):
                self.store.inspect_pending(bad)
        (self.root / name / "unexpected").write_text("x")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_UNEXPECTED_ENTRY"):
            self.store.inspect_pending(name)

    def test_process_death_after_recovery_rename_does_not_duplicate(self):
        name = self.pending(); ref = self.store.inspect_pending(name)["artifact"]["reference"]
        code = """
import json,os,sys
from eidolon_core.media_artifacts import ArtifactStore
store=ArtifactStore(sys.argv[1])
store._checkpoint=lambda stage: os._exit(32) if stage=='recovery-renamed' else None
store.publish_pending(sys.argv[2], json.loads(sys.argv[3]))
"""
        result = subprocess.run([sys.executable, "-c", code, str(self.root), name, json.dumps(ref)],
                                env=os.environ.copy(), timeout=10)
        self.assertEqual(result.returncode, 32)
        self.assertEqual(self.store.inventory()["pending_review"], [])
        self.assertEqual(len(self.store.inventory()["artifacts"]), 1)
        self.assertEqual(self.store.read(ref)[0], PNG)

    def test_export_is_complete_private_and_independent_from_store(self):
        ref = self.imported()["reference"]; target = self.base / "result.png"
        result = self.store.export_file(ref, target)
        self.assertTrue(result["exported"]); self.assertFalse(result["semantic_content_verified"])
        self.assertEqual(target.read_bytes(), PNG)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.stat().st_nlink, 1)
        target.write_bytes(b"edited externally")
        self.assertEqual(self.store.read(ref)[0], PNG)
        with self.assertRaises(FileExistsError):
            self.store.export_file(ref, target)
        self.assertEqual(target.read_bytes(), b"edited externally")

    def test_export_rejects_links_internal_store_and_public_parent(self):
        ref = self.imported()["reference"]; target = self.base / "alias"
        target.symlink_to(self.base / "missing")
        with self.assertRaises(FileExistsError):
            self.store.export_file(ref, target)
        self.assertFalse((self.base / "missing").exists())
        for folder in (self.root, self.root / ref["artifact_id"]):
            with self.assertRaisesRegex(MediaError, "EXPORT_INSIDE_STORE"):
                self.store.export_file(ref, folder / "new.png")
        folder = self.base / "public"; folder.mkdir(mode=0o755)
        with self.assertRaisesRegex(MediaError, "ARTIFACT_PERMISSIONS"):
            self.store.export_file(ref, folder / "new.png")

    def test_concurrent_export_destination_is_not_overwritten(self):
        ref = self.imported()["reference"]; target = self.base / "new.png"
        def checkpoint(stage):
            if stage == "export-durable":
                target.write_bytes(b"other writer")
        with patch.object(self.store, "_checkpoint", checkpoint), self.assertRaises(FileExistsError):
            self.store.export_file(ref, target)
        self.assertEqual(target.read_bytes(), b"other writer")
        self.assertEqual(list(self.base.glob(".media-export-*")), [])

    def test_corrupt_artifact_never_creates_export(self):
        ref = self.imported()["reference"]; target = self.base / "new.png"
        (self.root / ref["artifact_id"] / "payload").write_bytes(PNG[:-1] + b"X")
        with self.assertRaisesRegex(MediaError, "ARTIFACT_CONTENT_MISMATCH"):
            self.store.export_file(ref, target)
        self.assertFalse(target.exists())

    def test_process_death_export_is_absent_or_complete_never_partial(self):
        ref = self.imported()["reference"]
        code = """
import json,os,sys
from eidolon_core.media_artifacts import ArtifactStore
store=ArtifactStore(sys.argv[1])
store._checkpoint=lambda stage: os._exit(33) if stage==sys.argv[4] else None
store.export_file(json.loads(sys.argv[2]), sys.argv[3])
"""
        for stage in ("export-durable", "export-published"):
            target = self.base / (stage + ".png")
            result = subprocess.run([sys.executable, "-c", code, str(self.root), json.dumps(ref), str(target), stage],
                                    env=os.environ.copy(), timeout=10)
            self.assertEqual(result.returncode, 33)
            if stage == "export-durable":
                self.assertFalse(target.exists())
            else:
                self.assertEqual(target.read_bytes(), PNG)
                with self.assertRaises(FileExistsError):
                    self.store.export_file(ref, target)
            self.assertEqual(self.store.read(ref)[0], PNG)


if __name__ == "__main__":
    unittest.main()
