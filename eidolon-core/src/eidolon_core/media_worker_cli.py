# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_worker_cli.py
# Description : Exécution opérateur explicite des tickets média
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Operator-only POSIX CLI. No enqueue from arbitrary JSON and no automatic daemon."""
import argparse
import json
import sqlite3
import sys

from .contracts import ContractError
from .conversation_store import ConversationStore
from .http_api import ReadOnlyStore
from .media_agents import MediaError, load_json
from .media_artifacts import ArtifactStore
from .media_worker import MediaWorker, initialize
from .presentation import header, message, section


def render(value):
    lines = [header(title="File des agents Image/Vidéo")]
    rows = value.get("tickets", [value.get("receipt", value)])
    for row in rows:
        lines.append(section("Ticket média"))
        for key, label in (("ticket_id", "Ticket"), ("job_id", "Travail"), ("state", "État enregistré"),
                           ("execution", "Exécution"), ("failure_code", "Diagnostic")):
            if row.get(key) is not None:
                lines.append(message("INFO", f"{label} : {row[key]}"))
    view = value.get("result")
    if isinstance(view, dict):
        lines.append(section("Résultat non vérifié"))
        lines.append(message("INFO", f"Liaison : {view.get('binding')} ; état reçu : {view.get('state_received')}"))
        collection = view.get("collection")
        if isinstance(collection, dict):
            lines.append(message("INFO", f"Collecte : {collection.get('imported')} / {collection.get('expected')} ; partielle : {collection.get('partial')}"))
        for output in view.get("outputs", []):
            lines.append(message("INFO", f"Artefact {output.get('artifact_id')} ; empreinte : {output.get('verification')} ; contenu non vérifié"))
        observation = view.get("observation")
        if isinstance(observation, dict):
            lines.append(message("ATTENTION", "Observation du modèle, non vérifiée : " + str(observation.get("text", ""))))
    if value.get("observation"):
        lines.append(message("INFO", "Observation : " + value["observation"]))
    lines.append(message("ATTENTION", "Un reçu ou un résultat moteur ne prouve pas la réussite de la demande."))
    lines.append(message("INFO", "Aucune nouvelle tentative automatique ; réservation libérée après revue explicite."))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — file média, opérations explicites sur le serveur")
    parser.add_argument("--root", required=True, help="dossier privé de la file média")
    parser.add_argument("--state", required=True, help="état Core existant ; jamais créé ou migré ici")
    parser.add_argument("--worker-id", help="identité exacte, requise sauf pour init")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="créer une NOUVELLE file privée, sans moteur")
    listing = sub.add_parser("list", help="reçus d'un client, lecture locale")
    listing.add_argument("--client-id", required=True)
    for name in ("run", "result", "poll", "collect"):
        p = sub.add_parser(name)
        p.add_argument("--client-id", required=True)
        p.add_argument("--ticket", required=True)
        if name == "run":
            p.add_argument("--config", required=True)
            p.add_argument("--execute-local", action="store_true", required=True,
                           help="autoriser cet essai moteur local ; ne découle pas de la soumission")
        if name in {"result", "collect"}:
            p.add_argument("--artifact-root", required=True)
            p.add_argument("--artifact-store-id", required=True)
        if name == "collect":
            p.add_argument("--collect-local", action="store_true", required=True,
                           help="lire le moteur puis importer ses sorties, un seul essai")
    args = parser.parse_args(argv)
    try:
        conversations = ConversationStore(ReadOnlyStore(args.state))
        if args.command == "init":
            value = initialize(args.root, store_id=conversations.store_id)
        else:
            if not args.worker_id:
                raise MediaError("WORKER_ID_REQUIRED")
            worker = MediaWorker(args.root, worker_id=args.worker_id, store_id=conversations.store_id)
            if args.command == "list":
                value = {"tickets": worker.tickets(client_id=args.client_id)}
            elif args.command == "run":
                value = worker.run_once(args.ticket, client_id=args.client_id, conversations=conversations,
                                        config=load_json(args.config), execute_local=args.execute_local)
            elif args.command == "poll":
                value = worker.poll_once(args.ticket, client_id=args.client_id)
            else:
                artifacts = ArtifactStore(args.artifact_root, expected_store_id=args.artifact_store_id)
                if args.command == "collect":
                    value = worker.collect_once(args.ticket, client_id=args.client_id, artifact_store=artifacts)
                else:
                    value = worker.result(args.ticket, client_id=args.client_id, conversations=conversations,
                                          artifact_store=artifacts)
        print(render(value) if args.format == "human" else json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (MediaError, ContractError, OSError, ValueError, sqlite3.Error) as exc:
        code = exc.code if isinstance(exc, MediaError) else str(exc).split(":")[0] if isinstance(exc, ContractError) else "WORKER_UNAVAILABLE"
        print(message("ERREUR", code) if args.format == "human" else json.dumps({"error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
