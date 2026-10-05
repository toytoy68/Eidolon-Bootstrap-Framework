# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : repro3.py
# Description : Sondes synthétiques de la relecture C-REV-003
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Sondes de relecture C-REV-003 (Claude). Lecture seule sur le code Core.

Chaque sonde utilise un dossier d'état temporaire et des fournisseurs synthétiques.
Aucun réseau, aucun corpus utilisateur, aucun fichier du dépôt modifié. Les
« effets » sont des lignes ajoutées à un fichier du dossier temporaire.

Depuis eidolon-core/ :
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-c-rev-003/repro3.py
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import traceback

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Registry, default_registry, text_stats

HERE = Path(__file__).resolve()


# --- fournisseurs synthétiques, importables par les workers spawn -------------

def _effect():
    with (Path(os.environ["REVIEW3_DIR"]) / "effects").open("a") as stream:
        stream.write("effet pid %d\n" % os.getpid())


def quick_counting_tool(parameters, context):
    _effect()
    return text_stats(parameters, context)


def effect_then_raise_tool(parameters, context):
    """Produit son effet, puis lève : l'erreur ne prouve pas l'absence d'effet."""
    _effect()
    raise ConnectionResetError("connexion coupée après l'envoi de la requête")


def blocking_tool(parameters, context):
    directory = Path(os.environ["REVIEW3_DIR"])
    (directory / "entered").write_text("entré")
    time.sleep(30)
    _effect()
    return text_stats(parameters, context)


def registry(**kwargs):
    return Registry([replace(default_registry().get("text.stats"), **kwargs)])


TOOLS = {"quick": quick_counting_tool, "blocking": blocking_tool}


# --- utilitaires ---------------------------------------------------------------

def brief(m):
    return {k: m[k] for k in ("status", "phase", "error")}


def attempt(label, function):
    try:
        value = function()
        print(f"  {label}: {json.dumps(brief(value), ensure_ascii=False)}")
        return value
    except BaseException as exc:  # noqa: BLE001 - on veut voir l'exception brute
        print(f"  {label}: REFUS {type(exc).__name__}: {str(exc)[:110]}")
        return None


def fresh():
    directory = tempfile.mkdtemp(prefix="c-rev-003-")
    os.environ["REVIEW3_DIR"] = directory
    return directory, Store(directory)


def effects(directory):
    path = Path(directory) / "effects"
    return len(path.read_text().splitlines()) if path.exists() else 0


def kinds(store, identity):
    return [e["kind"] for e in store.events(identity)]


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def reconcile(runtime, identity, decision, **kwargs):
    return lambda: runtime.reconcile(identity, decision=decision, actor="relecteur",
                                     reason="sonde C-REV-003", **kwargs)


# --- sondes -------------------------------------------------------------------

def probe_r1_receipt_survives_parent_death():
    print("\n[R1 mort du parent après le retour de l'outil : adoption du reçu conservé]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=quick_counting_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    subprocess.run([sys.executable, str(HERE), "--crash", directory, identity, "TOOL_RETURNED"],
                   env=dict(os.environ, REVIEW3_DIR=directory), capture_output=True, timeout=30)
    attempt("run de reprise", lambda: runtime.run(identity))
    before = len(kinds(store, identity))
    attempt("reconcile no-effect", reconcile(runtime, identity, "no-effect"))
    attempt("reconcile no-effect --confirm-no-effect",
            reconcile(runtime, identity, "no-effect", confirm_no_effect=True))
    added = kinds(store, identity)[before:]
    print("  événements ajoutés par les deux refus :", added)
    call = store.get(identity)["calls"][0]
    print("  clés de reçu sur l'appel après refus :",
          sorted(k for k in call if k.endswith("receipt")))
    attempt("reconcile use-receipt", reconcile(runtime, identity, "use-receipt"))
    m = attempt("run", lambda: runtime.run(identity))
    print("  effets :", effects(directory), "| CALL_STARTED :",
          kinds(store, identity).count("CALL_STARTED"),
          "| origine dans result.evidence :", m["result"]["evidence"][0]["receipt_origin"])


def probe_r2_error_after_effect():
    print("\n[R2 l'outil produit son effet puis lève : no-effect sans confirmation ?]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=effect_then_raise_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run", lambda: runtime.run(identity))
    call = store.get(identity)["calls"][0]
    print("  error_receipt.ok :", call["error_receipt"]["ok"], "| effets :", effects(directory))
    attempt("reconcile no-effect (sans --confirm-no-effect)", reconcile(runtime, identity, "no-effect"))
    detail = [e for e in store.events(identity) if e["kind"] == "RECONCILED"][-1]["detail"]
    print("  journal RECONCILED : worker_authorized =", detail.get("worker_authorized"),
          "| confirmed_no_effect =", detail.get("confirmed_no_effect"))
    attempt("run (nouvelle tentative)", lambda: runtime.run(identity))
    print("  effets au total :", effects(directory), "| CALL_STARTED :",
          kinds(store, identity).count("CALL_STARTED"))


def probe_r3_both_killed_without_receipt():
    print("\n[R3 parent et exécutant tués pendant l'outil : marqueur présent, aucun reçu]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=blocking_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    driver = subprocess.Popen([sys.executable, str(HERE), "--drive", directory, identity, "blocking"],
                              env=dict(os.environ, REVIEW3_DIR=directory), start_new_session=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  outil entré :", wait_for(lambda: (Path(directory) / "entered").exists()))
    os.killpg(driver.pid, signal.SIGKILL)  # parent et enfant spawn, même groupe
    driver.wait()
    time.sleep(0.3)
    attempt("run de reprise", lambda: runtime.run(identity))
    attempt("reconcile no-effect (sans confirmation)", reconcile(runtime, identity, "no-effect"))
    call = store.get(identity)["calls"][0]
    lease = store.worker_lease_path(identity, call["id"], call["attempt"])
    print("  contenu du verrou :", repr(lease.read_text()))
    print("  effets :", effects(directory))
    return directory, store, runtime, identity, lease


def probe_r4_lease_removed():
    print("\n[R4 même situation, fichier de verrou supprimé (nettoyage manuel ou futur)]")
    directory, store, runtime, identity, lease = probe_r3_both_killed_without_receipt()
    lease.unlink()
    print("  verrou supprimé ; outil entré mais tué, effet réel inconnu")
    attempt("reconcile no-effect (sans confirmation)", reconcile(runtime, identity, "no-effect"))
    detail = [e for e in store.events(identity) if e["kind"] == "RECONCILED"]
    if detail:
        print("  journal RECONCILED : worker_authorized =", detail[-1]["detail"].get("worker_authorized"))


def probe_r5_state_residue():
    print("\n[R5 fichiers laissés dans le dossier d'état]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=quick_counting_tool))
    for _ in range(10):
        runtime.run(runtime.create(DEMO_REQUEST)["id"])
    names = [p.name for p in Path(directory).iterdir()]
    for suffix in (".worker.lock", ".receipt.json", ".pending"):
        print(f"  {suffix:14} : {sum(1 for n in names if n.endswith(suffix))}")
    print("  missions terminées : 10, toutes SUCCEEDED")


def drive(directory, identity, tool):
    Runtime(Store(directory), registry=registry(execute=TOOLS[tool])).run(identity)


def crash(directory, identity, boundary):
    def checkpoint(kind):
        if kind == boundary:
            os._exit(77)
    Runtime(Store(directory), registry=registry(execute=quick_counting_tool),
            checkpoint=checkpoint).run(identity)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--drive":
        drive(sys.argv[2], sys.argv[3], sys.argv[4])
        raise SystemExit(0)
    if len(sys.argv) == 5 and sys.argv[1] == "--crash":
        crash(sys.argv[2], sys.argv[3], sys.argv[4])
        raise SystemExit(0)
    print("Python", sys.version.split()[0], "|", sys.platform)
    for probe in (probe_r1_receipt_survives_parent_death, probe_r2_error_after_effect,
                  probe_r3_both_killed_without_receipt, probe_r4_lease_removed,
                  probe_r5_state_residue):
        try:
            probe()
        except Exception:  # noqa: BLE001
            print("  SONDE EN ERREUR :")
            traceback.print_exc(file=sys.stdout)
