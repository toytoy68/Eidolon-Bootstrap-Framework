# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : cli.py
# Description : Commandes de mission et choix du format de sortie
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Local JSON CLI. Exit 0 succeeds, 2 blocks/reviews, 3 fails, 4 cancels/abandons."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3

from .contracts import encode
from .action_view import presented_mission
from .diagnostics import synthetic_runtime
from .actions import ActionRuntime
from .targets import Catalog
from .memory import DEMO_REQUEST, EngineMemory
from .runtime import Limits, Runtime
from .store import Busy, Store
from .presentation import PRESENTATION_STANDARD, preview, render_error, render_result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core v0.1 — synthetic local missions")
    parser.add_argument("--state", default=".eidolon-core")
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per call, including process startup")
    parser.add_argument("--memory-root", help="existing isolated Memory Engine data root (optional)")
    parser.add_argument("--profile", choices=("text", "service-sim", "action-sim"), default="text")
    parser.add_argument("--targets", help="catalog JSON for a simulation profile; destinations are never contacted")
    parser.add_argument("--allow-target", action="append", help="allowed synthetic target id; replaces default fixture grants")
    parser.add_argument("--format", choices=("json", "human"), default="json",
                        help="JSON for automation (default), human for the Eidolon console presentation")
    commands = parser.add_subparsers(dest="command", required=True)
    recovery = commands.add_parser("recovery-prepare", help="copy one mission database to a NEW review-only directory")
    recovery.add_argument("--source", required=True, help="source mission SQLite database; opened read-only")
    recovery.add_argument("--destination", required=True, help="new directory outside the source state")
    recovery.add_argument("--actor", required=True)
    recovery.add_argument("--reason", required=True)
    inspect = commands.add_parser("recovery-inspect", help="inspect a historical review copy without starting Core")
    inspect.add_argument("--mission-id")
    commands.add_parser("research-pauses", help="inspect existing durable Web pauses; no network")
    release = commands.add_parser("research-release", help="release one reviewed pause; does not send a request")
    release.add_argument("pause_id")
    release.add_argument("--revision", type=int, required=True)
    release.add_argument("--actor", required=True)
    release.add_argument("--reason", required=True)
    commands.add_parser("presentation-preview", help="preview the common presentation without creating any state")
    commands.add_parser("demo", help="create and run the deterministic synthetic mission")
    diagnose = commands.add_parser("diagnose", help="observe one synthetic service, requires --profile service-sim")
    diagnose.add_argument("target")
    diagnose.add_argument("--create-only", action="store_true")
    restart = commands.add_parser("restart", help="propose a synthetic restart, requires --profile action-sim")
    restart.add_argument("target")
    decide = commands.add_parser("decide", help="record a local action decision; does not execute")
    decide.add_argument("mission_id")
    decide.add_argument("--proposal-sha", required=True)
    decide.add_argument("--decision", choices=("approve", "reject", "revoke"), required=True)
    decide.add_argument("--actor", required=True)
    decide.add_argument("--reason", required=True)
    submit = commands.add_parser("command-submit", help="record a synthetic decision and durable receipt; no execution")
    submit.add_argument("--request", required=True, help="JSON command file, at most 32768 bytes")
    cancel_command = commands.add_parser("command-cancel", help="record a cancellation request and receipt; no runtime")
    cancel_command.add_argument("--request", required=True, help="JSON cancellation file, at most 32768 bytes")
    receipt = commands.add_parser("command-receipt", help="look up a historical command receipt; no runtime")
    receipt.add_argument("--store-id", required=True)
    receipt.add_argument("--client-id", required=True)
    receipt.add_argument("--command-key", required=True)
    fixture = commands.add_parser("fixture", help="inspect or change ONLY the synthetic service state")
    fixture.add_argument("target")
    fixture.add_argument("--set-state", choices=("UP", "DOWN", "UNREACHABLE"))
    create = commands.add_parser("create", help="create a durable mission without executing it")
    create.add_argument("request", nargs="?", default=DEMO_REQUEST)
    for name in ("run", "show", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("mission_id")
        if name == "show":
            command.add_argument("--events", action="store_true")
    listing = commands.add_parser("client-missions", help="list bounded mission projections; local read-only")
    listing.add_argument("--cursor", help="JSON continuation cursor from a previous page")
    listing.add_argument("--limit", type=int, default=50)
    capture = commands.add_parser("client-snapshot", help="local read-only client projection; no network")
    capture.add_argument("mission_id")
    poll = commands.add_parser("client-poll", help="read event references after a saved cursor")
    poll.add_argument("mission_id")
    poll.add_argument("--cursor", required=True, help="JSON file containing the cursor object only")
    poll.add_argument("--limit", type=int, default=50)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("mission_id")
    reconcile.add_argument("--decision", choices=("no-effect", "observed-result", "use-receipt", "abandon"), required=True)
    reconcile.add_argument("--confirm-no-effect", action="store_true",
                           help="attest investigated absence of effect after an authorized/uncertain call, including an error receipt")
    reconcile.add_argument("--actor", required=True)
    reconcile.add_argument("--reason", required=True)
    reconcile.add_argument("--result", help="JSON file containing the observed tool output")
    args = parser.parse_args(argv)
    try:
        if args.command in {"recovery-prepare", "recovery-inspect"}:
            from .recovery import inspect_review, prepare_review
            result = (prepare_review(args.source, args.destination, actor=args.actor, reason=args.reason)
                      if args.command == "recovery-prepare" else
                      inspect_review(args.state, mission_id=args.mission_id))
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Copie historique en revue") + message("ATTENTION", encode(result)))
            else:
                print(encode(result))
            return 0  # Copy/inspection completed, never permission to resume.
        if args.command in {"research-pauses", "research-release"}:
            from .research_pauses import ResearchPauses
            path = Path(args.state) / "research-pauses.sqlite3"
            if not path.is_file():
                raise FileNotFoundError("research pauses require an existing pause database")
            pauses = ResearchPauses(path)
            result = (pauses.inspect() if args.command == "research-pauses" else
                      pauses.release(args.pause_id, expected_revision=args.revision, actor=args.actor, reason=args.reason))
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Suspensions Web") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 0  # inspection/release completed; no request was sent
        if args.command == "presentation-preview":
            text = preview()
            print(text if args.format == "human" else encode({"standard": PRESENTATION_STANDARD, "preview": text}))
            return 0
        if args.profile == "text" and (args.targets or args.allow_target):
            raise ValueError("target options require a simulation profile")
        if args.command == "diagnose" and args.profile != "service-sim":
            raise ValueError("diagnose requires --profile service-sim")
        if args.command in {"restart", "decide", "fixture", "command-submit"} and args.profile != "action-sim":
            raise ValueError("action commands require --profile action-sim")
        if args.profile != "text" and args.command in {"demo", "create"}:
            raise ValueError("simulation missions are created with diagnose or restart")
        if args.command == "command-cancel":
            from .commands import CancelCommands, parse_cancel_command
            with Path(args.request).open("rb") as handle:
                command = parse_cancel_command(handle.read(32769))
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise FileNotFoundError("cancellation requires an existing mission store")
            result = CancelCommands(Store(args.state)).submit(command)
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Demande d'annulation") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 0  # Request recorded; worker termination/effect absence are not claimed.
        if args.command == "command-receipt":
            from .commands import lookup_receipt
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise FileNotFoundError("receipt lookup requires an existing mission store")
            result = lookup_receipt(Store(args.state), store_id=args.store_id,
                                    client_id=args.client_id, command_key=args.command_key)
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Reçu de décision locale") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 0 if result["status"] == "FOUND" else 2
        command_request = None
        if args.command == "command-submit":
            from .commands import parse_command
            with Path(args.request).open("rb") as handle:
                command_request = parse_command(handle.read(32769))
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise FileNotFoundError("decision command requires an existing mission store")
        catalog = None
        if args.targets:
            path = Path(args.targets)
            if path.stat().st_size > 1_000_000:
                raise ValueError("catalog file exceeds 1 MB")
            catalog = Catalog.from_config(json.loads(path.read_text(encoding="utf-8")))
        if args.command == "client-missions":
            from .mission_list import MissionList, parse_cursor
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise FileNotFoundError("mission listing requires an existing mission store")
            cursor = None
            if args.cursor:
                with Path(args.cursor).open("rb") as handle:
                    cursor = parse_cursor(handle.read(4097))
            result = MissionList(Store(args.state)).page(cursor=cursor, limit=args.limit)
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Inventaire des missions") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 2 if result["status"] == "RESET_REQUIRED" else 0
        if args.command in {"client-snapshot", "client-poll"}:
            from .client_sync import ClientSync
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise FileNotFoundError("client sync requires an existing mission store")
            sync = ClientSync(Store(args.state))
            if args.command == "client-snapshot":
                result = sync.snapshot(args.mission_id)
            else:
                with Path(args.cursor).open("rb") as handle:
                    raw_cursor = handle.read(4097)
                if len(raw_cursor) > 4096:
                    raise ValueError("cursor file exceeds 4096 bytes")
                result = sync.poll(args.mission_id, json.loads(raw_cursor), limit=args.limit)
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Synchronisation locale") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 2 if result["status"] == "RESET_REQUIRED" else 0
        store = Store(args.state)
        options = {"limits": Limits(args.timeout),
                   "memory": EngineMemory(str(Path(args.memory_root).resolve())) if args.memory_root else None}
        runtime = (synthetic_runtime(store, catalog=catalog, allowed_targets=args.allow_target, **options)
                   if args.profile == "service-sim" else Runtime(store, **options))
        if args.profile == "action-sim":
            runtime = ActionRuntime(store, catalog=catalog, allowed_targets=args.allow_target, **options)
        if args.command == "command-submit":
            from .commands import DecisionCommands
            result = DecisionCommands(runtime).submit(command_request)
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Décision locale enregistrée") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 0  # Recording succeeded; no execution is claimed.
        if args.command == "fixture":
            result = (runtime.world.set_state(args.target, args.set_state) if args.set_state
                      else runtime.world.observe(args.target))
            if args.format == "human":
                from .presentation import header, message
                print(header(title="Service fictif") + message("INFO", encode(result)))
            else:
                print(encode(result))
            return 0
        if args.command == "restart":
            result = runtime.run(runtime.create_restart(args.target)["id"])
        elif args.command == "decide":
            result = runtime.decide(args.mission_id, expected_sha256=args.proposal_sha,
                                    decision=args.decision, actor=args.actor, reason=args.reason)
        elif args.command == "diagnose":
            result = runtime.create_diagnostic(args.target)
            if not args.create_only:
                result = runtime.run(result["id"])
        elif args.command in ("demo", "create"):
            result = runtime.create(DEMO_REQUEST if args.command == "demo" else args.request)
            if args.command == "demo":
                result = runtime.run(result["id"])
        elif args.command == "run":
            result = runtime.run(args.mission_id)
        elif args.command == "show":
            result = store.get(args.mission_id)
            if args.events:
                result["events"] = store.events(args.mission_id)
        elif args.command == "cancel":
            result = runtime.cancel(args.mission_id)
        else:
            output = None
            if args.result:
                path = Path(args.result)
                if path.stat().st_size > 1_000_000:
                    raise ValueError("result file exceeds 1 MB")
                output = json.loads(path.read_text(encoding="utf-8"))
            result = runtime.reconcile(args.mission_id, decision=args.decision,
                                       actor=args.actor, reason=args.reason, output=output,
                                       confirm_no_effect=args.confirm_no_effect)
        print(render_result(result) if args.format == "human" else encode(presented_mission(result)))
        if args.command in {"show", "create", "reconcile", "decide"} or (args.command == "diagnose" and args.create_only):
            return 0
        return {"SUCCEEDED": 0, "FAILED": 3, "CANCELLED": 4, "ABANDONED": 4}.get(result["status"], 2)
    except sqlite3.Error as exc:
        diagnostic = "storage unavailable; preserve uncertainty and inspect state/receipts before any resend"
        print(render_error("STORAGE_UNAVAILABLE", diagnostic) if args.format == "human"
              else encode({"error": "STORAGE_UNAVAILABLE", "message": diagnostic,
                           "cause_type": type(exc).__name__}), file=sys.stderr)
        return 2
    except (ValueError, KeyError, OSError, Busy) as exc:
        print(render_error(type(exc).__name__, str(exc)) if args.format == "human"
              else encode({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        diagnostic = "state preserved; use show/run to diagnose"
        print(render_error("INTERRUPTED", diagnostic) if args.format == "human"
              else encode({"error": "INTERRUPTED", "message": diagnostic}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
