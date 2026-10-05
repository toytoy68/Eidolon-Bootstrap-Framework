# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : repro2.py
# Description : Sondes synthétiques de la contre-revue C-REV-002
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Sondes de contre-revue C-REV-002 (Claude). Lecture seule sur le code Core.

Chaque sonde utilise un dossier d'état temporaire et des fournisseurs synthétiques.
Aucun réseau, aucun corpus utilisateur, aucun fichier du dépôt modifié. Les
« effets » sont des lignes ajoutées à un fichier du dossier temporaire.

Depuis eidolon-core/ :
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-05/claude-c-rev-002/repro2.py
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

from eidolon_core.contracts import ContractError, digest, encode, parse_plan
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.tools import Registry, default_registry, text_stats

HERE = Path(__file__).resolve()


# --- fournisseurs synthétiques, importables par les workers spawn -------------

@dataclass(frozen=True)
class RawModel:
    output: str
    model_id: str = "review2-raw/1"

    def propose(self, request, context):
        return self.output


def raising_tool(parameters, context):
    raise ConnectionRefusedError("refus de connexion synthétique, avant tout effet")


def counting_tool(parameters, context):
    """Outil « à effet » : attend le feu vert, puis ajoute une ligne au compteur."""
    directory = Path(os.environ["REVIEW2_DIR"])
    (directory / "entered").write_text("entré")
    deadline = time.monotonic() + 8
    while not (directory / "release").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    with (directory / "effects").open("a") as stream:
        stream.write("effet pid %d\n" % os.getpid())
    return text_stats(parameters, context)


def quick_counting_tool(parameters, context):
    with (Path(os.environ["REVIEW2_DIR"]) / "effects").open("a") as stream:
        stream.write("effet pid %d\n" % os.getpid())
    return text_stats(parameters, context)


def big_tool(parameters, context):
    return {"blob": "x" * 600_000}


def big_verify(parameters, context, output):
    return isinstance(output, dict) and output.get("blob") == "x" * 600_000


def registry(**kwargs):
    return Registry([replace(default_registry().get("text.stats"), **kwargs)])


def step(identity, ref="synthetic-note@1"):
    return {"id": identity, "tool": "text.stats", "parameters": {"reference": ref}}


def plan(steps):
    return encode({"version": 1, "steps": steps})


def brief(m):
    return {k: m[k] for k in ("status", "phase", "progress", "error")}


def show(label, m):
    print(f"  {label}: {json.dumps(brief(m), ensure_ascii=False)}")


def attempt(label, function):
    try:
        value = function()
        if isinstance(value, dict) and "status" in value:
            show(label, value)
        else:
            print(f"  {label}: retour {value!r}")
        return value
    except BaseException as exc:  # noqa: BLE001 - on veut voir l'exception brute
        print(f"  {label}: REFUS/EXCEPTION {type(exc).__name__}: {str(exc)[:120]}")
        return None


def fresh():
    directory = tempfile.mkdtemp(prefix="c-rev-002-")
    os.environ["REVIEW2_DIR"] = directory
    return directory, Store(directory)


def effects(directory):
    path = Path(directory) / "effects"
    return len(path.read_text().splitlines()) if path.exists() else 0


def kinds(store, identity):
    return [e["kind"] for e in store.events(identity)]


def wait_for(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def lease_free(store, identity, call):
    try:
        with store.worker_quiescent(identity, call):
            return True
    except Busy:
        return False


# --- sondes -------------------------------------------------------------------

def probe_n01_tool_error_dead_end():
    print("\n[N-01 erreur d'outil rendue dans les temps : quelles issues restent ?]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=raising_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    m = attempt("run (l'outil lève ConnectionRefusedError)", lambda: runtime.run(identity))
    call = m["calls"][0]
    print("  late_receipt :", json.dumps(call.get("late_receipt"), ensure_ascii=False))
    print("  événements :", kinds(store, identity))
    attempt("reconcile no-effect", lambda: runtime.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="échec avant tout effet"))
    print("  issues restantes : observed-result (il n'y a aucune sortie à fournir) ou abandon")
    attempt("reconcile abandon", lambda: runtime.reconcile(
        identity, decision="abandon", actor="relecteur", reason="seule issue sans inventer de sortie"))


def probe_n02_finished_orphan_double_effect():
    print("\n[N-02 orphelin terminé : no-effect accepté, puis second effet]")
    directory, store = fresh()
    transit = Path(directory) / "transit"
    transit.mkdir()
    env = dict(os.environ, REVIEW2_DIR=directory, TMPDIR=str(transit))
    runtime = Runtime(store, registry=registry(execute=counting_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    driver = subprocess.Popen([sys.executable, str(HERE), "--drive", directory, identity], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  outil entré (exécution autorisée) :", wait_for(lambda: (Path(directory) / "entered").exists()))
    os.kill(driver.pid, signal.SIGKILL)
    driver.wait()
    m = attempt("run de reprise après SIGKILL du parent", lambda: runtime.run(identity))
    call = m["calls"][0]
    attempt("reconcile no-effect pendant que l'orphelin vit", lambda: runtime.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="essai pendant l'exécution"))
    (Path(directory) / "release").touch()
    print("  verrou libéré après la fin de l'orphelin :", wait_for(lambda: lease_free(store, identity, call)))
    print("  effets produits à cet instant :", effects(directory))
    receipts = sorted(transit.glob("eidolon-worker-*/receipt.json"))
    for path in receipts:
        envelope = json.loads(path.read_text())
        print(f"  reçu de transit resté sur disque : ok={envelope['ok']} ({path.stat().st_size} octets)")
    stored = store.get(identity)["calls"][0]
    print("  late_receipt en base :", stored.get("late_receipt"), "| worker journalisé :", bool(stored.get("worker")))
    attempt("reconcile no-effect après la fin de l'orphelin", lambda: runtime.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="verrou libre, rien en base"))
    attempt("run (nouvelle tentative)", lambda: runtime.run(identity))
    print("  effets produits au total :", effects(directory),
          "| CALL_STARTED :", kinds(store, identity).count("CALL_STARTED"))


def probe_n03_cancel_during_handshake():
    print("\n[N-03 annulation entre WORKER_SPAWNED et l'autorisation : l'outil n'a pas pu tourner]")
    directory, store = fresh()
    holder = {}

    def cancel_at_spawn(kind):
        if kind == "WORKER_SPAWNED":
            store.request_cancel(holder["id"])
    runtime = Runtime(store, registry=registry(execute=quick_counting_tool), checkpoint=cancel_at_spawn)
    holder["id"] = identity = runtime.create(DEMO_REQUEST)["id"]
    attempt("run", lambda: runtime.run(identity))
    print("  effets produits :", effects(directory), "| événements :", kinds(store, identity)[-4:])
    plain = Runtime(store, registry=registry(execute=quick_counting_tool))
    attempt("reconcile no-effect", lambda: plain.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="jamais autorisé"))
    attempt("run", lambda: plain.run(identity))


def probe_n04_persistence_failure_at_spawn():
    print("\n[Point 1 : échec de persistance de WORKER_SPAWNED]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=quick_counting_tool))
    identity = runtime.create(DEMO_REQUEST)["id"]
    original = store.save

    def failing(mission, kind, detail=None):
        if kind == "WORKER_SPAWNED":
            raise OSError("panne synthétique de persistance")
        return original(mission, kind, detail)
    store.save = failing
    m = attempt("run", lambda: runtime.run(identity))
    store.save = original
    print("  effets produits :", effects(directory), "| worker en base :", m["calls"][0].get("worker"),
          "| événements :", kinds(store, identity)[-3:])
    attempt("reconcile no-effect", lambda: runtime.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="lancement jamais journalisé"))
    attempt("run", lambda: runtime.run(identity))
    print("  effets produits au total :", effects(directory),
          "| CALL_STARTED :", kinds(store, identity).count("CALL_STARTED"))


def probe_n05_parent_dies_at_boundaries():
    print("\n[Point 1 : mort du parent à chaque frontière (os._exit dans le point de contrôle)]")
    for boundary in ("CALL_STARTED", "WORKER_SPAWNED", "TOOL_RETURNED", "RESULT_SAVED"):
        directory, store = fresh()
        env = dict(os.environ, REVIEW2_DIR=directory)
        runtime = Runtime(store, registry=registry(execute=quick_counting_tool))
        identity = runtime.create(DEMO_REQUEST)["id"]
        driver = subprocess.run([sys.executable, str(HERE), "--crash", directory, identity, boundary],
                                env=env, capture_output=True, text=True, timeout=20)
        time.sleep(0.5)  # laisser un éventuel enfant constater la fermeture du tube
        m = runtime.run(identity)
        call = m["calls"][0]
        free = lease_free(store, identity, call) if m["status"] == "REVIEW_REQUIRED" else None
        print(f"  mort à {boundary} (code {driver.returncode}) -> {m['status']}/{m['phase']}"
              f" | effets {effects(directory)} | verrou libre {free}"
              f" | CALL_STARTED {kinds(store, identity).count('CALL_STARTED')}")


def probe_n06_depth_boundary():
    print("\n[N-04 imbrication : un plan accepté par parse_plan peut-il échouer à l'enregistrement ?]")

    def raw_for(depth):
        return ('{"version":1,"steps":[{"id":"s","tool":"text.stats","parameters":{"reference":'
                + "[" * depth + "]" * depth + "}}]}")

    def accepted(depth):
        try:
            parse_plan(raw_for(depth))
            return True
        except ContractError:
            return False
    low, high = 1, 31_000  # 31 000 niveaux restent sous la borne de 64 000 octets
    if accepted(high):
        print("  parse_plan accepte encore 31 000 niveaux ; pas de seuil à sonder ici")
        return
    while high - low > 1:
        middle = (low + high) // 2
        low, high = (middle, high) if accepted(middle) else (low, middle)
    print(f"  plus grande profondeur acceptée par parse_plan sur cet interpréteur : {low}")
    seen = {}
    for depth in range(low - 14, low + 2):
        _, store = fresh()
        runtime = Runtime(store, model=RawModel(raw_for(depth)))
        identity = runtime.create(DEMO_REQUEST)["id"]
        try:
            m = runtime.run(identity)
            again = runtime.run(identity)
            outcome = (f"{m['status']}/{m['phase']}/{(m['error'] or {}).get('code')}"
                       f" ({(m['error'] or {}).get('message')}) ; reprise -> {again['status']}/"
                       f"{(again['error'] or {}).get('code')} ; INTERNAL_ERROR journalisés : "
                       f"{kinds(store, identity).count('INTERNAL_ERROR')}")
        except BaseException as exc:  # noqa: BLE001
            outcome = "EXCEPTION " + type(exc).__name__
        seen.setdefault(outcome, []).append(depth)
    for outcome, depths in seen.items():
        print(f"  profondeurs {depths[0]}…{depths[-1]} ({len(depths)}) : {outcome}")


def probe_n07_evidence_and_sizes():
    print("\n[Point 3 : références de result.evidence, origine humaine, tailles]")
    # (a) résultat fourni par un humain : visible dans l'appel, pas dans la preuve finale
    directory, store = fresh()
    slow = Runtime(store, registry=registry(execute=counting_tool), limits=Limits(0.6))
    identity = slow.create(DEMO_REQUEST)["id"]
    m = slow.run(identity)
    output = text_stats(m["plan"]["steps"][0]["parameters"], m["context"])
    slow.reconcile(identity, decision="observed-result", actor="relecteur",
                   reason="sortie recalculée à la main", output=output)
    m = slow.run(identity)
    print("  après observed-result :", m["status"], "| receipt_origin de l'appel :", m["calls"][0]["receipt_origin"])
    print("  result.evidence :", json.dumps(m["result"]["evidence"], ensure_ascii=False))
    # (b) taille du corps de mission et coût des enregistrements avec cinq sorties de 600 ko
    directory, store = fresh()
    runtime = Runtime(store, model=RawModel(plan([step(str(i)) for i in range(5)])),
                      registry=registry(execute=big_tool, verify=big_verify))
    identity = runtime.create(DEMO_REQUEST)["id"]
    written = {"saves": 0, "bytes": 0}
    original = store.save

    def measuring(mission, kind, detail=None):
        original(mission, kind, detail)
        written["saves"] += 1
        written["bytes"] += len(encode(mission).encode("utf-8"))
    store.save = measuring
    started = time.monotonic()
    m = runtime.run(identity)
    elapsed = time.monotonic() - started
    store.save = original
    body = len(encode(store.get(identity)).encode("utf-8"))
    print(f"  5 x 600 ko : {m['status']} en {elapsed:.1f} s | corps final {body / 1e6:.2f} Mo"
          f" | {written['saves']} enregistrements, {written['bytes'] / 1e6:.1f} Mo réécrits"
          f" | résultat {len(encode(m['result']))} octets")
    started = time.monotonic()
    for _ in range(20):
        store.get(identity)
    print(f"  lecture complète de la mission : {(time.monotonic() - started) / 20 * 1000:.1f} ms en moyenne")


def probe_n08_late_receipt_digest():
    print("\n[Point 2 : reçu tardif et sortie fournie par l'humain]")
    # Même couture que les tests de Codex : le reçu de production est écrit,
    # puis le processus reste vivant jusqu'à l'échéance.
    from unittest.mock import patch
    from tests.support import receipt_then_wait
    directory, store = fresh()
    marker = Path(directory) / "receipt-ready"
    runtime = Runtime(store, limits=Limits(1.0))
    identity = runtime.create(DEMO_REQUEST)["id"]
    with patch.dict(os.environ, {"EIDOLON_TEST_RECEIPT_READY": str(marker)}), \
            patch("eidolon_core.worker._child", receipt_then_wait):
        m = attempt("run (reçu écrit, puis délai dépassé)", lambda: runtime.run(identity))
    call = m["calls"][0]
    if call.get("late_receipt") is None:
        print("  pas de reçu tardif obtenu sur cette machine ; sonde sans conclusion")
        return
    value = call["late_receipt"]["value"]
    print("  late_receipt.ok :", call["late_receipt"]["ok"], "| résultat de mission :", m["result"])
    attempt("reconcile no-effect", lambda: runtime.reconcile(
        identity, decision="no-effect", actor="relecteur", reason="essai d'effacement du reçu"))
    forged = dict(value, characters=value["characters"] + 1)
    attempt("reconcile observed-result avec une sortie DIFFÉRENTE du reçu conservé", lambda: runtime.reconcile(
        identity, decision="observed-result", actor="relecteur", reason="sortie retapée à la main", output=forged))
    stored = store.get(identity)["calls"][0]
    print("  output_sha256 (valeur fournie)   :", stored["output_sha256"][:16], "…")
    print("  empreinte de la valeur du reçu   :", digest(value)[:16], "…")
    print("  late_receipt_sha256 (enveloppe)  :", stored["late_receipt_sha256"][:16], "…")
    print("  détail journalisé de RECONCILED  :", sorted(store.events(identity)[-1]["detail"]))
    attempt("run (le vérificateur de text.stats recalcule et tranche)", lambda: runtime.run(identity))


def probe_n10_child_reset():
    print("\n[N-05 parent disparu sans avoir lu « ready » : exception côté enfant]")
    import multiprocessing
    import threading
    from eidolon_core.worker import _child
    parent, child = multiprocessing.Pipe(duplex=True)
    directory = tempfile.mkdtemp(prefix="c-rev-002-")
    outcome = {}

    def target():
        try:
            _child(child, quick_counting_tool, ({}, {}), str(Path(directory) / "receipt.json"), None)
            outcome["fin"] = "retour normal"
        except BaseException as exc:  # noqa: BLE001
            outcome["fin"] = f"exception non interceptée {type(exc).__name__}"
    os.environ["REVIEW2_DIR"] = directory
    thread = threading.Thread(target=target)
    thread.start()
    time.sleep(0.3)   # l'enfant a envoyé « ready » et attend « execute »
    parent.close()    # le parent disparaît sans lire
    thread.join(5)
    print("  fin de _child :", outcome.get("fin"), "| outil exécuté :", effects(directory) > 0)


def probe_n09_handshake_cost():
    print("\n[Coût du lancement d'un exécutant (spawn + poignée de main + SQLite)]")
    directory, store = fresh()
    runtime = Runtime(store, registry=registry(execute=quick_counting_tool))
    samples = []
    for _ in range(5):
        identity = runtime.create(DEMO_REQUEST)["id"]
        started = time.monotonic()
        m = runtime.run(identity)
        samples.append(time.monotonic() - started)
        assert m["status"] == "SUCCEEDED"
    print("  mission complète (4 exécutants : rappel, modèle, outil, vérification), 5 essais :",
          " ".join(f"{s:.2f}s" for s in samples))
    for limit in (0.05, 0.1, 0.2, 0.4):
        fast = Runtime(Store(tempfile.mkdtemp(prefix="c-rev-002-")), limits=Limits(limit))
        m = fast.run(fast.create(DEMO_REQUEST)["id"])
        print(f"  délai par appel {limit:.2f} s -> {m['status']}/{(m['error'] or {}).get('code')}")


def drive(directory, identity):
    Runtime(Store(directory), registry=registry(execute=counting_tool)).run(identity)


def crash(directory, identity, boundary):
    def checkpoint(kind):
        if kind == boundary:
            os._exit(77)
    Runtime(Store(directory), registry=registry(execute=quick_counting_tool), checkpoint=checkpoint).run(identity)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--drive":
        drive(sys.argv[2], sys.argv[3])
        raise SystemExit(0)
    if len(sys.argv) == 5 and sys.argv[1] == "--crash":
        crash(sys.argv[2], sys.argv[3], sys.argv[4])
        raise SystemExit(0)
    print("Python", sys.version.split()[0], "|", sys.platform)
    for probe in (probe_n01_tool_error_dead_end, probe_n02_finished_orphan_double_effect,
                  probe_n03_cancel_during_handshake, probe_n04_persistence_failure_at_spawn,
                  probe_n05_parent_dies_at_boundaries, probe_n06_depth_boundary,
                  probe_n07_evidence_and_sizes, probe_n08_late_receipt_digest, probe_n10_child_reset,
                  probe_n09_handshake_cost):
        try:
            probe()
        except Exception:  # noqa: BLE001
            print("  SONDE EN ERREUR :")
            traceback.print_exc(file=sys.stdout)
