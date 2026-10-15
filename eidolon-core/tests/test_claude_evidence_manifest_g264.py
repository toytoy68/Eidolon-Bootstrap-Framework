# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_evidence_manifest_g264.py
# Description : Validateur du manifeste de preuves : SHA complets, verdicts, contradictions, jamais d'autorisation (G264-5)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic manifests only; the validator collects nothing from the host."""
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "claude_evidence_manifest.py"
SPEC = importlib.util.spec_from_file_location("claude_evidence_manifest", TOOL)
em = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(em)

NOW = datetime.fromisoformat("2026-10-16T12:00:00+02:00")


def entry(step, verdict="PASS", **over):
    value = {"step": step, "environment": {"machine": "VM110", "os": "Debian 13", "python": "3.13.5",
                                           "account": "eidolon-memory"},
             "command": f"commande de l'étape {step}", "result": {"verdict": verdict, "observed": "sortie notée"},
             "limits": "aucune VM PC pour cette étape", "date": "2026-10-16T09:00:00+02:00",
             "evidence": [{"kind": "log", "ref": f"journal-{step}.txt", "sha256": "a" * 64}]}
    value.update(over)
    return value


def manifest(entries=None, **over):
    value = {"schema": em.SCHEMA, "sha": {"core": "1" * 40, "memory": "2" * 40},
             "entries": [entry(s) for s in range(10)] if entries is None else entries}
    value.update(over)
    return value


def check(m):
    return em.validate(m, now=NOW)


def test_a_complete_manifest_is_complete_but_never_an_authorization():
    report = check(manifest())
    assert report == {"verdict": "COMPLETE", "errors": [], "gaps": [], "authorizes_deployment": False}


@pytest.mark.parametrize("change, gap", [
    (lambda m: m["entries"].pop(3), "MISSING:step3"),
    (lambda m: m["entries"][4]["result"].update(verdict="UNKNOWN"), "UNKNOWN:step4"),
    (lambda m: m["entries"][5]["result"].update(verdict="FAIL"), "FAIL:step5"),
    (lambda m: m["entries"][6]["result"].update(verdict="SKIPPED"), "SKIPPED:step6"),
    (lambda m: m["entries"][1].update(differences=[{"test": "t", "class": "C", "reason": "inexpliqué"}]),
     "UNEXPLAINED_DIFFERENCE:step1"),
])
def test_missing_unknown_failed_skipped_or_unexplained_steps_are_incomplete(change, gap):
    m = manifest()
    change(m)
    report = check(m)
    assert report["verdict"] == "INCOMPLETE" and gap in report["gaps"] and report["authorizes_deployment"] is False


def test_classified_differences_a_and_b_keep_the_step_complete():
    m = manifest()
    m["entries"][1]["differences"] = [{"test": "test_x", "class": "A", "reason": "numpy absent"},
                                      {"test": "test_y", "class": "B", "reason": "AF_UNIX interdit, rejoué hors"}]
    assert check(m)["verdict"] == "COMPLETE"


@pytest.mark.parametrize("change, code", [
    (lambda m: m["sha"].update(core="1" * 7), "SHA_NOT_FULL"),
    (lambda m: m["sha"].update(memory="G" * 40), "SHA_NOT_FULL"),
    (lambda m: m.update(schema="other"), "SCHEMA"),
    (lambda m: m.update(extra=1), "UNEXPECTED_OR_MISSING_FIELD"),
    (lambda m: m["entries"][0]["environment"].pop("account"), "ENVIRONMENT"),
    (lambda m: m["entries"][0]["environment"].update(account=" "), "ENVIRONMENT"),
    (lambda m: m["entries"][0].update(command=""), "COMMAND_OR_LIMITS"),
    (lambda m: m["entries"][0].update(limits=None), "COMMAND_OR_LIMITS"),
    (lambda m: m["entries"][0].update(date="2026-10-16T09:00:00"), "DATE"),            # no time zone
    (lambda m: m["entries"][0].update(date="2026-10-17T09:00:00+02:00"), "DATE"),      # in the future
    (lambda m: m["entries"][0]["result"].update(verdict="OK"), "VERDICT"),
    (lambda m: m["entries"][0]["result"].update(observed=""), "RESULT"),
    (lambda m: m["entries"][0].update(evidence=[]), "PASS_WITHOUT_EVIDENCE"),
    (lambda m: m["entries"][0].update(evidence=[{"kind": "url", "ref": "x"}]), "EVIDENCE"),
    (lambda m: m["entries"][0].update(evidence=[{"kind": "log", "ref": "x", "sha256": "z"}]), "EVIDENCE"),
    (lambda m: m["entries"][0].update(step=10), "STEP"),
    (lambda m: m["entries"][0].update(step=True), "STEP"),
    (lambda m: m["entries"][1].update(differences=[{"test": "t", "class": "D", "reason": "r"}]), "DIFFERENCE"),
    (lambda m: m["entries"][1].update(differences=[{"test": "t", "class": "A", "reason": ""}]), "DIFFERENCE"),
    (lambda m: m["entries"].append(entry(2, "FAIL")), "CONTRADICTION"),
])
def test_invalid_manifests_are_refused_with_a_code(change, code):
    m = manifest()
    change(m)
    report = check(m)
    assert report["verdict"] == "INVALID" and any(e.startswith(code) for e in report["errors"]), report
    assert report["authorizes_deployment"] is False


def test_a_repeated_identical_observation_is_not_a_contradiction():
    m = manifest()
    m["entries"].append(entry(2))
    assert check(m)["verdict"] == "COMPLETE"


def cli(tmp_path, content, now="2026-10-16T12:00:00+02:00"):
    path = tmp_path / "manifest.json"
    path.write_bytes(content if isinstance(content, bytes) else json.dumps(content).encode())
    r = subprocess.run([sys.executable, str(TOOL), str(path), "--now", now], capture_output=True, text=True,
                       timeout=30)
    return r.returncode, json.loads(r.stdout) if r.stdout else r.stderr


def test_command_exit_codes_and_strict_json(tmp_path):
    assert cli(tmp_path, manifest())[0] == 0
    m = manifest()
    m["entries"].pop()
    assert cli(tmp_path, m)[0] == 1
    assert cli(tmp_path, manifest(sha={"core": "1" * 7, "memory": "2" * 40}))[0] == 2
    raw = json.dumps(manifest())
    dup = raw.replace('"schema"', '"schema": "x", "schema"', 1).encode()
    code, report = cli(tmp_path, dup)
    assert (code, report["errors"]) == (2, ["JSON"])
    assert cli(tmp_path, b'{"schema": NaN}')[0] == 2
    code, err = cli(tmp_path, manifest(), now="2026-10-16T12:00:00")
    assert code == 2 and "time zone" in err


def test_the_validator_has_no_host_collection_surface():
    source = TOOL.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "socket", "os.environ", "platform", "getpass", "shutil"):
        assert forbidden not in source
