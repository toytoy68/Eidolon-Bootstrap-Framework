# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_stt_vocabulary.py
# Description : Banc STT français avant/après vocabulaire contrôlé : noms, nombres, silence, bruit, phrases longues (G164)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""VM Core, run by Codex with the INSTALLED engines (Claude has no model in its container):

  python3 bench_stt_vocabulary.py --src /…/eidolon-core/src --comm /home/toytoy/eidolon-comm \\
      [--voice fr_FR-siwis-medium] [--out result.json]

Speech is synthesized by Piper (licit, synthetic, French), resampled to 16 kHz in Python; silence and
noise are generated with a fixed seed. Nothing is recorded or kept: only texts, scores and times go to
the JSON. Configurations compared on the SAME audio:
  baseline   no vocabulary, no guard (current deployment)
  guards     silence gate + no-speech/hallucination filters only
  replace    guards + exact replacements (no model bias)
  prompt     glossary initial_prompt + replacements + guards
  hotwords   faster-whisper hotwords + replacements + guards
  prompt+vad prompt with vad_filter=True
Reading the result: a configuration is acceptable only if silence/noise stay EMPTY (no invented text)
and the WER of phrases WITHOUT the names does not get worse; synthetic voice is not a human accuracy.
"""
import argparse
import gc
import array
import io
import json
import math
from pathlib import Path
import random
import re
import sys
import time
import wave

PHRASES = [
    ("control", "Merci d'avoir regardé cette vidéo.", "merci d'avoir regardé cette vidéo"),
    ("control", "Sous-titres activés.", "sous-titres activés"),
    ("control", "Abonnez-vous à cette lettre.", "abonnez-vous à cette lettre"),
    ("names", "Bonjour toytoy. Comment vas-tu aujourd'hui ?", "bonjour toytoy comment vas-tu aujourd'hui"),
    ("names", "Eidolon, ouvre la conversation avec toytoy.", "eidolon ouvre la conversation avec toytoy"),
    ("names", "Eidolon, décris la scène devant la caméra.", "eidolon décris la scène devant la caméra"),
    ("numbers", "Les nombres vingt-quatre, cent dix et mille deux cent cinquante.", "les nombres 24, 110 et 1250"),
    ("numbers", "Rappelle-moi le rendez-vous du douze octobre à quinze heures trente.",
     "rappelle-moi le rendez-vous du 12 octobre à 15 heures 30"),
    ("numbers", "La température du processeur est de soixante-sept degrés.", "la température du processeur est de 67 degrés"),
    ("control", "Le serveur fonctionne et les données restent locales.", "le serveur fonctionne et les données restent locales"),
    ("long", "Bonjour toytoy. Nous testons la mémoire Eidolon, les nombres vingt-quatre et cent dix, puis la caméra "
             "et la synthèse vocale. Le serveur fonctionne et les données restent locales.",
     "bonjour toytoy nous testons la mémoire eidolon les nombres 24 et 110 puis la caméra et la synthèse vocale "
     "le serveur fonctionne et les données restent locales"),
]
NUMBER_WORDS = {"vingt-quatre": "24", "cent dix": "110"}


def normalize(text):
    text = text.lower().replace("’", "'")
    text = re.sub(r"(?<=\d)[\s.  ](?=\d{3}\b)", "", text)          # 1 250 -> 1250
    text = re.sub(r"(\d+)\s*h\s*(\d+)", r"\1 heures \2", text)               # 15h30 -> 15 heures 30
    text = re.sub(r"[^\w'\- ]", " ", text)
    return text.split()


def wer(reference, hypothesis):
    ref, hyp = normalize(reference), normalize(hypothesis)
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        previous, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (r != h))
    return row[len(hyp)] / max(1, len(ref))


def to_16k(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        rate, frames = reader.getframerate(), reader.readframes(reader.getnframes())
    samples = array.array("h"); samples.frombytes(frames)
    count = int(len(samples) * 16000 / rate)
    out = array.array("h", (samples[min(len(samples) - 1, int(i * rate / 16000))] for i in range(count)))
    return out


def pcm_wav(samples):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(16000)
        writer.writeframes(samples.tobytes())
    return buffer.getvalue()


def noise(seconds, amplitude, seed):
    rnd = random.Random(seed)
    return array.array("h", (max(-32768, min(32767, int(rnd.gauss(0, amplitude)))) for _ in range(int(seconds * 16000))))


def mix(speech, amplitude, seed):
    hiss = noise(len(speech) / 16000, amplitude, seed)
    return array.array("h", (max(-32768, min(32767, a + b)) for a, b in zip(speech, hiss)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--comm", required=True, help="dossier eidolon-comm (venv/bin/piper, voices, models)")
    parser.add_argument("--voice", default="fr_FR-siwis-medium")
    parser.add_argument("--model", default="models/whisper-small")
    parser.add_argument("--out", default="bench-stt-vocabulary.json")
    args = parser.parse_args()
    sys.path.insert(0, args.src)
    from eidolon_core.comm_stt import DEFAULT_VOCABULARY, FasterWhisperSTT, SpeechToText, Vocabulary
    from eidolon_core.comm_tts import PiperTTS, TextToSpeech, chunks
    comm = Path(args.comm)
    tts = TextToSpeech(PiperTTS(str(comm / "venv/bin/piper"), str(comm / "voices")), default_voice=args.voice)
    cases = []
    for kind, text, reference in PHRASES:
        speech = array.array("h")
        for index in range(len(chunks(text))):
            speech.extend(to_16k(tts.synthesize("bench", text, index=index, rate=0.9)["wav"]))
        speech.extend(array.array("h", bytes(16000 * 2)))                   # 1 s of trailing silence
        cases.append({"kind": kind, "reference": reference, "pcm": speech})
        if kind in ("names", "control"):
            cases.append({"kind": kind + "+noise", "reference": reference, "pcm": mix(speech, 600, len(cases))})
    for seconds, amplitude, label in ((3, 0, "silence"), (5, 150, "low-noise"), (5, 800, "fan-noise"),
                                      (5, 2500, "loud-noise")):
        cases.append({"kind": label, "reference": "", "pcm": noise(seconds, amplitude, seconds * 1000 + amplitude)
                      if amplitude else array.array("h", bytes(seconds * 32000))})
    vocabulary = Vocabulary(DEFAULT_VOCABULARY["terms"], DEFAULT_VOCABULARY["replacements"])
    replace_only = Vocabulary((), DEFAULT_VOCABULARY["replacements"])
    model_dir = str(comm / args.model)
    configs = {
        "baseline": SpeechToText(FasterWhisperSTT(model_dir), time_budget=180, silence_rms=0, guard=False),
        "guards": SpeechToText(FasterWhisperSTT(model_dir), time_budget=180),
        "replace": SpeechToText(FasterWhisperSTT(model_dir), time_budget=180, vocabulary=replace_only),
        "prompt": SpeechToText(FasterWhisperSTT(model_dir, bias="prompt", vocabulary=vocabulary), time_budget=180),
        "hotwords": SpeechToText(FasterWhisperSTT(model_dir, bias="hotwords", vocabulary=vocabulary), time_budget=180),
        "prompt+vad": SpeechToText(FasterWhisperSTT(model_dir, bias="prompt", vad=True, vocabulary=vocabulary),
                                   time_budget=180),
    }
    results = {}
    for name, service in configs.items():
        rows = []
        for case in cases:
            started = time.monotonic()
            out = service.transcribe("bench", pcm_wav(case["pcm"]))
            row = {"kind": case["kind"], "transcript": out["text"], "seconds": round(time.monotonic() - started, 2),
                   "audio_s": round(len(case["pcm"]) / 16000, 1), "dropped": out.get("dropped_segments"),
                   "corrections": out.get("corrections", [])}
            if case["reference"]:
                words = normalize(out["text"])
                row.update(wer=round(wer(case["reference"], out["text"]), 3),
                           toytoy="toytoy" not in case["reference"] or "toytoy" in words,
                           eidolon="eidolon" not in case["reference"] or "eidolon" in words)
            else:
                row["invented_text"] = bool(out["text"])
            rows.append(row)
        spoken = [r for r in rows if "wer" in r]
        summary = {
            "mean_wer": round(sum(r["wer"] for r in spoken) / len(spoken), 3),
            "control_wer": round(sum(r["wer"] for r in spoken if r["kind"].startswith("control")) /
                                 max(1, sum(r["kind"].startswith("control") for r in spoken)), 3),
            "names_found": sum(r["toytoy"] and r["eidolon"] for r in spoken if "names" in r["kind"] or r["kind"] == "long"),
            "names_cases": sum("names" in r["kind"] or r["kind"] == "long" for r in spoken),
            "invented_on_silence_or_noise": sum(r.get("invented_text", False) for r in rows),
            "seconds_total": round(sum(r["seconds"] for r in rows), 1)}
        results[name] = {"summary": summary, "rows": rows}
        print(name, json.dumps(summary, ensure_ascii=False), flush=True)
        Path(args.out).write_text(json.dumps({"synthetic_audio": True, "voice": args.voice, "configs": results}, ensure_ascii=False, indent=1))
        service.engine._loaded = None
        gc.collect()
    Path(args.out).write_text(json.dumps({"synthetic_audio": True, "voice": args.voice, "configs": results},
                                         ensure_ascii=False, indent=1))
    print("saved", args.out)


if __name__ == "__main__":
    main()
