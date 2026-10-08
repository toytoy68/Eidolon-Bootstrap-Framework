# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : demo_g065.py
# Description : Sorties CLI JSON et humaine des deux contre-exemples G061 corrigés (C-TASK-G065)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""PYTHONPATH=src python3 docs/validation/2026-10-08/claude-g065/demo_g065.py   (synthetic, temporary)"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.recovery import prepare_review
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store


def cli(state, *argv):
    p = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(state), *argv], capture_output=True,
                       text=True, stdin=subprocess.DEVNULL, env=os.environ, timeout=60)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state"
        rt = Runtime(Store(state), limits=Limits(max_invocations=3))
        m = rt.run(rt.create(DEMO_REQUEST)["id"])
        print(f"mission : {m['status']} / {m['error']['code']}")
        code, out, _ = cli(state, "runtime-inspect", m["id"])
        r = json.loads(out)
        print(f"runtime-inspect JSON (code {code}) : budget {r['invocation_budget']} ; recorded_block {r['recorded_block']} ; "
              f"hints {r['hints']} ; authorizes_execution {r['authorizes_execution']}")
        code, out, _ = cli(state, "--format", "human", "runtime-inspect", m["id"])
        print(f"runtime-inspect humain (code {code}) :")
        print("\n".join(line for line in out.splitlines() if "Budget" in line or "Blocage" in line or "ATTENTION" in line))
        review = Path(tmp) / "review"
        prepare_review(state / "missions.sqlite3", review, actor="synthetic", reason="g065")
        for fmt in ("json", "human"):
            code, out, err = cli(review, "--format", fmt, "recovery-inspect", "--mission-id", "m-" + "e" * 32)
            print(f"recovery-inspect mission absente ({fmt}) : code {code} ; stdout vide {out == ''} ; stderr {err}")


if __name__ == "__main__":   # tool workers use multiprocessing "spawn"
    main()
