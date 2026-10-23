#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/guard.py
# Description : Met l'entraînement du mot d'appel en pause quand Eidolon sert ou chauffe (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Training must never disturb Gemma, Core or DARME on VM100.

Every ``interval`` seconds the guard reads Core's activity receipt (``activity.json``,
exported by Core every 10 s, G270) and the GPU temperatures. The training container is
paused (``docker pause``: processes frozen, memory kept) while:
  - a user interacted with Eidolon less than ``quiet_s`` ago, or the receipt is stale/unreadable
    (unknown activity = paused: the user comes first);
  - any GPU is at or above ``max_temp_c``;
and resumed when both conditions clear. It never stops, kills or restarts anything else.
"""
import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import time


def decide(*, now, activity, temperatures, quiet_s=600, receipt_max_age_s=60, max_temp_c=82):
    """Return (run: bool, reasons: list). Pure; tested offline."""
    reasons = []
    try:
        if not isinstance(activity, dict) or activity.get("schema") != "eidolon-activity-receipt/1":
            raise ValueError
        observed = datetime.fromisoformat(activity["observed_at"])
        last = datetime.fromisoformat(activity["last_activity"])
        if observed.tzinfo is None or last.tzinfo is None:
            raise ValueError
        if (now - observed).total_seconds() > receipt_max_age_s or observed > now:
            reasons.append("ACTIVITY_RECEIPT_STALE")
        elif (now - last).total_seconds() < quiet_s:
            reasons.append("USER_ACTIVE")
    except (ValueError, KeyError, TypeError):
        reasons.append("ACTIVITY_UNKNOWN")
    if not temperatures:
        reasons.append("GPU_TEMPERATURE_UNKNOWN")
    elif max(temperatures) >= max_temp_c:
        reasons.append("GPU_TOO_HOT")
    return not reasons, reasons


def gpu_temperatures():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        return [int(x) for x in out.split()]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def read_activity(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    p = argparse.ArgumentParser(description="Pause/reprise de l'entraînement selon l'activité d'Eidolon et la température GPU")
    p.add_argument("--container", required=True)
    p.add_argument("--activity", required=True, help="activity.json exporté par Core")
    p.add_argument("--interval", type=float, default=15)
    p.add_argument("--quiet", type=float, default=600, help="secondes sans interaction avant de reprendre")
    p.add_argument("--max-temp", type=int, default=82)
    a = p.parse_args()
    paused = False
    while True:
        alive = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", a.container],
                               capture_output=True, text=True)
        if alive.returncode != 0 or alive.stdout.strip() != "true":
            print(json.dumps({"guard": "container_gone"}), flush=True)
            return 0
        run, reasons = decide(now=datetime.now(timezone.utc), activity=read_activity(a.activity),
                              temperatures=gpu_temperatures(), quiet_s=a.quiet, max_temp_c=a.max_temp)
        if run and paused:
            subprocess.run(["docker", "unpause", a.container], check=False); paused = False
            print(json.dumps({"guard": "resumed"}), flush=True)
        elif not run and not paused:
            subprocess.run(["docker", "pause", a.container], check=False); paused = True
            print(json.dumps({"guard": "paused", "reasons": reasons}), flush=True)
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
