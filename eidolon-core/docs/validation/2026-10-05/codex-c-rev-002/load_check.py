# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : load_check.py
# Description : Contrôle ciblé des deux tests signalés sensibles à la charge
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Run only the two N-08 regressions, with six disposable CPU competitors."""
import os
import subprocess
import sys

if __name__ == "__main__":
    workers = []
    try:
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
        print("Python", sys.version.split()[0], "CPU affinity", len(os.sched_getaffinity(0)),
              "six competing CPU processes", flush=True)
        for _ in range(6):
            workers.append(subprocess.Popen([sys.executable, "-c", "while True: pass"]))
        result = subprocess.run([sys.executable, "-m", "unittest", "-v",
            "tests.test_core.CoreTests.test_verification_timeout_keeps_receipt_without_success",
            "tests.test_review_regressions.ReviewRegressionTests.test_f05_model_timeout_and_outage_resume_same_mission"],
            timeout=90)
    finally:
        for worker in workers:
            worker.terminate()
        for worker in workers:
            try:
                worker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
    raise SystemExit(result.returncode)
