#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/split_validation.py
# Description : Sépare les ~11 h de négatifs openWakeWord en moitiés A (sélection) et B (banc) (G296 v3)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""train.py picks and merges checkpoints on false_positive_validation_data_path.
Measuring false activations on that same file is not a held-out test. Half A (first
frames) goes to train.py, half B (last frames) only to the bench. Contiguous halves:
frames are consecutive 80 ms steps of real audio, so no window straddles both except
at the single cut. Idempotent; refuses to overwrite halves of another source.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def split(source, half_a, half_b, manifest):
    import numpy as np
    source_sha = sha256(source)
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["source_sha256"] != source_sha:
            raise SystemExit("moitiés d'une autre source : refus")
        if half_a.exists() and half_b.exists() and sha256(half_a) == previous["half_a_sha256"] \
                and sha256(half_b) == previous["half_b_sha256"]:
            return previous
    data = np.load(source, mmap_mode="r")
    if data.ndim != 2:
        raise SystemExit("validation features must be (frames, 96)")
    cut = data.shape[0] // 2
    np.save(half_a, np.ascontiguousarray(data[:cut]))
    np.save(half_b, np.ascontiguousarray(data[cut:]))
    record = {"schema": "eidolon-wake-validation-split/1", "source": source.name, "source_sha256": source_sha,
              "frames": int(data.shape[0]), "cut": int(cut),
              "half_a": half_a.name, "half_a_sha256": sha256(half_a),
              "half_b": half_b.name, "half_b_sha256": sha256(half_b),
              "note": "train.py assumes 11.3 h: its FP/h on half A is reported about 2x too low"}
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    p = argparse.ArgumentParser(description="Moitiés A/B des négatifs de validation")
    p.add_argument("--features-dir", required=True, type=Path)
    a = p.parse_args()
    d = a.features_dir
    print(json.dumps(split(d / "validation_set_features.npy", d / "validation_half_a.npy",
                           d / "validation_half_b.npy", d / "validation_split.json")))


if __name__ == "__main__":
    main()
