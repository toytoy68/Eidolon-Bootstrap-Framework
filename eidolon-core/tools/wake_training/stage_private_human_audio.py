#!/usr/bin/env python3
"""Stage private, operator-approved wakeword clips outside the official generator.

No training, feature extraction or validation set mutation is performed here.
Never commit this input archive or its outputs to a public Git repository.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import wave
import zipfile

def stage(archive: Path, destination: Path, *, accept_unreviewed: bool = False) -> dict:
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest.get("schema") != "eidolon-private-human-training/1":
            raise ValueError("unexpected private training manifest")
        if manifest.get("held_out") is not False:
            raise ValueError("never import held-out evaluation audio into training")
        clips = manifest.get("clips", [])
        if len(clips) == 0 or len(clips) > 500:
            raise ValueError("unexpected number of clips")
        if not accept_unreviewed and any(not c.get("verified_word", False) for c in clips):
            raise ValueError("manual review required: clips are not verified")
        if destination.exists() and any(destination.iterdir()):
            raise FileExistsError("destination must be empty")
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(destination, 0o700)
        staged = []
        for c in clips:
            name = c["file"]
            if "/" in name or "\\\\" in name or not name.endswith(".wav") or Path(name).name != name:
                raise ValueError("unexpected filename")
            audio = bundle.read(name)
            if hashlib.sha256(audio).hexdigest() != c["sha256"]:
                raise ValueError(f"sha256 mismatch for {name}")
            with wave.open(io.BytesIO(audio)) as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                    raise ValueError(f"unexpected PCM format for {name}")
                if not (0.25 <= wav.getnframes() / 16000 <= 4):
                    raise ValueError(f"unexpected clip duration for {name}")
            path = destination / name
            with path.open("xb") as output:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
                output.write(audio)
            staged.append({"name": name, "sha256": c["sha256"], "duration_ms": c["duration_ms"]})
        (destination / "import.json").write_text(json.dumps({
            "schema": "eidolon-human-staging/1",
            "state": "staged-only-not-trained",
            "verified_by_human": not accept_unreviewed,
            "clips": staged
        }, indent=2), encoding="utf8")
        os.chmod(destination / "import.json", 0o600)
    return {"clips": len(staged), "location": str(destination), "state": "staged-only-not-trained"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--allow-unreviewed-for-diagnostics-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(stage(args.archive, args.destination,
        accept_unreviewed=args.allow_unreviewed_for_diagnostics_only)))
