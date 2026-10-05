# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_qualification_boundaries.py
# Description : Frontières d'entrée et absence de preuve de qualification
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import unittest

from eidolon_core.qualification import ReportError, criteria_fingerprint, validate
from tests.test_qualification import base, reasons


class QualificationBoundaryTests(unittest.TestCase):
    def test_unhashable_metric_gives_contract_error(self):
        for metric in ([], {}, None, 1):
            r = base()
            r["criteria"]["thresholds"][0]["metric"] = metric
            with self.subTest(metric=metric), self.assertRaises(ReportError):
                validate(r)

    def test_exponent_overflow_large_integer_and_surrogates_are_report_errors(self):
        for value in (10**400, "\ud800"):
            r = base()
            if isinstance(value, int):
                r["measurements"]["ttft"]["value"] = value
            else:
                r["scope"]["engine"] = value
            for raw in (r, json.dumps(r)):
                with self.subTest(type=type(raw).__name__, value_type=type(value).__name__), self.assertRaises(ReportError):
                    validate(raw)
        with self.assertRaises(ReportError):
            validate('{"x":1e999}')
        with self.assertRaises(ReportError):
            criteria_fingerprint([{"value": float("nan")}])

    def test_empty_corpus_is_incomplete_and_does_not_hide_rejection(self):
        r = base()
        r["cases"].update(expected=0, executed=0, results=[])
        v = validate(r)
        self.assertEqual(v.status, "INCOMPLETE")
        self.assertIn("EMPTY_CORPUS", reasons(v))
        r["measurements"]["ttft"]["value"] = 9000
        v = validate(r)
        self.assertEqual(v.status, "REJECTED")
        self.assertTrue({"EMPTY_CORPUS", "THRESHOLD"} <= reasons(v))

    def test_physical_metric_domains_and_improvement(self):
        for metric, value in (("ttft", -1), ("error_rate", 1.1), ("error_rate", -0.1),
                              ("latency_degradation", -100.1)):
            r = base()
            from eidolon_core.qualification import METRIC_UNITS
            r["measurements"][metric] = {"unit": METRIC_UNITS[metric], "origin": "synthetic", "value": value}
            with self.subTest(metric=metric, value=value), self.assertRaises(ReportError):
                validate(r)
        r = base()
        r["measurements"]["latency_degradation"] = {"unit": "percent", "origin": "synthetic", "value": -25}
        self.assertEqual(validate(r).status, "PASSED_SCOPE")
        r["criteria"]["thresholds"][0]["value"] = -1
        with self.assertRaises(ReportError):
            validate(r)
