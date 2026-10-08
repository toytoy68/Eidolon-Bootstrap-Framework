# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_cli.py
# Description : Installation et usage explicite des agents Image/Vidéo en local
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""eidolon-media CLI: read-only catalog/prepare/inspect; explicit run on local engines."""
import argparse
import json
import sys

from .media_agents import MediaError, catalog, execute, inspect, load_json, prepare
from .media_backends import poll_job


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — agents Image et Vidéo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("agents", help="list installed agents; no engine contact")
    p = sub.add_parser("prepare", help="validate a draft offline; no file-content or engine access")
    p.add_argument("--request", required=True)
    p = sub.add_parser("run", help="explicit local engine call in a NEW private job directory")
    p.add_argument("--request", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--job", required=True)
    p.add_argument("--execute-local", action="store_true", required=True,
                   help="send chosen content to configured local engine; never enabled by a read token")
    for name in ("inspect", "poll"):
        p = sub.add_parser(name, help="inspect local record" if name == "inspect" else "read ComfyUI history once, no resubmit")
        p.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "agents":
            result = catalog()
        elif args.command == "prepare":
            result = {"state": "LOCAL_DRAFT", "submitted": False, "request": prepare(load_json(args.request, 32_000))}
        elif args.command == "run":
            result = execute(load_json(args.request, 32_000), load_json(args.config), args.job)
        elif args.command == "inspect":
            result = inspect(args.job)
        else:
            result = poll_job(inspect(args.job))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        # Exit 0 means command completed, not content verified or mission achieved.
        return 0
    except (MediaError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        code = exc.code if isinstance(exc, MediaError) else "MEDIA_INPUT_OR_STORAGE_ERROR"
        print(json.dumps({"error": code, "automatic_retry": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
