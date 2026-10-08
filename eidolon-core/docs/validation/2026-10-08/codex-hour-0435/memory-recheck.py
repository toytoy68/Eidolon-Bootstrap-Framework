# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : memory-recheck.py
# Description : Contre-vérification A5 via le lecteur Core sur corpus jetable
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Memory Engine must be on PYTHONPATH. No changes to either active corpus or engine code."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from core.sources.chatgpt_import import import_exports
from eidolon_core.contracts import validate_context
from eidolon_core.memory import EngineMemory


def conversation(identity, text):
    return {"id": identity, "title": "Synthetic integration", "create_time": 1700000000,
            "current_node": "node-1", "mapping": {"node-1": {"parent": None, "message": {
                "id": "message-1", "author": {"role": "user"}, "create_time": 1700000000,
                "content": {"content_type": "text", "parts": [text]}}}}}


def export(path, values, **options):
    path.write_text(json.dumps(values, ensure_ascii=False, **options), encoding="utf-8")
    return path


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and path.name != ".write.lock"}


def recall(root, query):
    before = hashes(root)
    bundle = validate_context(EngineMemory(str(root)).recall(query))
    assert hashes(root) == before, "Core recall changed canonical bytes"
    assert all(item["epistemic_status"] == "UNVERIFIED" and item["needs_review"] for item in bundle["items"])
    return bundle


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-memory-recheck-") as temporary:
        root = Path(temporary)
        corpus = root / "corpus"
        c1 = conversation("c1", "Eidolon premier échange.")
        c2 = conversation("c2", "Eidolon deuxième échange.")
        c3 = conversation("c3", "Eidolon troisième échange.")
        a = export(root / "first.json", [c1, c2])
        b = export(root / "second.json", [c2, c3], indent=2, sort_keys=True)
        first = import_exports(corpus, [a])
        canonical_before = hashes(corpus / "memory")
        second = import_exports(corpus, [b])
        canonical_after = hashes(corpus / "memory")
        assert all(canonical_after[path] == digest for path, digest in canonical_before.items())
        assert first["new_conversations"] == 2
        assert (second["replayed_conversations"], second["new_conversations"]) == (1, 1)
        before_replay = hashes(corpus)
        replay = import_exports(corpus, [b])
        assert (replay["replayed_conversations"], replay["new_conversations"]) == (2, 0)
        assert hashes(corpus) == before_replay
        items = recall(corpus, "Eidolon")["items"]
        assert len(items) == len({item["information_id"] for item in items}) == 3
        overlap = {"status": "PASS", "first_new": 2, "overlap_replayed": 1, "second_new": 1,
                   "distinct_recalled_items": 3, "canonical_originals_unchanged": True,
                   "repeated_import_unchanged": True, "core_recall_read_only": True}

        malformed_results = []
        before_invalid = hashes(corpus)
        for malformed in ("Bonjour", {"text": "Bonjour"}, None, 42, True):
            bad = conversation("bad", "placeholder")
            bad["mapping"]["node-1"]["message"]["content"]["parts"] = malformed
            invalid = export(root / "invalid.json", [c1, bad])
            try:
                import_exports(corpus, [invalid])
            except ValueError as error:
                assert "parts must be a list" in str(error)
            else:
                raise AssertionError("malformed parts accepted")
            assert hashes(corpus) == before_invalid
            malformed_results.append(type(malformed).__name__)
        assert len(recall(corpus, "Eidolon")["items"]) == 3

        negation = "Ne pas acheter la V100 cette semaine."
        negative_root = root / "negative"
        negative = export(root / "negative.json", [conversation("negative", negation)])
        import_exports(negative_root, [negative])
        item, = recall(negative_root, "acheter V100")["items"]
        reference = item["excerpt_reference"]
        assert item["content"] == negation[reference["start"]:reference["end"]]
        negation_status = {"status": "LIMIT_OBSERVED", "original": negation,
                           "excerpt": item["content"], "start": reference["start"], "end": reference["end"],
                           "exact_source_slice": True, "left_negation_present": "Ne pas" in item["content"],
                           "needs_review": item["needs_review"], "truncated": item["truncated"],
                           "epistemic_status": item["epistemic_status"], "core_recall_read_only": True}
        assert negation_status["left_negation_present"] is False

        continued_root = root / "continued"
        original = conversation("continued", "Eidolon début de conversation.")
        continued = copy.deepcopy(original)
        continued["mapping"]["node-2"] = {"parent": "node-1", "message": {"id": "message-2",
            "author": {"role": "assistant"}, "create_time": 1700000001,
            "content": {"content_type": "text", "parts": ["Suite sans le terme recherché."]}}}
        continued["current_node"] = "node-2"
        import_exports(continued_root, [export(root / "old-version.json", [original])])
        import_exports(continued_root, [export(root / "new-version.json", [continued])])
        versions = recall(continued_root, "Eidolon")["items"]
        refs = {(item["excerpt_reference"]["conversation_id"], item["excerpt_reference"]["message_id"])
                for item in versions}
        assert len(versions) == 2 and len(refs) == 1
        result = {"corpus": "synthetic_temporary_only", "engine_revision": "b33c3a0",
                  "overlapping_identical_conversations": overlap,
                  "malformed_parts": {"status": "PASS", "refused_types": malformed_results,
                                      "existing_corpus_unchanged": True},
                  "negation_context": negation_status,
                  "continued_versions": {"status": "LIMIT_OBSERVED", "recalled_items": 2,
                                         "distinct_message_references": 1, "canonical_versions_preserved": True},
                  "engine_sources_modified": False, "semantic_fact_confirmation": False}
    result["temporary_corpus_removed"] = not root.exists()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
