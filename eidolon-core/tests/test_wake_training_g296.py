# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_wake_training_g296.py
# Description : Kit d'entraînement « eidolon » : garde VM100, banc, configuration (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1] / "tools" / "wake_training"
sys.path.insert(0, str(KIT))
from guard import decide  # noqa: E402
from bench_model import edges, false_per_hour, feature_windows, timeline, timeline_scored  # noqa: E402

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
