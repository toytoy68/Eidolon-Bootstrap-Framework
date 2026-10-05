# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : repro.py
# Description : Sondes synthétiques de la revue C-REV-001
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Sondes de revue C-REV-001 (Claude Code). Lecture seule sur le code Core.

Chaque sonde utilise un dossier d'état temporaire et des fournisseurs synthétiques.
Aucun réseau, aucun corpus utilisateur, aucun fichier du dépôt modifié.

Depuis eidolon-core/ :
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-c-rev-001/repro.py
"""
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import traceback

from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST, SyntheticMemory
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Policy, Registry, default_registry

HERE = Path(__file__).resolve()


# --- fournisseurs synthétiques, importables par les workers spawn -------------

@dataclass(frozen=True)
class RawModel:
    output: str
    model_id: str = "review-raw/1"

    def propose(self, request, context):
        return self.output


@dataclass(frozen=True)
class TwoItemMemory(SyntheticMemory):
    provider_id: str = "review-two-items/1"

    def recall(self, query):
        data = super().recall(query)
        second = json.loads(json.dumps(data["items"][0]))
        second.update(information_id="synthetic-note-b", content="Second extrait synthétique.")
        data["items"].append(second)
        return data


@dataclass(frozen=True)
class EmptyMemory:
    provider_id: str = "review-empty/1"

    def recall(self, query):
        return {"items": []}


@dataclass(frozen=True)
class SlowModel:
    model_id: str = "review-slow-model/1"

    def propose(self, request, context):
        time.sleep(10)


def big_tool(parameters, context):
    return {"blob": "x" * 600_000}


def big_verify(parameters, context, output):
    return isinstance(output, dict) and output.get("blob") == "x" * 600_000


def slow_tool(parameters, context):
    time.sleep(10)


def raising_tool(parameters, context):
    raise RuntimeError("erreur déterministe avant tout effet")


def marker_tool(parameters, context):
    # Simule un outil à effet : l'effet arrive 2 s après le lancement.
    time.sleep(2)
    Path(os.environ["REVIEW_MARKER"]).write_text("effet produit par pid %d" % os.getpid())
    return {"done": True}


def registry(**kwargs):
    return Registry([replace(default_registry().get("text.stats"), **kwargs)])


def plan(steps):
    return encode({"version": 1, "steps": steps})


def step(identity, ref="synthetic-note@1"):
    return {"id": identity, "tool": "text.stats", "parameters": {"reference": ref}}


def brief(m):
    return {k: m[k] for k in ("status", "phase", "progress", "error")}


def attempt(label, function):
    try:
        value = function()
        print(f"  {label}: retour normal -> {json.dumps(brief(value), ensure_ascii=False)}")
        return value
    except BaseException as exc:  # noqa: BLE001 - on veut voir l'exception brute
        print(f"  {label}: EXCEPTION NON GÉRÉE {type(exc).__name__}: {str(exc)[:110]}")
        return None


def fresh():
    directory = tempfile.mkdtemp(prefix="c-rev-001-")
    return directory, Store(directory)


# --- sondes -------------------------------------------------------------------

def probe_model_output(title, raw):
    print(f"\n[{title}]")
    _, store = fresh()
    runtime = Runtime(store, model=RawModel(raw))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run 1", lambda: runtime.run(identity))
    print("  état persisté :", json.dumps(brief(store.get(identity)), ensure_ascii=False))
    attempt("run 2 (reprise)", lambda: runtime.run(identity))
    print("  événements :", [e["kind"] for e in store.events(identity)])
    attempt("cancel", lambda: runtime.cancel(identity))


def probe_p1_nonfinite():
    raw = '{"version":1,"steps":[{"id":"s","tool":"text.stats","parameters":{"reference":1e999}}]}'
    probe_model_output("P1-a nombre non fini écrit 1e999 dans la sortie modèle", raw)


def probe_p1_surrogate():
    raw = '{"version":1,"steps":[{"id":"\\ud800","tool":"text.stats","parameters":{"reference":"synthetic-note@1"}}]}'
    probe_model_output("P1-b substitut UTF-16 isolé (\\ud800) dans un identifiant d'étape", raw)


def probe_p1_depth():
    print("\n[P1-c imbrication profonde des paramètres]")
    for depth in (200, 990, 5000, 31000):
        raw = ('{"version":1,"steps":[{"id":"s","tool":"text.stats","parameters":{"reference":'
               + "[" * depth + "]" * depth + "}}]}")
        _, store = fresh()
        runtime = Runtime(store, model=RawModel(raw))
        identity = runtime.create(DEMO_REQUEST)["id"]
        attempt(f"profondeur {depth}", lambda: runtime.run(identity))


def probe_p2_big_output():
    print("\n[P2-a deux sorties d'outil de 600 ko, chacune sous la borne de 1 Mo, toutes vérifiées]")
    _, store = fresh()
    runtime = Runtime(store, model=RawModel(plan([step("a"), step("b")])),
                      registry=registry(execute=big_tool, verify=big_verify))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run 1", lambda: runtime.run(identity))
    m = store.get(identity)
    print("  état persisté :", json.dumps(brief(m), ensure_ascii=False),
          "| appels :", [c["status"] for c in m["calls"]])
    attempt("run 2 (reprise)", lambda: runtime.run(identity))
    print("  événements :", [e["kind"] for e in store.events(identity)])
    attempt("cancel", lambda: runtime.cancel(identity))


def probe_p2_review_exit():
    print("\n[P2-b sortie d'une mission REVIEW_REQUIRED sans affirmer « sans effet »]")
    _, store = fresh()
    runtime = Runtime(store, registry=registry(execute=raising_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run (outil qui lève une exception)", lambda: runtime.run(identity))
    attempt("cancel", lambda: runtime.cancel(identity))
    attempt("run après cancel", lambda: runtime.run(identity))
    for decision in ("abandon", "effect-unknown"):
        try:
            runtime.reconcile(identity, decision=decision, actor="relecteur", reason="essai")
        except ValueError as exc:
            print(f"  reconcile --decision {decision}: refus -> {exc}")
    runtime.reconcile(identity, decision="no-effect", actor="relecteur",
                      reason="seule décision disponible pour pouvoir clore")
    attempt("run après no-effect (annulation déjà demandée)", lambda: runtime.run(identity))


def probe_p2_model_timeout():
    print("\n[P2-c délai modèle : état terminal, contrairement au délai mémoire]")
    _, store = fresh()
    runtime = Runtime(store, model=SlowModel(), limits=Limits(0.5))
    identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run", lambda: runtime.run(identity))
    attempt("run avec le modèle rétabli", lambda: Runtime(
        store, model=SlowModel(), limits=Limits(0.5)).run(identity))


def probe_p2_orphan():
    print("\n[P2-d parent tué pendant l'appel : l'enfant continue et produit son effet]")
    directory, store = fresh()
    marker = Path(directory) / "marker.txt"
    env = dict(os.environ, REVIEW_MARKER=str(marker))
    runtime = Runtime(store, registry=registry(execute=marker_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    driver = subprocess.Popen([sys.executable, str(HERE), "--drive", directory, identity], env=env)
    for _ in range(500):
        if store.get(identity)["phase"] == "EXECUTING":
            break
        time.sleep(0.01)
    time.sleep(0.6)  # laisser le worker démarrer
    os.kill(driver.pid, signal.SIGKILL)
    driver.wait()
    print("  parent tué (SIGKILL), marqueur présent tout de suite :", marker.exists())
    m = attempt("run de reprise", lambda: runtime.run(identity))
    runtime.reconcile(identity, decision="no-effect", actor="relecteur",
                      reason="aucun PID d'enfant dans le journal pour vérifier")
    print("  réconciliation no-effect acceptée ; marqueur présent à cet instant :", marker.exists())
    time.sleep(3)
    print("  3 s plus tard, marqueur présent :", marker.exists(),
          "|", marker.read_text() if marker.exists() else "")
    started = [e["detail"] for e in store.events(identity) if e["kind"] == "CALL_STARTED"]
    print("  détail journalisé de CALL_STARTED :", json.dumps(started, ensure_ascii=False))
    return m


def probe_p3_subset():
    print("\n[P3-a plan valide qui ne couvre pas l'objectif]")
    cases = {
        "1 extrait sur 2": (plan([step("only-first")]), DEMO_REQUEST),
        "même extrait répété 5 fois": (plan([step(f"dup-{i}") for i in range(5)]), DEMO_REQUEST),
        "demande sans rapport": (plan([step("s")]), "Vérifie que le service nginx du NAS répond."),
    }
    for label, (raw, request) in cases.items():
        _, store = fresh()
        runtime = Runtime(store, model=RawModel(raw), memory=TwoItemMemory())
        m = runtime.run(runtime.create(request)["id"])
        print(f"  {label}: {m['status']} {m['progress']} | résumé : {(m['result'] or {}).get('summary')}")


def probe_p3_empty_and_blocked():
    print("\n[P3-b codes de diagnostic]")
    _, store = fresh()
    runtime = Runtime(store, memory=EmptyMemory())
    m = runtime.run(runtime.create(DEMO_REQUEST)["id"])
    print("  mémoire vide :", json.dumps(brief(m), ensure_ascii=False))

    _, store = fresh()
    runtime = Runtime(store, model=RawModel(plan([{"id": "s", "tool": "shell", "parameters": {}}])))
    identity = runtime.create(DEMO_REQUEST)["id"]
    m = runtime.run(identity)
    print("  outil refusé :", json.dumps(brief(m), ensure_ascii=False))
    m = Runtime(store, model=RawModel(m["model_output"]),
                policy=Policy(allowed_tools=("text.stats", "shell"))).run(identity)
    print("  même mission, politique élargie :", json.dumps(brief(m), ensure_ascii=False))

    def cancel_at_verified(kind):
        if kind == "RESULT_VERIFIED":
            store2.request_cancel(identity2)
    _, store2 = fresh()
    runtime2 = Runtime(store2, checkpoint=cancel_at_verified)
    identity2 = runtime2.create(DEMO_REQUEST)["id"]
    m = runtime2.run(identity2)
    print("  annulation à la frontière du succès :", json.dumps(brief(m), ensure_ascii=False),
          "| dernier événement :", store2.events(identity2)[-1]["kind"])


def probe_p3_polling():
    print("\n[P3-c coût du sondage d'annulation pendant un appel]")
    _, store = fresh()
    runtime = Runtime(store, registry=registry(execute=slow_tool), limits=Limits(2.0))
    identity = runtime.create(DEMO_REQUEST)["id"]
    count = {"n": 0}
    original = store.get

    def counting(i):
        count["n"] += 1
        return original(i)
    store.get = counting
    started = time.monotonic()
    runtime.run(identity)
    print(f"  {count['n']} lectures SQLite complètes de la mission en {time.monotonic() - started:.2f} s"
          " (une connexion ouverte par lecture)")


def drive(directory, identity):
    Runtime(Store(directory), registry=registry(execute=marker_tool)).run(identity)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--drive":
        drive(sys.argv[2], sys.argv[3])
        raise SystemExit(0)
    print("Python", sys.version.split()[0], "|", sys.platform)
    for probe in (probe_p1_nonfinite, probe_p1_surrogate, probe_p1_depth, probe_p2_big_output,
                  probe_p2_review_exit, probe_p2_model_timeout, probe_p2_orphan, probe_p3_subset,
                  probe_p3_empty_and_blocked, probe_p3_polling):
        try:
            probe()
        except Exception:  # noqa: BLE001
            print("  SONDE EN ERREUR :")
            traceback.print_exc(file=sys.stdout)
