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
   noise and music): a (frames, 96) array that train.py windows itself, 16 frames per
   window, stride 1 frame = 80 ms; same windowing here, then false activations per hour.
3. With ``--generator`` (the unmodified wakeword-generator checkout), each held-out clip is
   traced back to its phrase and voice with the generator's own ``speaker_pool`` and
   ``sample_plan`` (imported, not copied), to see which spellings are missed and which
   near-words fire.
4. Every metric is given for a threshold sweep, so the operating point is chosen from
   measured data, not from the 0.5 default.
Synthetic clips are not the user's room: this bench gates training, not activation.
"""
import argparse
import json
from pathlib import Path
import sys
import wave

FRAME = 1280            # 80 ms at 16 kHz
DEBOUNCE_S = 2.0
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


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
    return timeline_scored([(label, len(samples), score_clip(samples)) for label, samples in clips],
                           threshold, gap_s)


def timeline_scored(scored, threshold, gap_s=1.0):
    """scored: [(label, n_samples, frame_scores)], scored once and reused for every threshold."""
    at, utterances, events = 0.0, [], []
    for label, n_samples, scores in scored:
        duration = n_samples / 16000
        for t in edges(scores, threshold, at):
            events.append({"at": t, "phrase": "eidolon", "score": 1.0})
        if label == "positive":
            utterances.append({"start": round(at, 3), "end": round(at + duration, 3), "phrase": "eidolon"})
        at += duration + gap_s
    annotation = {"schema": "eidolon-wake-annotation/1", "duration_s": round(max(at, 1.0), 3),
                  "utterances": utterances, "playback": [], "hardware_measured": False}
    return annotation, {"schema": "eidolon-wake-detections/1", "detector": "eidolon-oww", "events": events}


def feature_windows(features, length):
    """Model inputs of shape (1, length, 96), as train.py builds its false-positive set.

    A 2-D (frames, 96) array is windowed with stride 1 (one step = 80 ms); a 3-D
    (n, length, 96) array is already windowed. The exported model takes a batch of 1.
    """
    import numpy as np
    if features.ndim == 3:
        for i in range(features.shape[0]):
            yield np.asarray(features[i:i + 1, -length:], dtype=np.float32)
    elif features.ndim == 2:
        for i in range(features.shape[0] - length):
            yield np.asarray(features[i:i + length], dtype=np.float32)[None]
    else:
        raise ValueError("features must be (frames, 96) or (n, frames, 96)")


def clip_origin(generator_dir, manifest, voices_dir, split="test"):
    """Return origin(kind, index) -> (phrase, voice) using the generator's own plan."""
    sys.path.insert(0, str(generator_dir))
    import pipeline                                        # wakeword-generator, read only
    counts = []
    for voice in manifest["voices"]:
        config = json.loads((Path(voices_dir) / (voice["file"] + ".json")).read_text(encoding="utf-8"))
        counts.append(int(config["num_speakers"]))
    pool = pipeline.speaker_pool(counts, split)
    phrases = {"positive": manifest["target_phrase"], "negative": manifest["negative_phrases"]}

    def origin(kind, index):
        """(phrase, voice, planned speaker id); the generator may swap a speaker after short clips."""
        voice_index, speaker, _variation, phrase_index = pipeline.sample_plan(
            index, pool, 1, len(phrases[kind]))
        return phrases[kind][phrase_index], Path(manifest["voices"][voice_index]["file"]).stem, speaker
    return origin


def breakdown(scored_clips, threshold):
    """scored_clips: [(label, phrase, voice, speaker, scores)] -> fired/total per axis.

    Axes: phrase, voice, speaker (voice#id) and phrase_voice (cross table), so a weak
    spelling cannot hide behind a strong voice or the reverse.
    """
    out = {}
    for label, phrase, voice, speaker, scores in scored_clips:
        fired = any(x >= threshold for x in scores)
        for axis, key in (("phrase", phrase), ("voice", voice), ("speaker", f"{voice}#{speaker}"),
                          ("phrase_voice", f"{phrase} | {voice}")):
            cell = out.setdefault(label, {}).setdefault(axis, {}).setdefault(key, {"fired": 0, "total": 0})
            cell["total"] += 1
            cell["fired"] += fired
    return out


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
    p.add_argument("--holdout-features", type=Path,
                   help="négatifs jamais vus par train.py (moitié B), pour le critère FP/h")
    p.add_argument("--holdout-clean", action="store_true",
                   help="le modèle a été sélectionné sur la moitié A seulement")
    p.add_argument("--generator", type=Path, help="checkout de wakeword-generator (origine des clips)")
    p.add_argument("--gate", type=Path, help="critères écrits avant entraînement (eidolon-wake-gate/1)")
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

    files = [("positive", f) for f in sorted(a.positive_dir.glob("*.wav"))[:a.limit]]
    files += [("negative", f) for f in sorted(a.negative_dir.glob("*.wav"))[:a.limit]]
    clips = [(label, read_wav(f)) for label, f in files]
    scored = [(label, len(samples), score_clip(samples)) for label, samples in clips]
    origin = None
    if a.generator:
        manifest = json.loads((a.positive_dir.parent / "generation.json").read_text(encoding="utf-8"))
        origin = clip_origin(a.generator, manifest, a.generator / "data" / "voices")
        traced = [(label, *origin(label, int(f.stem)), sc[2]) for (label, f), sc in zip(files, scored)]
    detail = [{"file": f"{label}_test/{f.name}", "label": label, "duration_s": round(sc[1] / 16000, 3),
               "max_score": round(max(sc[2]), 4)} for (label, f), sc in zip(files, scored)]
    if origin is not None:
        for row, t in zip(detail, traced):
            row.update(phrase=t[1], voice=t[2], speaker=t[3])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))
    from wake_eval_g296 import score
    session = ort.InferenceSession(str(a.model), providers=["CPUExecutionProvider"])
    model_input = session.get_inputs()[0]
    length = int(model_input.shape[1])                       # 16 frames for openWakeWord

    def window_scores(path):
        features = np.load(path, mmap_mode="r")
        return [float(session.run(None, {model_input.name: w})[0].reshape(-1)[0])
                for w in feature_windows(features, length)]
    negative_scores = window_scores(a.negative_features) if a.negative_features else None
    holdout_scores = window_scores(a.holdout_features) if a.holdout_features else None
    gate = None
    if a.gate:
        from gate import evaluate_gate, load_gate
        gate = load_gate(a.gate)
    thresholds = sorted(set(THRESHOLDS) | {a.threshold})
    sweep = []
    for th in thresholds:
        annotation, detections = timeline_scored(scored, th)
        held = score(annotation, detections, window_s=1.5)
        row = {"threshold": th, "verdict": held["verdict"],
               "recall": held["phrases"]["eidolon"]["recall"],
               "false_per_hour_clips": held["phrases"]["eidolon"]["false_per_hour"],
               "latency_p95_ms": held["phrases"]["eidolon"].get("latency_p95_ms")}
        if negative_scores is not None:
            row["negative_features"] = false_per_hour(negative_scores, th)
        if holdout_scores is not None:
            row["holdout_features"] = false_per_hour(holdout_scores, th) | {"clean": a.holdout_clean}
        if origin is not None:
            row["breakdown"] = breakdown(traced, th)
        if gate is not None:
            row["gate"] = evaluate_gate(row, gate)
        sweep.append(row | {"_held_out": held})
    main_row = next(r for r in sweep if r["threshold"] == a.threshold)
    report = {"schema": "eidolon-wake-bench/1", "threshold": a.threshold,
              "clips": {"positive": sum(c[0] == "positive" for c in clips),
                        "negative": sum(c[0] == "negative" for c in clips)},
              "held_out_clips": main_row["_held_out"], "synthetic_only": True,
              "sweep": [{k: v for k, v in r.items() if k != "_held_out"} for r in sweep],
              "clips_detail": detail}
    if gate is not None:
        passing = [r for r in sweep if r["gate"]["pass"]]
        report["gate"] = {"source": gate["_source"], "sha256": gate["_sha256"],
                          "operating_threshold": max(passing, key=lambda r: (r["recall"], -r["threshold"]))["threshold"]
                          if passing else None}
    if negative_scores is not None:
        report["negative_features"] = main_row["negative_features"]
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for r in report["sweep"]:
        print(json.dumps({"threshold": r["threshold"], "recall": r["recall"],
                          "false_per_hour_clips": r["false_per_hour_clips"],
                          "false_per_hour_11h": (r.get("negative_features") or {}).get("false_per_hour"),
                          "false_per_hour_holdout": (r.get("holdout_features") or {}).get("false_per_hour"),
                          "latency_p95_ms": r["latency_p95_ms"], "verdict": r["verdict"],
                          "gate": (r.get("gate") or {}).get("reasons")}, ensure_ascii=False))
    if origin is not None:
        b = main_row["breakdown"]
        print(json.dumps({"threshold": a.threshold,
                          "missed_positive": {k: f'{v["total"] - v["fired"]}/{v["total"]}'
                                              for k, v in b["positive"]["phrase"].items()},
                          "positive_by_voice": {k: f'{v["fired"]}/{v["total"]}' for k, v in b["positive"]["voice"].items()},
                          "fired_negative": {k: f'{v["fired"]}/{v["total"]}'
                                             for k, v in b.get("negative", {}).get("phrase", {}).items()},
                          "positive_by_speaker": {k: f'{v["fired"]}/{v["total"]}' for k, v in b["positive"]["speaker"].items()},
                          "missed_by_phrase_voice": {k: f'{v["total"] - v["fired"]}/{v["total"]}'
                                                     for k, v in b["positive"]["phrase_voice"].items()}},
                         ensure_ascii=False))
    if gate is not None:
        print(json.dumps({"gate": report["gate"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
