# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_query_cleanup.py
# Description : Frontières de nettoyage et absence d'émission des motifs retirés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
import unittest

from eidolon_core.contracts import ContractError
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research import AccessFailure, ResearchCoordinator
from tests.test_research import Provider, Reader, dns, hit


class QueryCleanupTests(unittest.TestCase):
    def test_recognized_personal_patterns_are_removed_in_full(self):
        cases = [
            ("jean@example.invalid", "EMAIL"),
            ("+33 1 23 45 67 89", "PHONE_SHAPE"),
            ("01 23 45 67 89", "PHONE_SHAPE"),
            ("0123456789", "PHONE_SHAPE"),
            ("FR76 0000 0000 0000 0000 0000 000", "IBAN_SHAPE"),
            ("https://user:SYNTH@host.example/private/SYNTH?key=SYNTH#SYNTH", "URL"),
            (r"C:\Users\alice\Documents\private.xlsx", "LOCAL_PATH"),
            (r'"C:\Users\alice\My Documents\private.xlsx"', "LOCAL_PATH"),
            ("/home/alice/notes.txt", "LOCAL_PATH"),
            (r"\\nas-fictif\partage\notes.txt", "LOCAL_PATH"),
            ("~/secret.txt", "LOCAL_PATH"),
            ("192.0.2.10", "NETWORK_ADDRESS"),
            ("2001:db8::a", "NETWORK_ADDRESS"),
            ("::1", "NETWORK_ADDRESS"),
        ]
        for private, kind in cases:
            with self.subTest(private=private):
                result = clean_query("diagnostic " + private + " procédure")
                self.assertEqual(result.text, "diagnostic procédure")
                self.assertEqual(dict(result.removed), {kind: 1})

    def test_g050_common_endpoints_paths_and_numbers_are_removed(self):
        cases = ["198.51.100.7:25565", "198.051.100.007", "[2001:db8::7]:25565",
                 "fr76 0000 0000 0000 0000 0000 000", "FR76-0000-0000-0000-0000-0000-000",
                 "0033 6 12 34 56 78", "+33 (0)6 12 34 56 78",
                 "www.example.invalid/reset?token=SYNTH", "example.invalid/reset?token=SYNTH",
                 "smb://server.example/private", "sftp://server.example/private",
                 "/opt/private/token", "/srv/private/token", "./secrets/token.txt",
                 r"%USERPROFILE%\private\token", "'/home/private folder/token'"]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(clean_query("notice " + value + " erreur").text, "notice erreur")
        self.assertEqual(clean_query("ip:198.51.100.7.").text, "ip: .")
        for public in ("node.js/express", "README.md#install", "./configure", "fr12 pour cela vous"):
            self.assertEqual(clean_query(public).text, public)

    def test_reports_do_not_export_raw_query_fingerprints(self):
        raw = "joindre 01 23 45 67 89"
        report = ResearchCoordinator([Provider("p", [])], Reader(), resolver=dns).run(raw)
        from eidolon_core.contracts import digest
        serialized = json.dumps(report)
        for fingerprint in (digest(raw), hashlib.sha256(raw.encode()).hexdigest()):
            self.assertNotIn(fingerprint, serialized)
        self.assertEqual(report["query_sha256"], clean_query(raw).cleaned_sha256)
        self.assertEqual(report["query_hash_scope"], "cleaned_utf8")

    def test_unicode_normalization_does_not_leave_email_fragments(self):
        for email in ("jean＠example.invalid", "jean\u200b@example.invalid", "jean@exam\u2060ple.invalid"):
            result = clean_query(email + " contact")
            self.assertEqual(result.text, "contact")
            self.assertTrue(result.normalized)
            self.assertEqual(dict(result.removed), {"EMAIL": 1})

    def test_receipt_does_not_contain_removed_values_or_cleaned_text(self):
        raw = "joindre jean@example.invalid au 01 23 45 67 89 SUJET_PRIVE"
        result = clean_query(raw)
        receipt = result.receipt()
        serialized = json.dumps(receipt)
        for value in ("jean", "example", "01 23", "SUJET_PRIVE"):
            self.assertNotIn(value, serialized)
        self.assertNotIn("original_sha256", receipt)
        self.assertNotIn(hashlib.sha256(raw.encode()).hexdigest(), serialized)
        self.assertEqual(receipt["cleaned_sha256"], hashlib.sha256(result.text.encode()).hexdigest())
        self.assertFalse(receipt["anonymity_guaranteed"])
        self.assertFalse(receipt["authorizes_transmission"])

    def test_ordinary_text_and_explicit_detection_limits(self):
        for value in ("python 3.11.15 release notes", "norme ISO 8601 2026-10-06",
                      "syntaxe @decorator python", "météo Lyon demain",
                      "Camille Fictif-Exemple adresse domicile",
                      "clé licence AAAA-BBBB-CCCC-DDDD activation",
                      '"Le client Martin refuse la clause" signification',
                      "jean point dupont arobase example point invalid"):
            self.assertEqual(clean_query(value).text, value)
        # Public product identifiers and URLs may be removed too: no semantic oracle.
        self.assertEqual(clean_query("référence 0612345678 notice").text, "référence notice")
        self.assertEqual(clean_query("https://docs.example/guide erreur").text, "erreur")

    def test_invalid_and_expanded_inputs_are_refused_without_echo(self):
        for value in (None, True, b"text", "", " ", "x"*1001, "SYNTH\ud800", "SYNTH\x00"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ContractError) as caught:
                    clean_query(value)
                self.assertNotIn("SYNTH", str(caught.exception))
        with self.assertRaisesRegex(ContractError, "NORMALIZED_QUERY_TOO_LARGE"):
            clean_query("\ufdfa" * 100)

    def test_empty_cleaned_query_has_no_provider_reader_or_dns_calls(self):
        provider, reader = Provider("p", [hit()]), Reader()
        def forbidden_dns(*args):
            self.fail("DNS called for an empty cleaned query")
        report = ResearchCoordinator([provider], reader, resolver=forbidden_dns).run("jean@example.invalid")
        self.assertEqual(report["status"], "QUERY_EMPTY_AFTER_CLEANUP")
        self.assertEqual(report["discovery_status"], "NOT_REQUESTED")
        self.assertEqual((provider.calls, len(reader.calls)), (0, 0))
        self.assertEqual(report["providers"], [])

    def test_every_fallback_receives_only_the_same_cleaned_query(self):
        sent = []
        class RecordingProvider(Provider):
            def search(self, query, limit):
                sent.append((self.provider_id, query))
                return super().search(query, limit)
        providers = [RecordingProvider("first", AccessFailure("UNAVAILABLE")),
                     RecordingProvider("second", [hit()])]
        raw = "joindre jean@example.invalid au 01 23 45 67 89"
        report = ResearchCoordinator(providers, Reader(), resolver=dns).run(raw)
        self.assertEqual(sent, [("first", "joindre au"), ("second", "joindre au")])
        self.assertEqual(report["status"], "READ_TARGET_MET")
        self.assertNotIn("jean", json.dumps(report))
        self.assertEqual(report["query_cleanup"]["removed"], {"EMAIL": 1, "PHONE_SHAPE": 1})

    def test_overlap_counts_containers_once_and_cleanup_is_idempotent(self):
        raw = 'https://jean@example.invalid/path?phone=0123456789 /home/jean@example.invalid/notes diagnostic'
        first = clean_query(raw)
        self.assertEqual(first.text, "diagnostic")
        self.assertEqual(dict(first.removed), {"URL": 1, "LOCAL_PATH": 1})
        second = clean_query(first.text)
        self.assertEqual(second.text, first.text)
        self.assertEqual(second.removed, ())


if __name__ == "__main__":
    unittest.main()
