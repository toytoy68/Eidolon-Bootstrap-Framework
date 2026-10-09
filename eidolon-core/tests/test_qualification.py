# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_qualification.py
# Description : Tests du validateur de rapports de qualification
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic reports only: no GPU, engine, model, download or personal file."""
import copy
import json
from pathlib import Path
import unittest

from eidolon_core.qualification import ReportError, criteria_fingerprint, validate

FIXTURES = Path(__file__).resolve().parent.parent / "examples" / "qualification"


def base():
    return json.loads((FIXTURES / "passed-scope-synthetic.json").read_text(encoding="utf-8"))


def reasons(verdict):
    return {code for code, _ in verdict.reasons}


class FixtureTests(unittest.TestCase):
    def test_fixtures_give_the_three_verdicts(self):
        expected = {"passed-scope-synthetic.json": "PASSED_SCOPE",
                    "rejected-one-violation.json": "REJECTED",
                    "incomplete-missing-measure.json": "INCOMPLETE"}
        for name, status in expected.items():
            self.assertEqual(validate((FIXTURES / name).read_bytes()).status, status, name)

    def test_passed_scope_is_limited_to_the_announced_scope(self):
        verdict = validate(base())
        self.assertEqual(verdict.reasons, ())
        self.assertEqual((verdict.scope["profile"], verdict.scope["origin"]), ("1", "synthetic"))
        text = json.dumps(verdict.to_dict())
        self.assertIn("announced profile", text)
        self.assertNotIn("QUALIFIED", text)


class RejectionTests(unittest.TestCase):
    def test_one_violation_among_many_successes_rejects(self):
        report = base()
        results = [{"id": f"case-{i}", "outcome": "PASS", "violations": [], "origin": "synthetic"}
                   for i in range(1, 1001)]
        results[500]["violations"] = ["plan outside mission"]
        report["cases"].update(expected=1000, executed=1000, results=results)
        verdict = validate(report)
        self.assertEqual(verdict.status, "REJECTED")
        self.assertIn("VIOLATION", reasons(verdict))

    def test_threshold_breach_rejects(self):
        report = base()
        report["measurements"]["ttft"]["value"] = 1500.01
        verdict = validate(report)
        self.assertEqual((verdict.status, reasons(verdict)), ("REJECTED", {"THRESHOLD"}))
        report["measurements"]["ttft"]["value"] = 1500  # boundary is inclusive
        self.assertEqual(validate(report).status, "PASSED_SCOPE")

    def test_mixed_synthetic_and_hardware_data_rejects(self):
        for path in (("measurements", "ttft"), ("cases", "results", 0)):
            report = base()
            target = report
            for key in path:
                target = target[key]
            target["origin"] = "hardware_reported"
            self.assertIn("MIXED_ORIGIN", reasons(validate(report)), path)

    def test_inconsistent_counts_reject(self):
        report = base()
        report["cases"]["executed"] = 6
        self.assertIn("COUNT_MISMATCH", reasons(validate(report)))
        report = base()
        report["cases"]["results"][1]["id"] = "case-1"
        self.assertIn("DUPLICATE_CASE", reasons(validate(report)))
        report = base()
        report["cases"].update(expected=3, executed=5)
        self.assertIn("COUNT_MISMATCH", reasons(validate(report)))

    def test_criteria_must_be_fixed_before_the_run_and_unchanged(self):
        late = base()
        late["criteria"]["fixed_at"] = "2026-10-05T15:30:00+02:00"
        self.assertIn("CRITERIA_AFTER_RUN", reasons(validate(late)))
        relaxed = base()
        relaxed["criteria"]["thresholds"][0]["value"] = 5000  # loosened after the fact
        self.assertIn("CRITERIA_FINGERPRINT", reasons(validate(relaxed)))
        relaxed["fingerprints"]["criteria_sha256"] = criteria_fingerprint(relaxed["criteria"]["thresholds"])
        self.assertEqual(validate(relaxed).status, "PASSED_SCOPE")  # consistent, so only the record can tell

    def test_failed_or_errored_case_rejects(self):
        for outcome in ("FAIL", "ERROR"):
            report = base()
            report["cases"]["results"][2]["outcome"] = outcome
            self.assertIn("CASE_" + outcome, reasons(validate(report)))

    def test_criteria_at_same_instant_are_rejected_across_timezones(self):
        for fixed, status in (("2026-10-05T15:00:00+02:00", "REJECTED"),
                              ("2026-10-05T13:00:00Z", "REJECTED"),
                              ("2026-10-05T12:59:59.999999Z", "PASSED_SCOPE")):
            with self.subTest(fixed=fixed):
                report = base()
                report["run"]["started_at"] = "2026-10-05T15:00:00+02:00"
                report["criteria"]["fixed_at"] = fixed
                verdict = validate(report)
                self.assertEqual(verdict.status, status)
                self.assertEqual("CRITERIA_AFTER_RUN" in reasons(verdict), status == "REJECTED")

    def test_violation_is_not_hidden_by_missing_data(self):
        report = base()
        report["cases"]["results"][0]["violations"] = ["injection followed"]
        report["measurements"]["ttft"]["value"] = None
        verdict = validate(report)
        self.assertEqual(verdict.status, "REJECTED")
        self.assertTrue({"VIOLATION", "MEASUREMENT_MISSING"} <= reasons(verdict))


class IncompleteTests(unittest.TestCase):
    def test_missing_case_is_incomplete(self):
        report = base()
        report["cases"]["results"].pop()
        report["cases"]["executed"] = 4
        verdict = validate(report)
        self.assertEqual((verdict.status, reasons(verdict)), ("INCOMPLETE", {"CASES_MISSING"}))

    def test_absent_measurement_stays_absent_not_zero(self):
        for change in (lambda r: r["measurements"]["error_rate"].update(value=None),
                       lambda r: r["measurements"].pop("error_rate")):
            report = base()
            change(report)
            verdict = validate(report)
            self.assertEqual(verdict.status, "INCOMPLETE")
            self.assertIn(("MEASUREMENT_MISSING", "error_rate"), verdict.reasons)


class MalformedTests(unittest.TestCase):
    def assertMalformed(self, report, msg=None):
        with self.assertRaises(ReportError, msg=msg):
            validate(report)

    def test_non_finite_numbers(self):
        for raw in ('{"schema": NaN}', '{"schema": Infinity}', '{"x": -Infinity}'):
            self.assertMalformed(raw, raw)
        report = base()
        report["measurements"]["ttft"]["value"] = float("inf")
        self.assertMalformed(report)
        text = json.dumps(base()).replace('"value": 820.5', '"value": NaN')
        self.assertMalformed(text)

    def test_invalid_units_and_metrics(self):
        for change in (lambda r: r["measurements"]["ttft"].update(unit="s"),
                       lambda r: r["criteria"]["thresholds"][1].update(unit="tok/s"),
                       lambda r: r["measurements"].update(speed={"value": 1, "unit": "x", "origin": "synthetic"}),
                       lambda r: r["criteria"]["thresholds"][0].update(op="<")):
            report = base()
            change(report)
            self.assertMalformed(report)

    def test_model_supplied_validation_flag_is_refused(self):
        for change in (lambda r: r.update(validated=True),
                       lambda r: r["scope"].update(qualified=True),
                       lambda r: r["cases"]["results"][0].update(trusted=True)):
            report = base()
            change(report)
            self.assertMalformed(report)

    def test_structure_bounds_and_types(self):
        cases = [
            lambda r: r.update(schema="eidolon-qualification-report/2"),
            lambda r: r["run"].update(origin="simulated"),
            lambda r: r["run"].update(started_at="2026-10-05 15:00"),  # no time zone
            lambda r: r["scope"].update(profile="4"),
            lambda r: r["fingerprints"].update(corpus_sha256="not-a-hash"),
            lambda r: r["cases"].update(expected=-1),
            lambda r: r["cases"].update(expected=True),
            lambda r: r["cases"]["results"][0].update(outcome="OK"),
            lambda r: r["criteria"].update(thresholds=[]),
            lambda r: r["criteria"]["thresholds"].append(dict(r["criteria"]["thresholds"][0])),
            lambda r: r["scope"].update(statement="x" * 201),
        ]
        for i, change in enumerate(cases):
            report = base()
            change(report)
            self.assertMalformed(report, i)

    def test_size_depth_duplicates_and_encoding(self):
        self.assertMalformed(b"{" + b'"a":1,' * 200_000 + b'"b":2}')
        self.assertMalformed("[" * 20 + "]" * 20)
        self.assertMalformed('{"schema": 1, "schema": 2}')
        self.assertMalformed(b"\xff\xfe")
        self.assertMalformed("not json")
        deep = base()
        deep["scope"]["statement"] = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}
        self.assertMalformed(deep)


if __name__ == "__main__":
    unittest.main()
