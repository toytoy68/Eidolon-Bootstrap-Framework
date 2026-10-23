# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_wake_eval_g296.py
# Description : Notation des mots d'appel G296 (rappel, fausses activations, latence)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "evaluation"))
from wake_eval_g296 import score  # noqa: E402


def ann(utterances, duration=3600, playback=()):
    return {"schema": "eidolon-wake-annotation/1", "duration_s": duration,
            "utterances": [{"start": s, "end": e, "phrase": p} for s, e, p in utterances],
            "playback": [list(x) for x in playback]}


def det(events):
    return {"schema": "eidolon-wake-detections/1", "detector": "test",
            "events": [{"at": a, "phrase": p, "score": .9} for a, p in events]}


def test_accepted_detector():
    utt = [(10 * i, 10 * i + .6, "eidolon") for i in range(1, 21)]
    r = score(ann(utt), det([(e + .2, "eidolon") for _, e, _ in utt]))
    m = r["phrases"]["eidolon"]
    assert (m["recall"], m["false_activations"], m["latency_p95_ms"]) == (1.0, 0, 200.0)
    assert r["verdict"] == {"eidolon": "ACCEPTED", "dis-moi": "NOT_MEASURED"}


def test_g282_like_latency_is_rejected():
    """Whisper on the VM after a 1.5 s pause: about 5 s after the word (G282 recipe)."""
    utt = [(10 * i, 10 * i + .6, "eidolon") for i in range(1, 21)]
    r = score(ann(utt), det([(e + 4.9, "eidolon") for _, e, _ in utt]), window_s=6)
    assert r["phrases"]["eidolon"]["latency_median_ms"] == 4900.0 and r["verdict"]["eidolon"] == "REJECTED"


def test_false_activations_are_counted_and_echo_separated():
    utt = [(100, 100.6, "dis-moi")]
    events = [(101, "dis-moi"), (500, "dis-moi"), (1000, "dis-moi"), (2000.5, "dis-moi")]
    r = score(ann(utt, playback=[(2000, 2010)]), det(events))
    m = r["phrases"]["dis-moi"]
    assert (m["detected"], m["false_activations"], m["false_during_playback"], m["false_per_hour"]) == (1, 3, 1, 3.0)
    assert r["verdict"]["dis-moi"] == "REJECTED"


def test_one_detection_per_utterance_and_phrase_must_match():
    utt = [(10, 10.5, "eidolon")]
    r = score(ann(utt), det([(10.6, "eidolon"), (10.7, "eidolon"), (10.6, "dis-moi")]))
    assert r["phrases"]["eidolon"]["detected"] == 1 and r["phrases"]["eidolon"]["false_activations"] == 1
    assert r["phrases"]["dis-moi"]["false_activations"] == 1


def test_late_detection_outside_window_is_a_miss_and_a_false_activation():
    r = score(ann([(10, 10.5, "eidolon")]), det([(13, "eidolon")]))
    assert r["phrases"]["eidolon"]["recall"] == 0.0 and r["phrases"]["eidolon"]["false_activations"] == 1


@pytest.mark.parametrize("bad", ["schema", "phrase", "order", "nan", "beyond"])
def test_invalid_inputs_refused(bad):
    a, d = ann([(10, 10.5, "eidolon")]), det([(10.6, "eidolon")])
    if bad == "schema": a["schema"] = "x"
    if bad == "phrase": d["events"][0]["phrase"] = "hey jarvis"
    if bad == "order": a["utterances"][0]["end"] = 9
    if bad == "nan": d["events"][0]["at"] = float("nan")
    if bad == "beyond": d["events"][0]["at"] = 99999
    with pytest.raises(ValueError):
        score(a, d)
