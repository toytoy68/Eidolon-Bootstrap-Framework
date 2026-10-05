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

from .contracts import encode
from .memory import DEMO_REQUEST, EngineMemory
from .runtime import Limits, Runtime
from .store import Busy, Store
from .presentation import PRESENTATION_STANDARD, preview, render_error, render_result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core v0.1 — synthetic local missions")
    parser.add_argument("--state", default=".eidolon-core")
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per call, including process startup")
    parser.add_argument("--memory-root", help="existing isolated Memory Engine data root (optional)")
    parser.add_argument("--format", choices=("json", "human"), default="json",
                        help="JSON for automation (default), human for the Eidolon console presentation")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("presentation-preview", help="preview the common presentation without creating any state")
    commands.add_parser("demo", help="create and run the deterministic synthetic mission")
    create = commands.add_parser("create", help="create a durable mission without executing it")
    create.add_argument("request", nargs="?", default=DEMO_REQUEST)
    for name in ("run", "show", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("mission_id")
        if name == "show":
            command.add_argument("--events", action="store_true")
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
        if args.command == "presentation-preview":
            text = preview()
            print(text if args.format == "human" else encode({"standard": PRESENTATION_STANDARD, "preview": text}))
            return 0
        store = Store(args.state)
        runtime = Runtime(store, limits=Limits(args.timeout),
                          memory=EngineMemory(str(Path(args.memory_root).resolve())) if args.memory_root else None)
        if args.command in ("demo", "create"):
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
        print(render_result(result) if args.format == "human" else encode(result))
        if args.command in {"show", "create", "reconcile"}:
            return 0
        return {"SUCCEEDED": 0, "FAILED": 3, "CANCELLED": 4, "ABANDONED": 4}.get(result["status"], 2)
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
