#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/bench_model.py
# Description : Banc du modèle « eidolon » sur clips de test et 11 h de négatifs (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Bench a trained openWakeWord model; output feeds tools/evaluation/wake_eval_g296.py.

1. Held-out clips (positive_test, negative_test made by the generator, never trained on)
   are laid end to end on a virtual timeline with 1 s gaps, scored frame by frame (80 ms),
   and written as an annotation + detections pair (detection = rising edge >= threshold,
   2 s debounce, as a live detector would do).
2. Optional ``--negative-features`` (openWakeWord validation features, ~11 h of speech,
   noise and music): false activations per hour on 16x96 windows, one step = 80 ms.
Synthetic clips are not the user's room: this bench gates training, not activation.
"""
import argparse
import json
from pathlib import Path
import sys
import wave

FRAME = 1280            # 80 ms at 16 kHz
DEBOUNCE_S = 2.0


def read_wav(path):
    import numpy as np
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 16000:
            raise ValueError("16 kHz mono PCM16 required: " + path.name)
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def edges(scores, threshold, start_s):
    """Rising edges >= threshold with debounce; scores are per 80 ms frame."""
    out, last = [], -1e9
    for i, s in enumerate(scores):
        t = start_s + (i + 1) * FRAME / 16000
        if s >= threshold and t - last >= DEBOUNCE_S:
            out.append(round(t, 3)); last = t
    return out


def timeline(clips, score_clip, threshold, gap_s=1.0):
    """clips: [(label, samples)] -> (annotation, detections) for wake_eval_g296."""
    at, utterances, events = 0.0, [], []
    for label, samples in clips:
        duration = len(samples) / 16000
        for t in edges(score_clip(samples), threshold, at):
            events.append({"at": t, "phrase": "eidolon", "score": 1.0})
        if label == "positive":
            utterances.append({"start": round(at, 3), "end": round(at + duration, 3), "phrase": "eidolon"})
        at += duration + gap_s
    annotation = {"schema": "eidolon-wake-annotation/1", "duration_s": round(max(at, 1.0), 3),
                  "utterances": utterances, "playback": [], "hardware_measured": False}
    return annotation, {"schema": "eidolon-wake-detections/1", "detector": "eidolon-oww", "events": events}


def false_per_hour(windows_scores, threshold):
    n = len(windows_scores)
    hours = n * FRAME / 16000 / 3600
    count = len(edges(windows_scores, threshold, 0.0))
    return {"windows": n, "hours": round(hours, 3), "false_activations": count,
            "false_per_hour": round(count / hours, 3) if hours else None}


def main():
    p = argparse.ArgumentParser(description="Banc du modèle de mot d'appel Eidolon")
    p.add_argument("--model", required=True, type=Path)
    p.add_argument("--melspec", required=True, type=Path)
    p.add_argument("--embedding", required=True, type=Path)
    p.add_argument("--positive-dir", required=True, type=Path)
    p.add_argument("--negative-dir", required=True, type=Path)
    p.add_argument("--negative-features", type=Path)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--limit", type=int, default=2000)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    import numpy as np
    import onnxruntime as ort
    from openwakeword.model import Model

    m = Model(wakeword_models=[str(a.model)], inference_framework="onnx",
              melspec_model_path=str(a.melspec), embedding_model_path=str(a.embedding))

    def score_clip(samples):
        m.reset()                                   # clips are independent
        padded = np.concatenate([samples, np.zeros(FRAME * 12, dtype=samples.dtype)])   # let the window close
        return [float(next(iter(m.predict(padded[i:i + FRAME]).values())))
                for i in range(0, len(padded) - FRAME + 1, FRAME)]

    clips = [("positive", read_wav(f)) for f in sorted(a.positive_dir.glob("*.wav"))[:a.limit]]
    clips += [("negative", read_wav(f)) for f in sorted(a.negative_dir.glob("*.wav"))[:a.limit]]
    annotation, detections = timeline(clips, score_clip, a.threshold)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))
    from wake_eval_g296 import score
    report = {"schema": "eidolon-wake-bench/1", "threshold": a.threshold,
              "clips": {"positive": sum(c[0] == "positive" for c in clips),
                        "negative": sum(c[0] == "negative" for c in clips)},
              "held_out_clips": score(annotation, detections, window_s=1.5), "synthetic_only": True}
    if a.negative_features:
        features = np.load(a.negative_features, mmap_mode="r")
        session = ort.InferenceSession(str(a.model), providers=["CPUExecutionProvider"])
        name = session.get_inputs()[0].name
        scores = []
        # openWakeWord exports a batch of exactly 1 (train.py export_to_onnx): one window per call.
        for i in range(len(features)):
            window = np.asarray(features[i:i + 1], dtype=np.float32)
            scores.append(float(session.run(None, {name: window})[0].reshape(-1)[0]))
        report["negative_features"] = false_per_hour(scores, a.threshold)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "held_out_clips"} | {
        "verdict": report["held_out_clips"]["verdict"],
        "recall": report["held_out_clips"]["phrases"]["eidolon"]["recall"],
        "false_per_hour_clips": report["held_out_clips"]["phrases"]["eidolon"]["false_per_hour"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
