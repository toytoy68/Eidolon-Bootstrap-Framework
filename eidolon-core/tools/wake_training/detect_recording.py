#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/detect_recording.py
# Description : Détections d'un modèle « eidolon » sur un enregistrement réel, pour wake_eval (G296 v3)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run a trained model over one real recording, as the live client would, and write
an eidolon-wake-detections/1 log for tools/evaluation/wake_eval_g296.py.

Streaming: one detector state for the whole file (no reset between frames), 80 ms
frames, rising edges above the threshold with a 2 s debounce (same as bench_model).
Recordings stay on the machine that made them; nothing is uploaded.
"""
import argparse
import json
from pathlib import Path

from bench_model import FRAME, edges, read_wav


def detections(scores, threshold, detector):
    return {"schema": "eidolon-wake-detections/1", "detector": detector,
            "events": [{"at": t, "phrase": "eidolon", "score": 1.0} for t in edges(scores, threshold, 0.0)]}


def main():
    p = argparse.ArgumentParser(description="Détections du mot d'appel sur un enregistrement")
    p.add_argument("--model", required=True, type=Path)
    p.add_argument("--melspec", required=True, type=Path)
    p.add_argument("--embedding", required=True, type=Path)
    p.add_argument("--recording", required=True, type=Path, help="WAV 16 kHz mono PCM16")
    p.add_argument("--threshold", required=True, type=float)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    from openwakeword.model import Model
    m = Model(wakeword_models=[str(a.model)], inference_framework="onnx",
              melspec_model_path=str(a.melspec), embedding_model_path=str(a.embedding))
    samples = read_wav(a.recording)
    scores = [float(next(iter(m.predict(samples[i:i + FRAME]).values())))
              for i in range(0, len(samples) - FRAME + 1, FRAME)]
    a.out.write_text(json.dumps(detections(scores, a.threshold, a.model.stem), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
