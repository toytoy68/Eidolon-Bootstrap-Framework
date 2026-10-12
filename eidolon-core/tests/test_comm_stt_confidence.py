# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_stt_confidence.py
# Description : Préserver les paroles réelles face aux filtres STT G164
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import unittest
from eidolon_core.comm_stt import Vocabulary, kept


class ConfidenceGuardTests(unittest.TestCase):
    def test_confident_speech_is_not_a_text_blacklist(self):
        vocab = Vocabulary(['Eidolon', 'toytoy'])
        for text in ["Merci d'avoir regardé cette vidéo !", 'Abonnez-vous à cette lettre.',
                     'Sous-titres activés.', 'Consulte Amara.org.',
                     'Glossaire : Eidolon, toytoy.', 'Eidolon.']:
            with self.subTest(text=text):
                self.assertTrue(kept({'text': text, 'no_speech_prob': 0.01,
                                      'avg_logprob': -0.1}, vocab))

    def test_missing_confidence_does_not_prove_hallucination(self):
        self.assertTrue(kept({'text': "Merci d'avoir regardé cette vidéo !"}))

    def test_uncertain_suspect_text_is_filtered(self):
        self.assertFalse(kept({'text': "Merci d'avoir regardé cette vidéo !",
                               'no_speech_prob': 0.5, 'avg_logprob': -1.4}))

    def test_uncertain_normal_text_is_not_filtered_by_phrase_rule(self):
        self.assertTrue(kept({'text': 'La température est de vingt degrés.',
                              'no_speech_prob': 0.5, 'avg_logprob': -1.4}))

    def test_malformed_vocabulary_is_refused_as_a_contract_error(self):
        from eidolon_core.comm_contract import CommError
        for terms, replacements in [('Eidolon', {}), (None, {}), ([], [['a', 'b']]), ([], 7)]:
            with self.subTest(terms=terms, replacements=replacements):
                with self.assertRaises(CommError) as ctx:
                    Vocabulary(terms, replacements)
                self.assertEqual(ctx.exception.code, 'INVALID_REQUEST')
