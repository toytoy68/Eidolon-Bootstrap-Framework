#!/usr/bin/env python3
# ==========================================================
# Projet       : Eidolon Bootstrap Framework
# Script       : video-generation/eidolon_video.py
# Version      : 0.1.0-alpha
# Description  : Client minimal (bibliothèque standard seule)
#                pour lancer un workflow vidéo ComfyUI depuis
#                Eidolon, avec enrichissement facultatif du
#                prompt par un LLM local via Ollama.
# ==========================================================
"""Génère une vidéo via l'API HTTP de ComfyUI.

Exemples :
  python3 eidolon_video.py -w workflows/wan22-ti2v-5b-v100-16g.json \\
      -p "un phare sous l'orage, vagues énormes, plan aérien"

  python3 eidolon_video.py -w workflows/wan22-t2v-14b-gguf-v100.json \\
      -p "..." --enhance --ollama-model huihui_ai/qwen3-abliterated:14b

  # Surcharge générique d'une entrée de nœud (valeur JSON ou texte) :
  python3 eidolon_video.py -w ... -p "..." \\
      --set 1.unet_name=Wan2.2-T2V-A14B-HighNoise-Q5_K_M.gguf

Le workflow doit être au format API de ComfyUI. Les nœuds de prompt
sont repérés par leur titre (_meta.title) « Positive » et « Negative ».
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ENHANCE_SYSTEM = (
    "You rewrite short video ideas into a single detailed prompt for the "
    "Wan 2.2 text-to-video model. Write one English paragraph of 60 to 120 "
    "words describing, in this order: the subject and its action, the "
    "setting, lighting and mood, camera framing and movement, and visual "
    "style. Use concrete visual details only. Do not add dialogue, text "
    "overlays, lists, quotes or any commentary. Output only the prompt."
)


# ----------------------------------------------------------
# HTTP
# ----------------------------------------------------------

def http_json(url: str, payload: dict | None = None, timeout: float = 30) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ----------------------------------------------------------
# Enrichissement du prompt (Ollama)
# ----------------------------------------------------------

def enhance_prompt(idea: str, url: str, model: str, keep_alive: str | int = 0) -> str:
    payload = {
        "model": model,
        "system": ENHANCE_SYSTEM,
        "prompt": idea,
        "stream": False,
        "think": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0.7},
    }
    try:
        out = http_json(url.rstrip("/") + "/api/generate", payload, timeout=300)
    except urllib.error.HTTPError as exc:
        # Anciennes versions d'Ollama : le champ "think" peut être refusé.
        if exc.code == 400:
            payload.pop("think", None)
            out = http_json(url.rstrip("/") + "/api/generate", payload, timeout=300)
        else:
            raise
    text = out.get("response", "")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return text or idea


# ----------------------------------------------------------
# Modification du workflow
# ----------------------------------------------------------

def nodes_by_title(wf: dict, title: str) -> list[dict]:
    return [n for n in wf.values() if n.get("_meta", {}).get("title") == title]


def set_if_scalar(inputs: dict, key: str, value: Any) -> bool:
    """Remplace une entrée seulement si ce n'est pas un lien vers un autre nœud."""
    if key in inputs and not isinstance(inputs[key], list):
        inputs[key] = value
        return True
    return False


def apply_steps(wf: dict, steps: int) -> None:
    advanced = [n for n in wf.values() if n.get("class_type") == "KSamplerAdvanced"]
    if steps < (2 if advanced else 1):
        raise ValueError("Au moins 2 étapes pour High/Low Noise, 1 pour un sampler simple.")
    if advanced:
        # Deux passes (High Noise puis Low Noise) : on conserve la
        # proportion de bascule définie dans le workflow.
        first = next(
            (n for n in advanced if n["inputs"].get("start_at_step") == 0),
            advanced[0],
        )
        old_steps = max(int(first["inputs"].get("steps", steps)), 1)
        old_switch = int(first["inputs"].get("end_at_step", old_steps // 2))
        switch = max(1, min(steps - 1, round(steps * old_switch / old_steps)))
        for n in advanced:
            i = n["inputs"]
            i["steps"] = steps
            if i.get("start_at_step") == 0:
                i["end_at_step"] = switch
            else:
                i["start_at_step"] = switch
    for n in wf.values():
        if n.get("class_type") == "KSampler":
            n["inputs"]["steps"] = steps


def parse_set(expr: str) -> tuple[str, str, Any]:
    if "=" not in expr or "." not in expr.split("=", 1)[0]:
        raise ValueError(f"--set attend NŒUD.entrée=valeur, reçu : {expr}")
    target, raw = expr.split("=", 1)
    node_id, key = target.split(".", 1)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    return node_id, key, value


def prepare_workflow(wf: dict, args: argparse.Namespace, prompt: str) -> dict:
    pos = nodes_by_title(wf, "Positive")
    if not pos:
        raise SystemExit("Aucun nœud intitulé « Positive » dans le workflow.")
    for n in pos:
        n["inputs"]["text"] = prompt

    if args.negative is not None:
        for n in nodes_by_title(wf, "Negative"):
            n["inputs"]["text"] = args.negative

    seed = args.seed if args.seed is not None else random.randint(0, 2**32 - 1)
    for n in wf.values():
        i = n.get("inputs", {})
        set_if_scalar(i, "seed", seed)
        set_if_scalar(i, "noise_seed", seed)
        for key in ("width", "height", "length"):
            value = getattr(args, key)
            if value is not None:
                set_if_scalar(i, key, value)
        if args.fps is not None and n.get("class_type") == "CreateVideo":
            i["fps"] = float(args.fps)
        if args.prefix and n.get("class_type") == "SaveVideo":
            i["filename_prefix"] = args.prefix

    if args.steps is not None:
        apply_steps(wf, args.steps)

    for expr in args.set or []:
        node_id, key, value = parse_set(expr)
        if node_id not in wf:
            raise SystemExit(f"--set : nœud {node_id} absent du workflow.")
        if key not in wf[node_id]["inputs"]:
            raise ValueError(f"--set : entrée {node_id}.{key} absente du workflow.")
        wf[node_id]["inputs"][key] = value

    validate_workflow(wf)
    args.used_seed = seed
    return wf


def validate_workflow(wf: dict) -> None:
    """Contrôles locaux des graphes fournis ; l'API ComfyUI reste autoritaire."""
    for node_id, node in wf.items():
        inputs = node["inputs"]
        for key, value in inputs.items():
            if isinstance(value, list):
                if (len(value) != 2 or value[0] not in wf
                        or type(value[1]) is not int or value[1] < 0):
                    raise ValueError(f"Lien invalide : {node_id}.{key}")
        kind = node["class_type"]
        if kind in ("Wan22ImageToVideoLatent", "EmptyHunyuanLatentVideo"):
            multiple = 32 if kind == "Wan22ImageToVideoLatent" else 16
            for key in ("width", "height", "length", "batch_size"):
                value = inputs[key]
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{node_id}.{key} doit être un entier positif.")
            if inputs["width"] % multiple or inputs["height"] % multiple:
                raise ValueError(f"Dimensions attendues : multiples de {multiple}.")
            if (inputs["length"] - 1) % 4:
                raise ValueError("Le nombre d'images doit valoir 4n + 1.")
        if kind in ("KSampler", "KSamplerAdvanced"):
            steps = inputs["steps"]
            if type(steps) is not int or steps < (2 if kind == "KSamplerAdvanced" else 1):
                raise ValueError("Nombre d'étapes invalide.")
            if kind == "KSamplerAdvanced":
                start, end = inputs["start_at_step"], inputs["end_at_step"]
                if (type(start) is not int or type(end) is not int
                        or not 0 <= start < min(end, steps)):
                    raise ValueError("Intervalle de débruitage vide ou invalide.")
        if kind == "CreateVideo":
            fps = inputs["fps"]
            if (isinstance(fps, bool) or not isinstance(fps, (int, float))
                    or not math.isfinite(fps) or not 1 <= fps <= 120):
                raise ValueError("FPS attendu entre 1 et 120.")


# ----------------------------------------------------------
# Exécution
# ----------------------------------------------------------

def submit(server: str, wf: dict) -> str:
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    try:
        out = http_json(server + "/prompt", payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(body)
            print(json.dumps(detail, indent=2, ensure_ascii=False), file=sys.stderr)
        except json.JSONDecodeError:
            print(body, file=sys.stderr)
        raise SystemExit(f"ComfyUI a refusé le workflow (HTTP {exc.code}).")
    return out["prompt_id"]


def wait(server: str, prompt_id: str, timeout: float) -> dict:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        hist = http_json(f"{server}/history/{prompt_id}")
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                for msg in status.get("messages", []):
                    if msg[0] == "execution_error":
                        err = msg[1]
                        raise SystemExit(
                            f"Erreur dans le nœud {err.get('node_id')} "
                            f"({err.get('node_type')}) : {err.get('exception_message')}"
                        )
                raise SystemExit("Échec de l'exécution (voir les journaux de ComfyUI).")
            if status.get("completed") is True:
                return entry
        elapsed = int(time.monotonic() - start)
        print(f"\r[INFO] Génération en cours… {elapsed // 60:02d}:{elapsed % 60:02d}",
              end="", file=sys.stderr, flush=True)
        time.sleep(3)
    raise SystemExit(f"Délai dépassé ({int(timeout)} s), tâche {prompt_id}. "
                     "La tâche peut encore tourner sur ComfyUI ; elle n'a pas été annulée.")


def download_outputs(server: str, entry: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for node_out in entry.get("outputs", {}).values():
        for items in node_out.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or "filename" not in item:
                    continue
                query = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                name = item["filename"]
                if (not isinstance(name, str) or name in ("", ".", "..")
                        or any(c in name for c in ("/", "\\", ":", "\0"))):
                    raise ValueError(f"Nom de sortie non sûr : {name!r}")
                dest = out_dir / name
                # Création exclusive : refuse aussi les liens symboliques et les collisions.
                with dest.open("xb") as output:
                    try:
                        with urllib.request.urlopen(f"{server}/view?{query}", timeout=300) as r:
                            shutil.copyfileobj(r, output, length=1024 * 1024)
                    except BaseException:
                        output.close()
                        dest.unlink(missing_ok=True)
                        raise
                saved.append(dest)
    return saved


# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-w", "--workflow", required=True, type=Path, help="Workflow ComfyUI au format API")
    ap.add_argument("-p", "--prompt", required=True, help="Description de la vidéo")
    ap.add_argument("-n", "--negative", help="Prompt négatif (sinon celui du workflow)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--length", type=int, help="Nombre d'images (multiple de 4 + 1, ex. 81)")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--steps", type=int)
    ap.add_argument("--prefix", help="Préfixe du fichier de sortie côté ComfyUI")
    ap.add_argument("--set", action="append", metavar="NŒUD.entrée=valeur",
                    help="Surcharge libre d'une entrée de nœud (répétable)")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    ap.add_argument("--timeout", type=float, default=3 * 3600)
    ap.add_argument("--enhance", action="store_true", help="Enrichir le prompt avec un LLM local (Ollama)")
    ap.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ap.add_argument("--ollama-model", default="qwen3:14b")
    ap.add_argument("--ollama-keep-alive", default=0,
                    help="0 : décharger après enrichissement (défaut) ; ex. 5m sur GPU séparé")
    ap.add_argument("--dry-run", action="store_true", help="Afficher le workflow final sans l'envoyer")
    args = ap.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        ap.error("--timeout doit être positif et fini")
    if args.seed is not None and not 0 <= args.seed < 2**64:
        ap.error("--seed doit être compris entre 0 et 2**64-1")

    server = args.server.rstrip("/")
    wf = json.loads(args.workflow.read_text(encoding="utf-8"))

    prompt = args.prompt
    if args.enhance:
        print(f"[INFO] Enrichissement du prompt avec {args.ollama_model}…", file=sys.stderr)
        prompt = enhance_prompt(prompt, args.ollama_url, args.ollama_model,
                                args.ollama_keep_alive)
        print(f"[INFO] Prompt final : {prompt}", file=sys.stderr)

    wf = prepare_workflow(wf, args, prompt)

    if args.dry_run:
        print(json.dumps(wf, indent=2, ensure_ascii=False))
        return

    prompt_id = submit(server, wf)
    print(f"[INFO] Tâche {prompt_id} envoyée (seed {args.used_seed}).", file=sys.stderr)
    entry = wait(server, prompt_id, args.timeout)
    print(file=sys.stderr)

    files = download_outputs(server, entry, args.out)
    if not files:
        raise SystemExit("Aucun fichier produit.")
    for f in files:
        print(f)


if __name__ == "__main__":
    main()

