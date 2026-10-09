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
from .media_artifacts import ArtifactStore, initialize
from .media_outputs import collect, inspect_collection
from .media_preflight import preflight, render_preflight


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — agents Image et Vidéo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("agents", help="list installed agents; no engine contact")
    p = sub.add_parser("preflight", help="check chosen local inputs; optional metadata probes, never inference")
    p.add_argument("--request", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--probe-local", action="store_true", help="explicitly query configured local node/model metadata")
    p.add_argument("--format", choices=("json", "human"), default="json")
    p = sub.add_parser("collect", help="copy recorded ComfyUI outputs into a private store, without resubmission")
    p.add_argument("--job", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--store-id", required=True)
    p.add_argument("--collection", required=True, help="NEW collection directory in a trusted parent")
    p = sub.add_parser("collection-inspect", help="inspect a collection offline, including partial imports")
    p.add_argument("--collection", required=True)
    p = sub.add_parser("artifact-init", help="create a NEW private artifact store; no engine contact")
    p.add_argument("--root", required=True)
    p.add_argument("--max-artifacts", type=int, default=128)
    p.add_argument("--max-bytes", type=int, default=1024 * 1024 * 1024)
    for name in ("artifact-import", "artifact-inspect", "artifacts", "artifact-recovery-inspect", "artifact-publish", "artifact-export"):
        p = sub.add_parser(name, help="import explicitly or inspect local media artifacts")
        p.add_argument("--root", required=True)
        p.add_argument("--store-id", required=True)
        if name == "artifact-import":
            p.add_argument("--source", required=True)
        elif name in {"artifact-inspect", "artifact-publish", "artifact-export"}:
            p.add_argument("--reference", required=True, help="JSON reference or import manifest")
        if name == "artifact-export":
            p.add_argument("--destination", required=True, help="NEW file outside the store, in an owned private directory")
        if name in {"artifact-recovery-inspect", "artifact-publish"}:
            p.add_argument("--pending", required=True)
        if name == "artifact-publish":
            p.add_argument("--publish-reviewed", required=True, action="store_true", help="explicitly publish the reviewed complete pending bundle")
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
        elif args.command == "preflight":
            result = preflight(load_json(args.request, 32_000), load_json(args.config), probe_local=args.probe_local)
        elif args.command == "collect":
            result = collect(args.job, args.root, args.store_id, args.collection)
        elif args.command == "collection-inspect":
            result = inspect_collection(args.collection)
        elif args.command == "artifact-init":
            result = initialize(args.root, max_artifacts=args.max_artifacts, max_bytes=args.max_bytes)
        elif args.command in {"artifact-import", "artifact-inspect", "artifacts", "artifact-recovery-inspect", "artifact-publish", "artifact-export"}:
            store = ArtifactStore(args.root, expected_store_id=args.store_id)
            if args.command == "artifact-import":
                result = store.import_file(args.source)
            elif args.command == "artifacts":
                result = store.inventory()
            elif args.command == "artifact-recovery-inspect":
                result = store.inspect_pending(args.pending)
            else:
                ref = load_json(args.reference, 4096)
                if type(ref) is dict and "reference" in ref:
                    ref = ref["reference"]
                if args.command == "artifact-publish":
                    result = store.publish_pending(args.pending, ref)
                elif args.command == "artifact-export":
                    result = store.export_file(ref, args.destination)
                else:
                    _, manifest = store.read(ref)
                    result = {"artifact": manifest, "content_hash_checked": True, "semantic_content_verified": False}
        elif args.command == "prepare":
            result = {"state": "LOCAL_DRAFT", "submitted": False, "request": prepare(load_json(args.request, 32_000))}
        elif args.command == "run":
            result = execute(load_json(args.request, 32_000), load_json(args.config), args.job)
        elif args.command == "inspect":
            result = inspect(args.job)
        else:
            result = poll_job(inspect(args.job))
        if args.command == "preflight" and args.format == "human":
            print(render_preflight(result))
        else:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        if args.command == "preflight" and result["state"] == "PROBE_INCOMPLETE":
            return 3
        # Exit 0 means command completed, not content verified or mission achieved.
        return 0
    except (MediaError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        code = exc.code if isinstance(exc, MediaError) else "MEDIA_INPUT_OR_STORAGE_ERROR"
        print(json.dumps({"error": code, "automatic_retry": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
