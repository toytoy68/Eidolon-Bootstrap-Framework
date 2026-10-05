"""Opt-in integration: actual Memory Engine code, synthetic temporary corpus."""
from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import snapshot, validate_context
from eidolon_core.memory import DEMO_REQUEST, DEMO_TEXT, EngineMemory
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from examples.memory_engine_demo import STAMP, seed


def hashes(root):
    # Engine may initialize technical lock files. All other bytes must be stable.
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and p.name != ".write.lock"}


@unittest.skipUnless(os.environ.get("EIDOLON_MEMORY_INTEGRATION") == "1",
                     "opt-in real Memory Engine dependency; see README")
class MemoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ec-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "engine"
        self.backend, self.writer, self.memory = seed(self.root)
        self.adapter = EngineMemory(str(self.root))

    def test_exact_bundle_parity_and_all_canonical_bytes_unchanged(self):
        from core.retrieval.contextual import ContextualRecall
        before = hashes(self.root)
        expected = snapshot(asdict(ContextualRecall(self.backend).recall(
            DEMO_REQUEST, mode="operational", max_items=5, max_chars=4000, max_item_chars=1000)))
        actual = validate_context(self.adapter.recall(DEMO_REQUEST))
        self.assertEqual(actual, expected)
        self.assertEqual(hashes(self.root), before)
        item = actual["items"][0]
        self.assertEqual(item["provenance"], self.memory.provenance)
        self.assertEqual(item["verification"], self.memory.verification)
        self.assertEqual(item["temporal"], self.memory.temporal)
        self.assertTrue(item["needs_review"])
        self.assertEqual(item["epistemic_status"], "UNVERIFIED")

    def test_complete_mission_with_actual_api_in_spawned_reader(self):
        before = hashes(self.root)
        runtime = Runtime(Store(Path(self.temp.name) / "missions"), memory=self.adapter)
        m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        self.assertEqual(m["status"], "SUCCEEDED")
        self.assertEqual(m["calls"][0]["output"]["characters"], len(DEMO_TEXT))
        self.assertEqual(m["result"]["sources"]["items"][0]["revision"], 1)
        self.assertEqual(hashes(self.root), before)

    def test_unfinished_coordinated_write_blocks_recall_and_core(self):
        with patch.object(self.writer.events, "save", side_effect=RuntimeError("synthetic crash")):
            with self.assertRaises(RuntimeError):
                self.writer.update(replace(self.memory, content="changed synthetic content"),
                                   previous_revision=1, operation_id="fixture-update",
                                   event_id="fixture-event-2", actor="fixture", timestamp=STAMP)
        before = hashes(self.root)
        runtime = Runtime(Store(Path(self.temp.name) / "missions"), memory=self.adapter)
        m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        self.assertEqual(m["status"], "BLOCKED")
        self.assertEqual(m["error"]["code"], "MEMORY_UNAVAILABLE")
        self.assertIsNone(m["plan"])
        self.assertEqual(hashes(self.root), before)

    def test_missing_root_not_created_by_reader(self):
        root = Path(self.temp.name) / "missing"
        with self.assertRaises(FileNotFoundError):
            EngineMemory(str(root)).recall("demo")
        self.assertFalse(root.exists())

    def test_refuted_source_filtered_by_real_engine_not_promoted(self):
        self.writer.update(replace(self.memory, metadata={**self.memory.metadata, "epistemic_status": "REFUTED"}),
                           previous_revision=1, operation_id="fixture-refute", event_id="fixture-refute-event",
                           actor="fixture", timestamp=STAMP)
        before = hashes(self.root)
        result = self.adapter.recall(DEMO_REQUEST)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["excluded_counts"], {"REFUTED": 1})
        self.assertEqual(hashes(self.root), before)

    def test_archive_message_references_and_caveats_preserved(self):
        from core.sources.chatgpt_import import plan_conversation
        conversation = {"id": "synthetic-conversation", "title": "Synthetic", "create_time": 1700000000,
                        "mapping": {"node-1": {"parent": None, "message": {
                            "id": "message-1", "author": {"role": "user"}, "create_time": 1700000000,
                            "content": {"content_type": "text", "parts": ["Ne pas acheter la V100 cette semaine."]}}}}}
        memory, at = plan_conversation(conversation, "0" * 64)
        self.writer.create(memory, operation_id="synthetic-archive", event_id="synthetic-archive-event",
                           actor="fixture", timestamp=at)
        before = hashes(self.root)
        result = self.adapter.recall("V100")
        item = next(i for i in result["items"] if i["information_id"] == memory.information_id)
        ref = item["excerpt_reference"]
        self.assertEqual(ref["conversation_id"], "synthetic-conversation")
        self.assertEqual(ref["message_id"], "message-1")
        self.assertEqual(ref["role"], "user")
        original = conversation["mapping"]["node-1"]["message"]["content"]["parts"][0]
        self.assertEqual(item["content"], original[ref["start"]:ref["end"]])
        self.assertEqual(item["epistemic_status"], "UNVERIFIED")
        self.assertTrue(item["needs_review"])
        self.assertEqual(hashes(self.root), before)
        # This validates reference fidelity only, NOT the known A5-02 semantic defect.
