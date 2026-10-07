# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_fixture.py
# Description : Jeu de recette synthétique isolé pour la consultation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Create a new Linux-only fixture; never open or repair an existing state.

The existing parent and its ancestors must be trusted. Runtime defaults are
synthetic and no external adapter can be configured here. The `state`
directory remains blocked to the read API until all checks, token and manifest
succeed. Its stable path preserves runtime bindings.
A failure leaves the newly owned directory for inspection, never recursive
cleanup. This is not a backup, installer or power-loss durability guarantee.
"""
import argparse
import json
import os
from pathlib import Path

from .access_token import create as create_token
from .actions import ActionRuntime
from .client_sync import ClientSync
from .commands import CancelCommands, DecisionCommands
from .memory import DEMO_REQUEST
from .presentation import header, message
from .receipt_lookup import lookup
from .runtime import Runtime
from .store import Store

PROTOCOL = "eidolon-beta-fixture/1"
QUERY_FIELDS = ("store_id", "client_id", "command_key", "mission_id")
TEXT = {
    "FIXTURE_READY": "Six missions synthétiques vérifiées ; état de consultation prêt.",
    "RESEARCH_FIXTURE_READY": "Trois recherches synthétiques et copies d'archives vérifiées ; aucune rotation active.",
    "INVALID_PROFILE": "Profil de recette inconnu ; aucune destination créée.",
    "DESTINATION_EXISTS": "La destination existe déjà ; aucun contenu modifié.",
    "DESTINATION_UNAVAILABLE": "Choisir un nouveau dossier dans un parent existant de confiance.",
    "PREPARATION_FAILED": "Préparation incomplète ; conserver le dossier pour inspection et choisir une nouvelle destination.",
}


def _populate(directory):
    store = Store(directory)
    runtime = Runtime(store)
    actions = ActionRuntime(store)
    scenarios, queries = [], []

    def add(role, mission, expected_status, proposal_status=None, cancel=False):
        current = store.get(mission["id"])
        projected = ClientSync(store).snapshot(mission["id"])["snapshot"]["mission"]
        if current["status"] != expected_status or projected["cancel_requested"] is not cancel:
            raise ValueError("fixture assertion failed")
        if proposal_status is not None and current["proposal"]["status"] != proposal_status:
            raise ValueError("fixture proposal assertion failed")
        scenarios.append({"role": role, "mission_id": mission["id"],
                          "expected_status": expected_status, "cancel_requested": cancel,
                          "proposal_status": proposal_status})

    completed = runtime.run(runtime.create(DEMO_REQUEST)["id"])
    add("text_completed", completed, "SUCCEEDED")
    fresh = runtime.create(DEMO_REQUEST)
    add("not_started", fresh, "NEW")
    store_id = ClientSync(store).snapshot(fresh["id"])["store_id"]
    pending = actions.run(actions.create_restart("nas")["id"])
    add("approval_pending", pending, "BLOCKED", "PENDING")
    requested = runtime.create(DEMO_REQUEST)
    command = dict(protocol="eidolon-cancel-command/1", store_id=store_id,
                   client_id="beta-fixture", command_key="cancel-requested",
                   mission_id=requested["id"], actor="Recette synthétique",
                   reason="Demande enregistrée sans reprise du runtime")
    CancelCommands(store).submit(command)
    queries.append({key: command[key] for key in QUERY_FIELDS})
    add("cancel_requested", requested, "NEW", cancel=True)
    cancelled = runtime.cancel(runtime.create(DEMO_REQUEST)["id"])
    add("cancelled", cancelled, "CANCELLED", cancel=True)
    revoked = actions.run(actions.create_restart("nas")["id"])
    for decision in ("approve", "revoke"):
        current = store.get(revoked["id"])
        command = dict(protocol="eidolon-decision-command/1", store_id=store_id,
                       client_id="beta-fixture", command_key="historical-" + decision,
                       mission_id=current["id"], expected_revision=current["revision"],
                       proposal_sha256=current["proposal"]["sha256"], decision=decision,
                       actor="Recette synthétique", reason="Historique sans exécution du service")
        DecisionCommands(actions).submit(command)
        queries.append({key: command[key] for key in QUERY_FIELDS})
    add("approval_revoked", revoked, "BLOCKED", "REVOKED")
    for query in queries:
        if lookup(store, query)["status"] != "FOUND":
            raise ValueError("fixture receipt assertion failed")
    if actions.world.observe("sim-nas")["restarts"] != 0:
        raise ValueError("unexpected simulated restart")
    return {"protocol": PROTOCOL, "synthetic": True, "store_id": store_id,
            "state_directory": "state", "token_file": "read-token",
            "scenarios": scenarios, "receipt_queries": queries,
            "simulated_service_restarts": 0, "external_services_contacted": False,
            "server_started": False, "authorizes_execution": False}


def create(destination, *, profile="missions"):
    report = {"protocol": PROTOCOL, "status": "NOT_CREATED",
              "code": "DESTINATION_UNAVAILABLE", "destination_created": False,
              "synthetic": True, "server_started": False, "authorizes_execution": False}
    if type(profile) is not str or profile not in {"missions", "research-archives"}:
        report["code"] = "INVALID_PROFILE"
        return report
    try:
        root = Path(destination)
        # mkdir is exclusive, including for dangling symlinks and existing files.
        root.mkdir(mode=0o700)
    except FileExistsError:
        report["code"] = "DESTINATION_EXISTS"
        return report
    except (OSError, TypeError, ValueError):
        return report
    report.update(status="INCOMPLETE", code="PREPARATION_FAILED", destination_created=True)
    try:
        root.chmod(0o700)  # permit use even under an unusually restrictive umask
        state = root / "state"
        state.mkdir(mode=0o700)
        state.chmod(0o700)
        marker = state / "BETA-PREPARATION-INCOMPLETE"
        marker.write_text("Synthetic fixture preparation is incomplete. Do not serve or resume.\n", encoding="utf-8")
        if profile == "research-archives":
            from .beta_research_fixture import populate
            manifest = populate(state)
        else:
            manifest = _populate(state)
        if create_token(root / "read-token")["status"] != "CREATED":
            return report
        with (root / "manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # No operation that may fail follows publication. The parent is private
        # and exclusively owned by this invocation, not a concurrent workspace.
        marker.unlink()
    except Exception:
        # CLI boundary: never expose raw exception contents, state or secrets.
        # KeyboardInterrupt/SystemExit still propagate; partial data is retained.
        return report
    report.update(status="READY", code="FIXTURE_READY" if profile == "missions" else "RESEARCH_FIXTURE_READY",
                  mission_count=len(manifest["scenarios"]), receipt_count=len(manifest["receipt_queries"]))
    return report


def render(report, output_format):
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    return "\n".join((header(title="Recette synthétique"),
                      message("OK" if report["status"] == "READY" else "ERREUR",
                              report["code"] + " : " + TEXT[report["code"]]),
                      message("INFO", "Aucun serveur lancé. Utiliser manifest.json puis http_api --check ; "
                              "un reçu historique n’autorise aucune exécution.")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — préparer un jeu de missions synthétiques isolé")
    parser.add_argument("--output", required=True, help="Nouveau dossier dans un parent existant de confiance")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    parser.add_argument("--profile", choices=("missions", "research-archives"), default="missions")
    args = parser.parse_args(argv)
    report = create(args.output, profile=args.profile)
    print(render(report, args.format))
    return 0 if report["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
