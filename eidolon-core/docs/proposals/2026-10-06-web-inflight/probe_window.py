# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_window.py
# Description : Fenêtre réponse reçue / pause non commise, en processus réels (C-TASK-G030)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic multi-process probe of the CURRENT code; no network, no real provider.

A child process runs one research with durable pauses. The provider answers 429
(RATE_LIMITED, retry_after=120) and appends one line per contact to a counter file.
The child may die with os._exit at a chosen point. A second, fresh child then runs
the same research, as a rebuilt coordinator would. The counter shows whether the
provider was contacted again. Today's expected answer for the windows before the
pause commit is "yes": that is the gap the proposed journal must close.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CHILD = r'''
import os, sys
from pathlib import Path
from eidolon_core import research_pauses
from eidolon_core.research import AccessFailure, ResearchCoordinator
from eidolon_core.research_pauses import ResearchPauses

state, counter, crash = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]

class Provider:
    provider_id = "provider.synthetic"
    def search(self, query, limit):
        with counter.open("a") as f:
            f.write("contact\n"); f.flush(); os.fsync(f.fileno())
        if crash == "in_exchange":
            os._exit(9)          # request delivered, answer never seen
        raise AccessFailure("RATE_LIMITED", retry_after=120)

class Reader:
    reader_id = "reader.synthetic"
    def read(self, url, policy):
        raise AssertionError("no read expected")

original = ResearchPauses.pause
def pause(self, *args, **kwargs):
    if crash == "before_pause_commit":
        os._exit(9)              # 429 received, pause not written
    result = original(self, *args, **kwargs)
    if crash == "after_pause_commit":
        os._exit(9)              # pause written, report never returned
    return result
ResearchPauses.pause = pause

coordinator = ResearchCoordinator([Provider()], Reader(), resolver=lambda host: [],
                                  pauses=ResearchPauses(state / "research-pauses.sqlite3"))
report = coordinator.run("requete synthetique")
print(report["providers"][0]["status"])
'''


def child(src, state, counter, crash):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([sys.executable, "-c", CHILD, str(state), str(counter), crash],
                          env=env, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout.strip() or done.stderr.strip().splitlines()[-1:]


def scenario(src, crash):
    with tempfile.TemporaryDirectory() as tmp:
        state, counter = Path(tmp), Path(tmp) / "contacts.txt"
        first = child(src, state, counter, crash)
        second = child(src, state, counter, "none")
        contacts = len(counter.read_text().splitlines()) if counter.exists() else 0
        return {"crash": crash, "first_run": first, "rebuilt_run": second, "provider_contacts": contacts}


def main():
    src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "src"
    for crash in ("none", "in_exchange", "before_pause_commit", "after_pause_commit"):
        print(json.dumps(scenario(src, crash), ensure_ascii=False))


if __name__ == "__main__":
    main()
