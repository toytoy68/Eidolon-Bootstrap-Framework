# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes.py
# Description : Sondes synthétiques de la contre-revue C-TASK-G005 (C-005a)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Probes for C-005a at 5c169cb (Claude). Temporary state, synthetic world only.

From eidolon-core/:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-g005/probes.py
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import encode
from eidolon_core.store import Store

HERE = Path(__file__).resolve()


def fresh():
    directory = tempfile.mkdtemp(prefix="claude-g005-")
    store = Store(directory)
    return directory, store, ActionRuntime(store)


def restarts(runtime):
    return runtime.world.observe("sim-nas")["restarts"]


def short(m):
    return f"{m['status']} / {(m.get('error') or {}).get('code')} / proposition {(m.get('proposal') or {}).get('status')}"


def attempt(label, function):
    try:
        m = function()
        print(f"  {label}: {short(m)}")
        return m
    except BaseException as exc:  # noqa: BLE001
        print(f"  {label}: REFUS {type(exc).__name__}: {str(exc)[:110]}")
        return None


def approve(runtime, m, decision="approve", sha=None):
    return lambda: runtime.decide(m["id"], expected_sha256=sha or m["proposal"]["sha256"], decision=decision,
                                  actor="relecteur", reason="sonde G005")


def reconcile(runtime, identity, decision, **kwargs):
    return lambda: runtime.reconcile(identity, decision=decision, actor="relecteur", reason="sonde G005", **kwargs)


def kinds(store, identity):
    return [e["kind"] for e in store.events(identity)]


def probe_boundaries():
    print("\n[1] Interruption du parent à chaque frontière, après accord")
    for boundary in ("ACTION_CONDITION_CHECKED", "CALL_STARTED", "WORKER_SPAWNED", "TOOL_RETURNED"):
        directory, store, runtime = fresh()
        m = runtime.run(runtime.create_restart("nas")["id"])
        runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                       actor="relecteur", reason="sonde G005")
        code = subprocess.run([sys.executable, str(HERE), "--crash", directory, m["id"], boundary],
                              capture_output=True, timeout=60).returncode
        m = runtime.run(m["id"])
        print(f"  mort à {boundary} (code {code}) -> {short(m)} | redémarrages {restarts(runtime)}")
        if m["status"] == "REVIEW_REQUIRED":
            receipt = runtime.world.receipt(m["id"])
            attempt("    no-effect confirmé", reconcile(runtime, m["id"], "no-effect", confirm_no_effect=True))
            if receipt is not None:
                attempt("    observed-result (reçu du simulateur)",
                        reconcile(runtime, m["id"], "observed-result", output=receipt["result"]))
                final = attempt("    run", lambda: runtime.run(m["id"]))
            else:
                again = attempt("    run (nouvelle tentative)", lambda: runtime.run(m["id"]))
                if again and again["proposal"]["status"] == "PENDING":
                    print("    ancien accord réutilisé : non ; historique :", len(again.get("proposal_history", [])))
                    attempt("    nouvel accord", approve(runtime, again))
                final = attempt("    run", lambda: runtime.run(m["id"]))
        else:
            final = m if m["status"] != "BLOCKED" else attempt("    run", lambda: runtime.run(m["id"]))
        print(f"    bilan : {short(final) if final else '-'} | redémarrages {restarts(runtime)}"
              f" | CALL_STARTED {kinds(store, m['id']).count('CALL_STARTED')}")


def probe_copied_approval():
    print("\n[2] Accord copié d'une mission à l'autre")
    directory, store, runtime = fresh()
    a = runtime.run(runtime.create_restart("nas")["id"])
    b = runtime.run(runtime.create_restart("nas")["id"])
    print("  empreintes différentes :", a["proposal"]["sha256"] != b["proposal"]["sha256"])
    attempt("decide B avec l'empreinte de A", approve(runtime, b, sha=a["proposal"]["sha256"]))
    attempt("decide A avec l'empreinte de A", approve(runtime, a))
    attempt("run B (non approuvée)", lambda: runtime.run(b["id"]))
    print("  redémarrages :", restarts(runtime))


def probe_condition_changes():
    print("\n[3] DOWN -> UP -> DOWN après accord (même état, révision différente)")
    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                   actor="relecteur", reason="sonde G005")
    runtime.world.set_state("sim-nas", "UP")
    runtime.world.set_state("sim-nas", "DOWN")
    m = attempt("run", lambda: runtime.run(m["id"]))
    print("  appels :", len(m["calls"]), "| redémarrages :", restarts(runtime))
    attempt("ré-approuver la même proposition", approve(runtime, m))


def probe_concurrent_missions():
    print("\n[4] Deux missions approuvées sur la même révision ; B passe le contrôle, A agit avant B")
    directory, store, runtime = fresh()
    a = runtime.run(runtime.create_restart("nas")["id"])
    b = runtime.run(runtime.create_restart("nas")["id"])
    for m in (a, b):
        runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                       actor="relecteur", reason="sonde G005")

    def checkpoint(kind):
        if kind == "CALL_STARTED":  # B has checked the condition and consumed its approval
            runtime.run(a["id"])

    racer = ActionRuntime(store, world=runtime.world, checkpoint=checkpoint)
    b = attempt("run B (A s'exécute pendant B)", lambda: racer.run(b["id"]))
    print("  A :", short(store.get(a["id"])), "| redémarrages :", restarts(runtime),
          "| reçu B :", runtime.world.receipt(b["id"]) is not None)
    if b and b["status"] == "REVIEW_REQUIRED":
        print("  erreur rendue par l'outil de B :", (b["calls"][0].get("error_receipt") or {}).get("message", "")[:90])
        attempt("  no-effect sans confirmation", reconcile(runtime, b["id"], "no-effect"))
        attempt("  abandon", reconcile(runtime, b["id"], "abandon"))


def probe_cancel_and_revoke():
    print("\n[5] Annulation et révocation")
    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                   actor="relecteur", reason="sonde G005")
    store.request_cancel(m["id"])
    m = attempt("annulation après accord, puis run", lambda: runtime.run(m["id"]))
    print("  redémarrages :", restarts(runtime))

    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                   actor="relecteur", reason="sonde G005")

    def cancel_at_start(kind):
        if kind == "CALL_STARTED":
            store.request_cancel(m["id"])

    late = ActionRuntime(store, world=runtime.world, checkpoint=cancel_at_start)
    m = attempt("annulation juste après CALL_STARTED (accord consommé)", lambda: late.run(m["id"]))
    if m:
        history = (m["calls"][0].get("attempt_history") or [{}])[-1]
        print("  redémarrages :", restarts(runtime), "| statut de l'accord :", m["proposal"]["status"],
              "| tentative tracée non autorisée :", history.get("reconciliation", {}).get("decision"))

    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    attempt("approve", approve(runtime, m))
    attempt("revoke", approve(runtime, m, decision="revoke"))
    attempt("run après révocation", lambda: runtime.run(m["id"]))
    attempt("ré-approuver après révocation", approve(runtime, m))
    print("  redémarrages :", restarts(runtime))


@dataclass(frozen=True)
class TamperingModel:
    field: str
    model_id: str = "probe-tampering-action/1"

    def propose(self, request, context):
        parameters = dict(context["_core_action"])
        parameters[self.field] = ("m-" + "0" * 32 if self.field == "operation_id"
                                  else parameters[self.field] + 1 if self.field == "expected_revision"
                                  else "sim-other")
        return encode({"version": 1, "steps": [{"id": "restart", "tool": "service.restart.simulated",
                                                "parameters": parameters}]})


def probe_model_tampering():
    print("\n[6] Un modèle modifie les paramètres de l'action")
    for field in ("expected_revision", "operation_id", "target"):
        directory, store, runtime = fresh()
        tampering = ActionRuntime(store, world=runtime.world, model=TamperingModel(field))
        m = attempt(f"paramètre {field} altéré", lambda: tampering.run(tampering.create_restart("nas")["id"]))
        print("    proposition créée :", bool(m and m.get("proposal")), "| appels :", len(m["calls"]) if m else "-",
              "| redémarrages :", restarts(runtime))


def probe_after_success():
    print("\n[7] Après succès : preuve historique, santé actuelle, mémoire, proposition ancienne")
    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    context_before = json.dumps(m["context"], sort_keys=True)
    runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                   actor="relecteur", reason="sonde G005")
    m = runtime.run(m["id"])
    runtime.world.set_state("sim-nas", "DOWN")
    shown = store.get(m["id"])
    print("  mission :", short(shown), "| issue :", shown["outcome"]["status"])
    print("  service actuellement :", runtime.world.observe("sim-nas")["state"],
          "| limite affichée :", [l for l in shown["result"]["limits"] if "current health" in l])
    print("  contexte mémoire inchangé :", json.dumps(shown["context"], sort_keys=True) == context_before)
    pending = runtime.run(runtime.create_restart("nas")["id"])
    again = runtime.run(pending["id"])
    print("  proposition sans décision, relancée :", short(again),
          "| toujours la même empreinte :", again["proposal"]["sha256"] == pending["proposal"]["sha256"])


def probe_world_replaced():
    print("\n[8] Base de simulation remplacée après l'accord")
    directory, store, runtime = fresh()
    m = runtime.run(runtime.create_restart("nas")["id"])
    runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"], decision="approve",
                   actor="relecteur", reason="sonde G005")
    world = Path(directory) / "simulation.sqlite3"
    world.unlink()
    replaced = ActionRuntime(store)  # initializes a new world with a new identity
    print("  identité changée :", replaced.world.world_id != runtime.world.world_id)
    attempt("run avec la nouvelle base", lambda: replaced.run(m["id"]))
    print("  redémarrages dans la nouvelle base :", restarts(replaced))


def crash(directory, identity, boundary):
    def checkpoint(kind):
        if kind == boundary:
            os._exit(77)
    store = Store(directory)
    ActionRuntime(store, checkpoint=checkpoint).run(identity)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--crash":
        crash(sys.argv[2], sys.argv[3], sys.argv[4])
        raise SystemExit(0)
    print("Python", sys.version.split()[0], "|", sys.platform)
    for probe in (probe_boundaries, probe_copied_approval, probe_condition_changes, probe_concurrent_missions,
                  probe_cancel_and_revoke, probe_model_tampering, probe_after_success, probe_world_replaced):
        try:
            probe()
        except Exception:  # noqa: BLE001
            print("  SONDE EN ERREUR :")
            traceback.print_exc(file=sys.stdout)
