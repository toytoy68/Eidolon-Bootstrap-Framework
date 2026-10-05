# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes.py
# Description : Sondes synthétiques de la contre-revue C-TASK-G001
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Probes for c63c4d1 (Claude). Read-only on Core code, temporary state only.

From eidolon-core/:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-g001/probes.py
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
from eidolon_core.ollama_model import OllamaConfig, OllamaModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.targets import Catalog
from eidolon_core.tools import Registry, default_registry, text_stats

HERE = Path(__file__).resolve()


def _effect():
    with (Path(os.environ["G001_DIR"]) / "effects").open("a") as stream:
        stream.write("effet\n")


def effect_then_raise_tool(parameters, context):
    _effect()
    raise ConnectionResetError("connexion coupée après l'envoi")


def blocking_tool(parameters, context):
    (Path(os.environ["G001_DIR"]) / "entered").write_text("1")
    time.sleep(30)
    _effect()
    return text_stats(parameters, context)


def registry(execute):
    return Registry([replace(default_registry().get("text.stats"), execute=execute)])


def fresh():
    directory = tempfile.mkdtemp(prefix="claude-g001-")
    os.environ["G001_DIR"] = directory
    return directory, Store(directory)


def effects(directory):
    path = Path(directory) / "effects"
    return len(path.read_text().splitlines()) if path.exists() else 0


def attempt(label, function):
    try:
        m = function()
        print(f"  {label}: {m['status']} / {(m.get('error') or {}).get('code')}")
        return m
    except BaseException as exc:  # noqa: BLE001
        print(f"  {label}: REFUS {type(exc).__name__}: {str(exc)[:100]}")
        return None


def reconcile(runtime, identity, decision, **kwargs):
    return lambda: runtime.reconcile(identity, decision=decision, actor="relecteur",
                                     reason="sonde G001", **kwargs)


def probe_n09():
    print("\n[N-09 effet puis exception : confirmation exigée ?]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(effect_then_raise_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run", lambda: runtime.run(identity))
    attempt("no-effect sans confirmation", reconcile(runtime, identity, "no-effect"))
    print("  effets :", effects(directory), "| CALL_STARTED :",
          [e["kind"] for e in store.events(identity)].count("CALL_STARTED"))
    attempt("no-effect --confirm-no-effect", reconcile(runtime, identity, "no-effect", confirm_no_effect=True))
    call = store.get(identity)["calls"][0]
    history = call.get("attempt_history", [])
    print("  historique conservé :", len(history), "tentative(s) ;",
          "reçu d'erreur archivé :", bool(history and history[0].get("error_receipt")),
          "| confirmation journalisée :", history and history[0]["reconciliation"].get("confirmed_no_effect"))


def probe_n10():
    print("\n[N-10 verrou supprimé après WORKER_SPAWNED]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(blocking_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    driver = subprocess.Popen([sys.executable, str(HERE), "--drive", directory, identity],
                              env=dict(os.environ, G001_DIR=directory), start_new_session=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while not (Path(directory) / "entered").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    os.killpg(driver.pid, signal.SIGKILL)
    driver.wait()
    time.sleep(0.3)
    runtime.run(identity)
    call = store.get(identity)["calls"][0]
    lease = store.worker_lease_path(identity, call["id"], call["attempt"])
    print("  worker journalisé :", call.get("worker") is not None, "| verrou :", repr(lease.read_text()))
    lease.unlink()
    attempt("no-effect --confirm-no-effect (verrou absent)",
            reconcile(runtime, identity, "no-effect", confirm_no_effect=True))
    print("  verrou recréé par la tentative :", lease.exists())
    attempt("abandon", reconcile(runtime, identity, "abandon"))
    print("  effets :", effects(directory))


def probe_catalog_copies():
    print("\n[Catalogue : les objets rendus sont-ils détachés ?]")
    config = {"schema": "targets/1", "targets": [
        {"id": "nas-main", "name": "NAS", "kind": "nas_storage",
         "capabilities": [{"name": "files.read", "effect": "local_read", "scope": {"roots": ["archives"]}}]}]}
    catalog = Catalog.from_config(config)
    before = catalog.fingerprint()
    config["targets"][0]["capabilities"][0]["scope"]["roots"].append("source modifiée")
    catalog.manifest()["targets"][0]["capabilities"][0]["scope"]["roots"].append("manifeste")
    catalog.get("nas-main").capabilities[0].scope["roots"].append("get")
    catalog.lookup("nas-main", "files.read").capability.scope["roots"].append("lookup")
    print("  empreinte inchangée :", catalog.fingerprint() == before,
          "| portée :", catalog.get("nas-main").capabilities[0].scope)
    target = catalog.get("nas-main")
    try:
        Catalog([target, target])
        print("  constructeur direct, doublon : ACCEPTÉ")
    except Exception as exc:  # noqa: BLE001
        print("  constructeur direct, doublon : refusé,", type(exc).__name__)


def probe_ollama_options():
    print("\n[Options Ollama : immuables et reflétées par model_id ?]")
    source = {"temperature": 0, "seed": 7}
    config = OllamaConfig("http://127.0.0.1:11434", "synthetic:1b", source)
    model = OllamaModel(config)
    before = model.model_id
    source["temperature"] = 1
    print("  source modifiée → options :", dict(config.options), "| model_id inchangé :", model.model_id == before)
    try:
        config.options["temperature"] = 1  # type: ignore[index]
        print("  écriture directe : ACCEPTÉE")
    except TypeError:
        print("  écriture directe : refusée (TypeError)")
    model.config = replace(config, options={"temperature": 0.5, "seed": 7})
    print("  remplacement explicite → model_id change :", model.model_id != before)
    import pickle
    clone = pickle.loads(pickle.dumps(model.propose)).__self__
    print("  après pickle (spawn) : options", dict(clone.config.options), "| model_id identique :",
          clone.model_id == model.model_id)


def probe_objective_tamper():
    print("\n[C-001a : une demande hors catalogue peut-elle atteindre le modèle ou un outil ?]")
    directory, store = fresh()
    runtime = Runtime(store)
    identity = runtime.create(DEMO_REQUEST)["id"]
    m = runtime.run(identity)
    print("  mission normale :", m["status"], "/", m["outcome"]["status"])
    m2 = runtime.create("Résume mes documents personnels.")
    print("  demande hors catalogue (create) : objectif", m2["objective"]["kind"],
          "| issue", m2["outcome"]["status"])
    m2 = runtime.run(m2["id"])
    print("  demande hors catalogue (run) :", m2["status"], "/", m2["outcome"]["status"],
          "| appels :", len(m2["calls"]))


def drive(directory, identity):
    Runtime(Store(directory), registry=registry(blocking_tool)).run(identity)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--drive":
        drive(sys.argv[2], sys.argv[3])
        raise SystemExit(0)
    print("Python", sys.version.split()[0], "|", sys.platform)
    for probe in (probe_n09, probe_n10, probe_catalog_copies, probe_ollama_options, probe_objective_tamper):
        try:
            probe()
        except Exception:  # noqa: BLE001
            print("  SONDE EN ERREUR :")
            traceback.print_exc(file=sys.stdout)
