# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : mutations.py
# Description : Vérifie que les tests de session détectent quatre garde-fous retirés (C-TASK-G031)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core/: python3 docs/validation/2026-10-06/claude-g031/mutations.py
Each mutation is applied to session.js in place, tested, then the original is restored."""
from pathlib import Path
import subprocess

PATH = Path("desktop/connected/src/session.js")
MUTATIONS = {
    "garde connEpoch retirée": ("      if (epoch !== state.connEpoch) { state.stats.staleConnection += 1; return { stale: true }; }\n      var status", "      var status"),
    "pas d'effacement si autre base": ("        wipe();\n        state.notice", "        state.notice"),
    "jeton de sélection ignoré": ("if (!sel || sel.token !== req.token)", "if (!sel)"),
    "jeton gardé après 401": ("token = null; state.connEpoch += 1;", "state.connEpoch += 1;"),
}
original = PATH.read_text(encoding="utf-8")
try:
    for name, (before, after) in MUTATIONS.items():
        assert original.count(before) == 1, name
        PATH.write_text(original.replace(before, after), encoding="utf-8")
        run = subprocess.run(["node", "--test", "desktop/connected/tests/session.test.js"], capture_output=True, text=True)
        failed = [line for line in run.stdout.splitlines() if line.startswith("not ok")]
        print(f"{name}: {len(failed)} échec(s) — " + "; ".join(failed))
finally:
    PATH.write_text(original, encoding="utf-8")
