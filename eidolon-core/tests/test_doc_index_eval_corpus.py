# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_doc_index_eval_corpus.py
# Description : Corpus E2 de 40 questions figé avant tout essai réel (G196) : empreinte, structure, abstentions
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

CORPUS = Path(__file__).resolve().parents[1] / "docs" / "doc-index-eval" / "corpus-v1.json"
FROZEN_SHA256 = "e4a74463d5eb145e96d378facbe09be1e212db8185f0cca0f3d6fd5fcbadad4a"


class FrozenCorpus(unittest.TestCase):
    def setUp(self):
        self.raw = CORPUS.read_bytes()
        self.corpus = json.loads(self.raw)

    def test_corpus_is_frozen(self):
        """Any change is a new version with a logged reason, never an edit after seeing results."""
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), FROZEN_SHA256)

    def test_shape_and_balance(self):
        questions = self.corpus["questions"]
        self.assertEqual(len(questions), 40)
        self.assertEqual(len({q["id"] for q in questions}), 40)
        self.assertEqual(Counter(q["kind"] for q in questions),
                         {"factual": 25, "procedure": 5, "negation": 5, "abstention": 5})
        self.assertEqual(set(q["theme"] for q in questions), {"wikipedia", "debian", "python", "proxmox"})

    def test_abstentions_expect_nothing_and_answers_are_checkable(self):
        for q in self.corpus["questions"]:
            if q["kind"] == "abstention":
                self.assertEqual((q["expected_source"], q["answer_must_contain"], q["verification"]),
                                 (None, [], "abstain_expected"), q["id"])
            else:
                self.assertIn(q["expected_source"]["corpus"], self.corpus["licences"], q["id"])
                self.assertTrue(q["answer_must_contain"], q["id"])
                self.assertEqual(q["verification"], "to_verify_on_frozen_snapshot", q["id"])


if __name__ == "__main__":
    unittest.main()
