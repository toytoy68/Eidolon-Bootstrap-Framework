#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/diagnose_clips.py
# Description : Pourquoi des clips « eidolon » sont ratés : durée, phonèmes, extraits à écouter (G296 v3)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Diagnose a bench report (eidolon-wake-bench/1 with clips_detail), without training.

1. Per spelling and voice: detected / missed, and median duration of each group
   (a missed group much shorter or longer than the detected one points at synthesis).
2. Phonemes of every target spelling as each voice's own eSpeak voice reads them
   (piper.phonemize_espeak, the phonemizer used to synthesize the clips).
3. A listening folder: up to N missed and N detected clips of the worst cells, copied
   (synthetic audio only). A human ear decides whether the clip says « Eille-do-lon ».
"""
import argparse
import json
from pathlib import Path
import shutil
import statistics


def table(detail, threshold):
    cells = {}
    for c in detail:
        if c["label"] != "positive" or "phrase" not in c:
            continue
        cell = cells.setdefault((c["phrase"], c["voice"]), {"hit": [], "miss": []})
        cell["hit" if c["max_score"] >= threshold else "miss"].append(c)
    rows = []
    for (phrase, voice), cell in sorted(cells.items()):
        n = len(cell["hit"]) + len(cell["miss"])
        med = lambda xs: round(statistics.median(x["duration_s"] for x in xs), 3) if xs else None
        rows.append({"phrase": phrase, "voice": voice, "total": n, "missed": len(cell["miss"]),
                     "recall": round(len(cell["hit"]) / n, 4), "median_s_detected": med(cell["hit"]),
                     "median_s_missed": med(cell["miss"])})
    return rows, cells


def phonemes(phrases, voices_dir):
    try:
        from piper.phonemize_espeak import EspeakPhonemizer
    except ImportError:
        return {"error": "piper not importable here"}
    p, out = EspeakPhonemizer(), {}
    for config in sorted(Path(voices_dir).glob("*.onnx.json")):
        voice = json.loads(config.read_text(encoding="utf-8")).get("espeak", {}).get("voice", "fr")
        out[config.name.removesuffix(".onnx.json")] = {
            ph: "".join("".join(s) for s in p.phonemize(voice, ph)) for ph in phrases}
    return out


def main():
    a = argparse.ArgumentParser(description="Diagnostic des clips ratés")
    a.add_argument("--bench", required=True, type=Path)
    a.add_argument("--clips-root", required=True, type=Path, help="output/<recette>")
    a.add_argument("--voices", required=True, type=Path)
    a.add_argument("--threshold", type=float)
    a.add_argument("--listen", type=int, default=8)
    a.add_argument("--out", required=True, type=Path)
    args = a.parse_args()
    bench = json.loads(args.bench.read_text(encoding="utf-8"))
    threshold = args.threshold if args.threshold is not None else bench["threshold"]
    rows, cells = table(bench["clips_detail"], threshold)
    manifest = json.loads((args.clips_root / "generation.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    worst = sorted(rows, key=lambda r: r["recall"])[:3]
    listen = args.out / "a-ecouter"
    listen.mkdir(exist_ok=True)
    for r in worst:
        cell = cells[(r["phrase"], r["voice"])]
        for kind in ("miss", "hit"):
            for c in sorted(cell[kind], key=lambda c: c["max_score"])[:args.listen]:
                name = f'{kind}-{r["voice"]}-{r["phrase"]}-{Path(c["file"]).name}'.replace(" ", "_").replace("?", "Q").replace("!", "E")
                shutil.copyfile(args.clips_root / c["file"], listen / name)
    report = {"schema": "eidolon-wake-diagnosis/1", "bench": str(args.bench), "threshold": threshold,
              "cells": rows, "worst_cells": worst,
              "phonemes": phonemes(manifest["target_phrase"], args.voices)}
    (args.out / "diagnostic.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps({"phonemes": report["phonemes"]}, ensure_ascii=False))
    print(json.dumps({"listen": str(listen), "files": len(list(listen.iterdir()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
