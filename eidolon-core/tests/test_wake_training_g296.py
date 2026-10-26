# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_wake_training_g296.py
# Description : Kit d'entraînement « eidolon » : garde VM100, banc, configuration (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1] / "tools" / "wake_training"
sys.path.insert(0, str(KIT))
from guard import decide  # noqa: E402
from bench_model import breakdown, clip_origin, edges, false_per_hour, feature_windows, timeline, timeline_scored  # noqa: E402

NOW = datetime(2026, 10, 23, 22, 0, tzinfo=timezone.utc)


def receipt(last_minutes_ago, observed_s_ago=5):
    return {"schema": "eidolon-activity-receipt/1", "source": "host.eidolon",
            "observed_at": (NOW - timedelta(seconds=observed_s_ago)).isoformat(),
            "last_activity": (NOW - timedelta(minutes=last_minutes_ago)).isoformat()}


def test_guard_runs_only_when_idle_cool_and_known():
    assert decide(now=NOW, activity=receipt(30), temperatures=[55, 60]) == (True, [])
    assert decide(now=NOW, activity=receipt(2), temperatures=[55]) == (False, ["USER_ACTIVE"])
    assert decide(now=NOW, activity=receipt(30), temperatures=[55, 82]) == (False, ["GPU_TOO_HOT"])


@pytest.mark.parametrize("activity", [None, {}, {"schema": "x"}, receipt(30, observed_s_ago=300),
                                      {**receipt(30), "observed_at": "2026-10-23T22:00:00"}])
def test_unknown_or_stale_activity_pauses(activity):
    run, reasons = decide(now=NOW, activity=activity, temperatures=[50])
    assert run is False and reasons[0] in ("ACTIVITY_UNKNOWN", "ACTIVITY_RECEIPT_STALE")


def test_unknown_temperature_pauses():
    assert decide(now=NOW, activity=receipt(30), temperatures=[]) == (False, ["GPU_TEMPERATURE_UNKNOWN"])


def test_edges_debounce_like_a_live_detector():
    scores = [0, .9, .9, .9] + [0] * 30 + [.8]
    assert edges(scores, .5, 0.0) == [0.16, 2.8]


def test_timeline_feeds_wake_eval():
    sys.path.insert(0, str(KIT.parent / "evaluation"))
    from wake_eval_g296 import score
    clips = [("positive", [0] * 16000), ("negative", [0] * 16000), ("positive", [0] * 8000)]
    fired = iter([[0] * 10 + [.9], [0] * 20, [.1] * 20])
    annotation, detections = timeline(clips, lambda s: next(fired), .5)
    r = score(annotation, detections)["phrases"]["eidolon"]
    assert (r["utterances"], r["detected"], r["false_activations"]) == (2, 1, 0)


def test_false_per_hour_on_feature_windows():
    r = false_per_hour([0.0] * 45000 + [1.0], .5)        # 45 001 windows of 80 ms = 1 h
    assert r["false_activations"] == 1 and r["false_per_hour"] == 1.0


def test_training_config_has_only_eidolon():
    text = (KIT / "eidolon-training.yml").read_text().lower()
    assert "model_name: eidolon" in text and "dis-moi" not in text and "dis moi" not in text


def test_runner_shell_is_valid_and_never_targets_production():
    script = KIT / "run_vm100.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    body = script.read_text()
    for forbidden in ("systemctl", "26333", "11500", "/opt/eidolon", "docker rm -f", "rm -rf /", "ollama"):
        assert forbidden not in body.lower(), forbidden
    assert "1cc2c42" in body and "nice -n 19" in body


def test_guard_process_pauses_then_resumes_with_fake_docker(tmp_path):
    """Real guard.py process; docker and nvidia-smi are stand-ins logging their calls."""
    import json, os, time
    log, state, activity = tmp_path / "calls", tmp_path / "running", tmp_path / "activity.json"
    state.write_text("8")                                  # inspect answers "true" 8 times, then stops
    (tmp_path / "docker").write_text(f"""#!/bin/sh
echo "$@" >> {log}
if [ "$1" = inspect ]; then n=$(cat {state}); [ "$n" -le 0 ] && exit 1; echo $((n-1)) > {state}; echo true; fi
""")
    (tmp_path / "nvidia-smi").write_text("#!/bin/sh\necho 55\necho 60\n")
    for f in ("docker", "nvidia-smi"):
        (tmp_path / f).chmod(0o755)
    def write(minutes_ago):
        now = datetime.now(timezone.utc)
        activity.write_text(json.dumps({"schema": "eidolon-activity-receipt/1", "source": "host.eidolon",
            "observed_at": now.isoformat(), "last_activity": (now - timedelta(minutes=minutes_ago)).isoformat()}))
    write(1)                                               # user active: must pause
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}")
    proc = subprocess.Popen([sys.executable, str(KIT / "guard.py"), "--container", "eidolon-wake-train",
                             "--activity", str(activity), "--interval", "0.2"], env=env,
                            stdout=subprocess.PIPE, text=True)
    time.sleep(0.7); write(60)                              # user gone for an hour: must resume
    out, _ = proc.communicate(timeout=20)
    events = [json.loads(line)["guard"] for line in out.splitlines()]
    assert events[0] == "paused" and "resumed" in events and events[-1] == "container_gone"
    calls = log.read_text()
    assert "pause eidolon-wake-train" in calls and "unpause eidolon-wake-train" in calls
    assert "rm" not in calls.split() and "stop" not in calls.split() and "kill" not in calls.split()


def test_feature_windows_match_train_py_and_the_exported_rank():
    """VM100 run of 24/10: validation features are (frames, 96); the model wants (1, 16, 96)."""
    import numpy as np
    frames = np.arange(20 * 96, dtype=np.float32).reshape(20, 96)
    windows = list(feature_windows(frames, 16))
    assert len(windows) == 4                                   # range(frames - 16), as train.py
    assert all(w.shape == (1, 16, 96) and w.dtype == np.float32 for w in windows)
    assert (windows[1][0] == frames[1:17]).all()               # stride 1 = 80 ms
    ready = np.zeros((3, 16, 96), dtype=np.float32)
    assert [w.shape for w in feature_windows(ready, 16)] == [(1, 16, 96)] * 3
    try:
        list(feature_windows(np.zeros(5), 16))
    except ValueError:
        pass
    else:
        raise AssertionError("rank 1 must be refused")


def test_threshold_sweep_reuses_one_scoring():
    scored = [("positive", 16000, [0.0, 0.65, 0.0]), ("negative", 16000, [0.45, 0.0, 0.0])]
    low = timeline_scored(scored, .4)[1]["events"]
    high = timeline_scored(scored, .6)[1]["events"]
    assert len(low) == 2 and len(high) == 1


def test_clip_origin_uses_the_generator_plan_without_copying_it(tmp_path):
    gen = tmp_path / "gen"; (gen / "data" / "voices").mkdir(parents=True)
    (gen / "pipeline.py").write_text(
        "def speaker_pool(counts, split):\n"
        "    return [(v, s) for v, c in enumerate(counts) for s in range(c)]\n"
        "def sample_plan(index, pool, variation_count, phrase_count):\n"
        "    v, s = pool[index % len(pool)]\n"
        "    return v, s, 0, index % phrase_count\n")
    for name, n in (("a", 1), ("b", 2)):
        (gen / "data" / "voices" / f"{name}.onnx.json").write_text(json.dumps({"num_speakers": n}))
    manifest = {"target_phrase": ["Eidolon", "Aïdolon"], "negative_phrases": ["idole"],
                "voices": [{"file": "a.onnx"}, {"file": "b.onnx"}]}
    origin = clip_origin(gen, manifest, gen / "data" / "voices")
    assert origin("positive", 0) == ("Eidolon", "a", 0) and origin("positive", 1) == ("Aïdolon", "b", 0)
    assert origin("negative", 2) == ("idole", "b", 1)


def test_breakdown_counts_misses_and_false_fires():
    b = breakdown([("positive", "Eidolon", "a", 0, [0.9]), ("positive", "Aïdolon", "a", 1, [0.1]),
                   ("negative", "idole", "b", 0, [0.7]), ("negative", "Eden", "b", 0, [0.2])], .5)
    assert b["positive"]["phrase_voice"]["Aïdolon | a"] == {"fired": 0, "total": 1}
    assert b["positive"]["speaker"] == {"a#0": {"fired": 1, "total": 1}, "a#1": {"fired": 0, "total": 1}}
    assert b["positive"]["phrase"] == {"Eidolon": {"fired": 1, "total": 1}, "Aïdolon": {"fired": 0, "total": 1}}
    assert b["negative"]["phrase"]["idole"]["fired"] == 1 and b["negative"]["voice"]["b"] == {"fired": 1, "total": 2}


def test_v2_recipe_targets_only_the_eille_do_lon_spellings():
    """toytoy, 24/10: « Eille-do-lon » (/ɛjdolɔ̃/). v1 spellings read as other words are refused."""
    import yaml
    config = yaml.safe_load((KIT / "eidolon-training.yml").read_text(encoding="utf-8"))
    assert config["model_name"] == "eidolon_v2"
    targets = {t.casefold() for t in config["target_phrase"]}
    assert targets.isdisjoint({"eidolon", "éidolone", "aïdolon", "eydolon"})   # /ɛdolɔ̃/, /eidolɔn/, /aidolɔ̃/
    assert all("dolon" in t.replace("-", "") for t in targets)
    negatives = {n.casefold() for n in config["custom_negative_phrases"]}
    assert {"idole", "et dolent", "et dolores", "eden"} <= negatives and targets.isdisjoint(negatives)


def _bench_dry_run(tmp_path, provenance, half_b=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    calls = tmp_path / "docker.calls"
    (bin_dir / "docker").write_text(f'#!/bin/sh\necho "$@" >> {calls}\n')
    (bin_dir / "docker").chmod(0o755)
    work = tmp_path / "wake"; models = work / "models"; models.mkdir(parents=True)
    for run in ("eidolon", "eidolon_v2"):
        (work / "wakeword-generator" / "output" / run / "positive_test").mkdir(parents=True)
    (models / "eidolon-1.onnx").write_bytes(b"x")
    if half_b:
        features = work / "wakeword-generator" / "data" / "features"; features.mkdir(parents=True)
        (features / "validation_half_b.npy").write_bytes(b"x")
    if provenance is not None:
        (models / "eidolon-1.provenance.json").write_text(json.dumps(provenance))
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "WAKE_WORKDIR": str(work)}
    r = subprocess.run(["bash", str(KIT / "run_vm100.sh"), "bench"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return calls.read_text()


def test_bench_uses_the_test_clips_of_the_model_recipe(tmp_path):
    call = _bench_dry_run(tmp_path, {"run": "eidolon_v2"})
    assert "output/eidolon_v2/positive_test" in call and "eidolon-1.bench-eidolon_v2.json" in call
    assert "--generator /workspace" in call


def test_bench_of_a_v1_model_falls_back_to_v1_clips(tmp_path):
    call = _bench_dry_run(tmp_path, {"model": "eidolon-1.onnx"})          # v1 provenance had no "run"
    assert "output/eidolon/positive_test" in call and "bench-eidolon.json" in call


# ---- C199 : critères écrits avant la v3, diagnostic, négatifs tenus à l'écart --------------
from gate import evaluate_gate, load_gate  # noqa: E402
from split_validation import split  # noqa: E402
from detect_recording import detections  # noqa: E402
from diagnose_clips import table  # noqa: E402

V2_AT_05 = {   # banc v2 exécuté sur VM100 par GPT le 26/10, seuil 0,5 (G296-WAKE-V2-FINAL)
    "recall": 0.859, "latency_p95_ms": 150.0,
    "negative_features": {"false_per_hour": 0.374},
    "breakdown": {
        "positive": {
            "phrase": {k: {"fired": t - m, "total": t} for k, m, t in (
                ("Eïdolon", 29, 285), ("Eille-dolon", 20, 286), ("Eilledolon", 128, 287),
                ("Heïdolon", 34, 287), ("Eïdo-lon", 28, 286), ("Eïdolon !", 24, 285), ("Eïdolon ?", 19, 284))},
            "voice": {"fr_FR-siwis-medium": {"fired": 489, "total": 500},
                      "fr_FR-upmc-medium": {"fired": 753, "total": 1000},
                      "fr_FR-tom-medium": {"fired": 476, "total": 500}}},
        "negative": {"phrase": {"et dolent": {"fired": 1, "total": 88}, "et Dolores": {"fired": 1, "total": 88},
                                "aide au long": {"fired": 1, "total": 88}, "Héléna": {"fired": 1, "total": 84},
                                "idole": {"fired": 0, "total": 1652}}}}}


def test_gate_v3_rejects_v2_for_the_right_reasons():
    gate = load_gate(KIT / "gate-v3.json")
    verdict = evaluate_gate(V2_AT_05, gate)
    assert verdict == {"pass": False, "reasons": [
        "RECALL", "GENERAL_AUDIO_NOT_MEASURED", "SPELLING:Eilledolon",
        "SPELLING:Eïdolon", "SPELLING:Heïdolon",                # 0,898 et 0,882 : sous le plancher 0,90
        "VOICE:fr_FR-upmc-medium"]}
    held_out = dict(V2_AT_05, holdout_features={"false_per_hour": 0.374, "clean": False})
    assert "GENERAL_AUDIO_NOT_HELD_OUT" in evaluate_gate(held_out, gate)["reasons"]
    assert "TRAP_RATE" not in verdict["reasons"]           # 4 / 2 000 pièges déclenchent


def test_gate_accepts_only_when_every_floor_holds():
    gate = load_gate(KIT / "gate-v3.json")
    good = {"recall": 0.96, "latency_p95_ms": 200, "holdout_features": {"false_per_hour": 0.4, "clean": True},
            "breakdown": {"positive": {"phrase": {"a": {"fired": 96, "total": 100}},
                                       "voice": {"v": {"fired": 96, "total": 100}}},
                          "negative": {"phrase": {"idole": {"fired": 1, "total": 100}}}}}
    assert evaluate_gate(good, gate) == {"pass": True, "reasons": []}
    one_trap = json.loads(json.dumps(good)); one_trap["breakdown"]["negative"]["phrase"]["idole"]["fired"] = 4
    assert evaluate_gate(one_trap, gate)["reasons"] == ["TRAP_RATE", "TRAP:idole"]
    weak = json.loads(json.dumps(good)); weak["breakdown"]["positive"]["phrase"]["b"] = {"fired": 80, "total": 100}
    assert evaluate_gate(weak, gate)["reasons"] == ["SPELLING:b"]


def test_gate_file_is_strict(tmp_path):
    bad = json.loads((KIT / "gate-v3.json").read_text()); del bad["synthetic"]["max_trap_fire_rate"]
    (tmp_path / "g.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_gate(tmp_path / "g.json")
    assert len(load_gate(KIT / "gate-v3.json")["_sha256"]) == 64


def test_v3a_recipe_reuses_v2_clips_exactly_and_holds_out_half_b():
    import yaml
    v2 = yaml.safe_load((KIT / "eidolon-training.yml").read_text(encoding="utf-8"))
    v3 = yaml.safe_load((KIT / "eidolon-training-v3.yml").read_text(encoding="utf-8"))
    for key in ("model_name", "target_phrase", "custom_negative_phrases", "n_samples", "n_samples_val"):
        assert v3[key] == v2[key], key          # sinon le générateur refuse ou régénère
    assert v3["false_positive_validation_data_path"].endswith("validation_half_a.npy")
    assert v3["target_false_positives_per_hour"] == 0.25 and v3["steps"] == 100000
    assert "dis-moi" not in (KIT / "eidolon-training-v3.yml").read_text().lower()


def test_split_validation_halves_are_disjoint_and_idempotent(tmp_path):
    import numpy as np
    src = tmp_path / "validation_set_features.npy"
    np.save(src, np.arange(10 * 96, dtype=np.float32).reshape(10, 96))
    a, b, m = tmp_path / "validation_half_a.npy", tmp_path / "validation_half_b.npy", tmp_path / "split.json"
    first = split(src, a, b, m)
    assert np.load(a).shape == (5, 96) and (np.load(b)[0] == np.load(src)[5]).all()
    assert split(src, a, b, m) == first
    np.save(src, np.zeros((10, 96), dtype=np.float32))
    with pytest.raises(SystemExit):
        split(src, a, b, m)


def test_detect_recording_writes_wake_eval_detections():
    d = detections([0.0] * 10 + [0.9] + [0.0] * 30 + [0.95], 0.5, "eidolon-x")
    assert d["schema"] == "eidolon-wake-detections/1"
    assert [e["at"] for e in d["events"]] == [0.88, 3.36]


def test_diagnose_table_splits_hits_and_misses():
    detail = [{"label": "positive", "phrase": "Eilledolon", "voice": "upmc", "duration_s": d, "max_score": s}
              for d, s in ((0.9, 0.9), (0.7, 0.1), (0.6, 0.2))]
    rows, cells = table(detail, 0.5)
    assert rows == [{"phrase": "Eilledolon", "voice": "upmc", "total": 3, "missed": 2, "recall": 0.3333,
                     "median_s_detected": 0.9, "median_s_missed": 0.65}]


def test_bench_uses_clean_holdout_only_for_models_selected_on_half_a(tmp_path):
    call = _bench_dry_run(tmp_path / "v3", {"run": "eidolon_v2", "config": "eidolon-training-v3.yml"}, half_b=True)
    assert "--holdout-features data/features/validation_half_b.npy --holdout-clean" in call
    assert "--gate /kit/wake_training/gate-v3.json" in call
    call = _bench_dry_run(tmp_path / "v2", {"run": "eidolon_v2"}, half_b=True)
    assert "--holdout-features data/features/validation_half_b.npy" in call and "--holdout-clean" not in call


def test_diagnose_refuses_a_bench_without_clip_detail(tmp_path):
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    (bin_dir / "docker").write_text("#!/bin/sh\nexit 0\n"); (bin_dir / "docker").chmod(0o755)
    models = tmp_path / "wake" / "models"; models.mkdir(parents=True)
    (models / "eidolon-1.onnx").write_bytes(b"x")
    (models / "eidolon-1.bench-eidolon.json").write_text("{}")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "WAKE_WORKDIR": str(tmp_path / "wake")}
    r = subprocess.run(["bash", str(KIT / "run_vm100.sh"), "diagnose"], env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "clips_detail" in r.stdout + r.stderr
