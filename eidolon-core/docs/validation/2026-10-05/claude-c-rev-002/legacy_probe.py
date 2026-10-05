# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : legacy_probe.py
# Description : Reprise par le code corrigé de missions créées avant correction
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Sonde C-REV-002 « appels anciens » (Claude). États synthétiques uniquement.

Un arbre de l'ancien commit (b45ac76) crée des missions interrompues ; le code
de l'arbre courant les reprend. Depuis eidolon-core/ :

    git worktree add --detach /tmp/old-b45ac76 b45ac76
    REVIEW2_OLD_TREE=/tmp/old-b45ac76/eidolon-core PYTHONDONTWRITEBYTECODE=1 \
        PYTHONPATH=src:. python docs/validation/2026-10-05/claude-c-rev-002/legacy_probe.py
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve()
TWO_STEPS = json.dumps({"version": 1, "steps": [
    {"id": "a", "tool": "text.stats", "parameters": {"reference": "synthetic-note@1"}},
    {"id": "b", "tool": "text.stats", "parameters": {"reference": "synthetic-note@1"}}]},
    sort_keys=True, separators=(",", ":"))


def build(directory, slow=False):
    # Uniquement des API présentes dans les deux versions.
    from eidolon_core.runtime import Limits, Runtime
    from eidolon_core.store import Store
    from eidolon_core.tools import Registry, default_registry
    from tests.support import FixedModel, slow_tool
    registry = None
    if slow:
        registry = Registry([replace(default_registry().get("text.stats"), execute=slow_tool)])
    return Store(directory), lambda checkpoint=None: Runtime(
        Store(directory), model=FixedModel(TWO_STEPS), registry=registry,
        limits=Limits(0.6) if slow else None, checkpoint=checkpoint)


def old_side(directory, scenario):
    """Exécuté avec l'ancien code : laisse une mission dans l'état voulu."""
    store, make = build(directory, slow=scenario in ("review", "reconciled"))
    runtime = make()
    identity = runtime.create("Mission synthétique héritée")["id"]
    Path(directory, "identity").write_text(identity)
    if scenario in ("review", "reconciled"):
        runtime.run(identity)  # délai -> REVIEW_REQUIRED par l'ancien code
        if scenario == "reconciled":
            runtime.reconcile(identity, decision="no-effect", actor="ancien", reason="avant correction")
        return
    boundary, occurrence = {"verified": ("RESULT_VERIFIED", 1), "started": ("CALL_STARTED", 1),
                            "returned": ("RESULT_SAVED", 1)}[scenario]
    count = {"n": 0}

    def crash(kind):
        if kind == boundary:
            count["n"] += 1
            if count["n"] == occurrence:
                os._exit(77)
    make(crash).run(identity)


def new_side():
    from eidolon_core.store import Busy
    old_tree = os.environ["REVIEW2_OLD_TREE"]
    import eidolon_core
    print("Python", sys.version.split()[0], "| code courant :", Path(eidolon_core.__file__).parent)
    for scenario, label in (("verified", "1er appel VERIFIED puis arrêt brutal"),
                            ("returned", "sortie enregistrée (RETURNED) puis arrêt brutal"),
                            ("started", "arrêt brutal pendant l'appel (STARTED)"),
                            ("review", "REVIEW_REQUIRED posé par l'ancien code (délai)"),
                            ("reconciled", "no-effect déjà accepté par l'ancien code")):
        directory = tempfile.mkdtemp(prefix="c-rev-002-legacy-")
        env = dict(os.environ, PYTHONPATH=f"{old_tree}/src:{old_tree}")
        done = subprocess.run([sys.executable, str(HERE), "--old", directory, scenario], env=env,
                              capture_output=True, text=True, timeout=60, cwd=old_tree)
        identity = Path(directory, "identity").read_text()
        slow = scenario in ("review", "reconciled")
        store, make = build(directory, slow=slow)
        before = store.get(identity)
        print(f"\n[{label}] ancien processus : code {done.returncode}")
        print("  état hérité :", before["status"], before["phase"],
              [(c["status"], c.get("worker_protocol")) for c in before["calls"]])
        runtime = make()
        m = runtime.run(identity)
        print("  run (code courant) :", m["status"], m["phase"], (m["error"] or {}).get("code"),
              [(c["status"], c.get("worker_protocol")) for c in m["calls"]])
        if m["status"] == "REVIEW_REQUIRED":
            accepted = False
            for decision in ("no-effect", "observed-result"):
                try:
                    runtime.reconcile(identity, decision=decision, actor="relecteur", reason="appel hérité",
                                      output={"x": 1} if decision == "observed-result" else None)
                    print(f"  reconcile {decision} : ACCEPTÉ (nouvelle tentative lancée par le code courant)")
                    accepted = True
                    break
                except (Busy, ValueError) as exc:
                    print(f"  reconcile {decision} : refus {type(exc).__name__}: {exc}")
            if not accepted:
                m = runtime.reconcile(identity, decision="abandon", actor="relecteur", reason="appel hérité")
                print("  reconcile abandon :", m["status"], m["error"]["code"], [c["status"] for c in m["calls"]])
        kinds = [e["kind"] for e in store.events(identity)]
        print("  CALL_STARTED :", kinds.count("CALL_STARTED"), "| WORKER_SPAWNED :", kinds.count("WORKER_SPAWNED"))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--old":
        old_side(sys.argv[2], sys.argv[3])
    else:
        new_side()
