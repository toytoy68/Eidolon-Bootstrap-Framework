# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_vision_contention.py
# Description : Banc vision : taille d'image et contention avec le dialogue sur le même GPU, images synthétiques (G169)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""VM Core, run by Codex through the existing GPU tunnel (loopback only):

  python3 bench_vision_contention.py --src /…/eidolon-core/src --endpoint http://127.0.0.1:11435 \\
      --vision-model gemma4:12b --dialogue-model <modèle du dialogue> [--runs 5] [--out result.json]

Questions: (1) does a smaller image (640, 896, 1280 px wide) change the vision latency, or does the model
resize anyway? (2) how much do vision and dialogue slow each other on the same GPU? Images are SYNTHETIC
shapes (no person, no face): the presence answer is not a qualification on people. Nothing is kept
except times and the model's yes/no; no prompt or image is written to disk.
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.request


def image(width):
    from PIL import Image, ImageDraw
    import io
    height = round(width * 9 / 16)
    picture = Image.new("RGB", (width, height), (230, 230, 230))
    draw = ImageDraw.Draw(picture)
    draw.rectangle((width // 10, height // 5, width // 2, height * 4 // 5), fill=(40, 90, 160))
    draw.ellipse((width * 6 // 10, height // 4, width * 9 // 10, height * 3 // 4), fill=(200, 60, 40))
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def dialogue_once(endpoint, model):
    body = json.dumps({"model": model, "stream": False, "options": {"num_predict": 120, "temperature": 0},
                       "messages": [{"role": "user", "content": "Explique en cinq phrases ce qu'est une sauvegarde chiffrée."}]}).encode()
    request = urllib.request.Request(endpoint + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    with opener.open(request, timeout=180) as response:
        response.read(1024 * 1024)
    return time.monotonic() - started


def summary(values):
    values = sorted(values)
    return {"n": len(values), "p50_s": round(statistics.median(values), 2) if values else None,
            "p95_s": round(values[min(len(values) - 1, int(0.95 * len(values)))], 2) if values else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11435")
    parser.add_argument("--vision-model", required=True)
    parser.add_argument("--dialogue-model", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--out", default="bench-vision-contention.json")
    args = parser.parse_args()
    if not args.endpoint.startswith("http://127.0.0.1:"):
        raise SystemExit("loopback endpoint only")
    sys.path.insert(0, args.src)
    from eidolon_core.comm_vision import OllamaVision
    vision = OllamaVision(args.endpoint, args.vision_model)
    result = {"synthetic_images": True, "vision_model": args.vision_model, "dialogue_model": args.dialogue_model}

    def vision_times(width, runs):
        data, times, errors = image(width), [], 0
        for _ in range(runs):
            started = time.monotonic()
            try:
                vision.describe(data, time.monotonic() + 120)
                times.append(time.monotonic() - started)
            except Exception:                       # noqa: BLE001 - counted, never printed (may hold paths)
                errors += 1
        return {"bytes": len(data), **summary(times), "errors": errors}

    vision.describe(image(640), time.monotonic() + 180)              # warm-up, not measured
    dialogue_once(args.endpoint, args.dialogue_model)
    result["vision_alone"] = {str(w): vision_times(w, args.runs) for w in (640, 896, 1280)}
    result["dialogue_alone"] = summary([dialogue_once(args.endpoint, args.dialogue_model) for _ in range(args.runs)])
    load, stop = [], threading.Event()

    def background():
        while not stop.is_set():
            try:
                load.append(dialogue_once(args.endpoint, args.dialogue_model))
            except Exception:                       # noqa: BLE001
                pass
    worker = threading.Thread(target=background, daemon=True); worker.start()
    result["vision_during_dialogue"] = {"1280": vision_times(1280, args.runs)}
    stop.set(); worker.join(200)
    result["dialogue_during_vision"] = summary(load)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
