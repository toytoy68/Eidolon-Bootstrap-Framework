#!/usr/bin/env bash
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/run_vm100.sh
# Description : Entraîne et mesure le mot d'appel unique « eidolon » sur VM100 (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
# Autorisation de toytoy : 23/10/2026, 21 h 32. Décisions du 23/10 relayées par GPT.
# Isolé de la production : tout se passe sous $WAKE_WORKDIR, dans des conteneurs Docker
# nommés eidolon-wake-*, en priorité minimale, mis en pause dès que Eidolon sert
# (activity.json de Core) ou qu'un GPU chauffe. Aucun service n'est arrêté ni redémarré.
#
#   WAKE_ACTIVITY=/chemin/activity.json  ./run_vm100.sh            # CPU seulement (défaut)
#   WAKE_ACTIVITY=... WAKE_GPU=1         ./run_vm100.sh            # entraînement sur le GPU n° 1 seul
#   ./run_vm100.sh status                                          # où en est-on
#   ./run_vm100.sh bench [modèle.onnx]                             # banc seul (défaut : dernier modèle)
set -euo pipefail

KIT="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="${WAKE_WORKDIR:-$HOME/eidolon-validation/g296/wake}"
GENERATOR_URL="https://github.com/lfpoulain/wakeword-generator.git"
GENERATOR_COMMIT="1cc2c42"                     # PolyForm NC, outil externe non modifié
IMAGE="eidolon-wake-generator:1cc2c42"
ACTIVITY="${WAKE_ACTIVITY:-}"
GPU="${WAKE_GPU:-}"
MIN_FREE_GB=45
LOG="$WORKDIR/run.log"

say() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
fail() { say "ERREUR : $*"; exit 1; }

mkdir -p "$WORKDIR"
umask 077

if [ "${1:-}" = status ]; then
  docker ps -a --filter name=eidolon-wake- --format '{{.Names}} {{.Status}}' || true
  ls -la "$WORKDIR/models" 2>/dev/null || echo "aucun modèle produit"
  tail -n 20 "$LOG" 2>/dev/null || true
  exit 0
fi

# ---- Banc : clips tenus à l'écart et ~11 h de négatifs ---------------------------
bench() {
  local model="$1" base
  base="$(basename "$model" .onnx)"
  say "Banc : $base (balayage de seuils)."
  docker run --rm --cpu-shares 64 -v "$GEN:/workspace" -v "$KIT/..:/kit:ro" -v "$WORKDIR/models:/models" \
    -w /workspace --entrypoint python3.10 "$IMAGE" /kit/wake_training/bench_model.py \
    --model "/models/$base.onnx" \
    --melspec /opt/openWakeWord/openwakeword/resources/models/melspectrogram.onnx \
    --embedding /opt/openWakeWord/openwakeword/resources/models/embedding_model.onnx \
    --positive-dir output/eidolon/positive_test --negative-dir output/eidolon/negative_test \
    --negative-features data/features/validation_set_features.npy \
    --out "/models/$base.bench.json" | tee -a "$LOG"
  say "Banc : $WORKDIR/models/$base.bench.json. Rien n'est activé."
}

GEN="$WORKDIR/wakeword-generator"
if [ "${1:-}" = bench ]; then
  command -v docker >/dev/null || fail "Docker absent."
  model="${2:-$(ls -1t "$WORKDIR"/models/eidolon-*.onnx 2>/dev/null | head -1)}"
  [ -n "$model" ] && [ -f "$model" ] || fail "aucun modèle à mesurer sous $WORKDIR/models"
  case "$model" in "$WORKDIR/models/"*) ;; *) fail "le modèle doit être sous $WORKDIR/models" ;; esac
  bench "$model"
  exit 0
fi

# ---- Contrôles préalables ------------------------------------------------------
[ -n "$ACTIVITY" ] || fail "WAKE_ACTIVITY doit désigner activity.json de Core (pause quand Eidolon sert)."
[ -r "$ACTIVITY" ] || fail "activity.json illisible : $ACTIVITY"
command -v docker >/dev/null || fail "Docker absent."
command -v nvidia-smi >/dev/null || fail "nvidia-smi absent (sonde de température requise)."
free_gb=$(df -BG --output=avail "$WORKDIR" | tail -1 | tr -dc 0-9)
[ "$free_gb" -ge "$MIN_FREE_GB" ] || fail "Seulement ${free_gb} Go libres sous $WORKDIR (${MIN_FREE_GB} requis)."
if [ -n "$GPU" ]; then
  [[ "$GPU" =~ ^[0-9]$ ]] || fail "WAKE_GPU doit être un numéro de GPU."
  nvidia-smi -i "$GPU" >/dev/null || fail "GPU $GPU introuvable."
fi
say "Départ : dossier $WORKDIR, ${free_gb} Go libres, GPU ${GPU:-aucun (CPU)}."
nvidia-smi --query-gpu=index,name,memory.used,temperature.gpu --format=csv,noheader | tee -a "$LOG"

# ---- Outil externe, à un commit précis -------------------------------------------
if [ ! -d "$GEN/.git" ]; then
  git clone --quiet "$GENERATOR_URL" "$GEN"
fi
git -C "$GEN" fetch --quiet origin
git -C "$GEN" checkout --quiet "$GENERATOR_COMMIT"
[ "$(git -C "$GEN" rev-parse --short=7 HEAD)" = "$GENERATOR_COMMIT" ] || fail "commit inattendu de wakeword-generator"
[ -z "$(git -C "$GEN" status --porcelain --untracked-files=no)" ] || fail "wakeword-generator modifié localement : refus."
install -m 600 "$KIT/eidolon-training.yml" "$GEN/eidolon-training.yml"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  say "Construction de l'image (une fois)."
  nice -n 19 docker build --quiet -t "$IMAGE" "$GEN" | tee -a "$LOG"
fi

# ---- Étapes, chacune surveillée par le garde -----------------------------------
run_step() {
  local step="$1" name="eidolon-wake-$1" gpu=()
  if [ "$step" = train ] && [ -n "$GPU" ]; then gpu=(--gpus "device=$GPU"); fi
  docker rm "$name" >/dev/null 2>&1 || true            # conteneur terminé d'un essai précédent
  say "Étape $step : démarrage."
  docker run -d --name "$name" --cpu-shares 64 --shm-size=8g "${gpu[@]}" \
    -v "$GEN:/workspace" -w /workspace "$IMAGE" --config eidolon-training.yml "$step" >/dev/null
  nice -n 19 python3 "$KIT/guard.py" --container "$name" --activity "$ACTIVITY" >>"$LOG" 2>&1 &
  local guard=$!
  local code
  code=$(docker wait "$name")
  wait "$guard" || true
  docker logs --tail 40 "$name" >>"$LOG" 2>&1 || true
  docker rm "$name" >/dev/null 2>&1 || true
  [ "$code" = 0 ] || fail "étape $step : code $code (voir $LOG). Relancer reprend où l'outil s'était arrêté."
  say "Étape $step : terminée."
}
for step in prepare generate augment train; do run_step "$step"; done

# ---- Modèle, empreinte et provenance -------------------------------------------
MODEL="$GEN/output/eidolon.onnx"
[ -f "$MODEL" ] || fail "modèle absent : $MODEL"
mkdir -p "$WORKDIR/models"
stamp=$(date +%Y%m%d-%H%M%S)
install -m 600 "$MODEL" "$WORKDIR/models/eidolon-$stamp.onnx"
sha=$(sha256sum "$WORKDIR/models/eidolon-$stamp.onnx" | cut -d' ' -f1)
cat > "$WORKDIR/models/eidolon-$stamp.provenance.json" <<JSON
{"schema": "eidolon-wake-model-provenance/1", "model": "eidolon-$stamp.onnx", "sha256": "$sha",
 "phrase": "eidolon", "generator": "lfpoulain/wakeword-generator@$GENERATOR_COMMIT (PolyForm Noncommercial, unmodified)",
 "config_sha256": "$(sha256sum "$KIT/eidolon-training.yml" | cut -d' ' -f1)",
 "image": "$(docker image inspect -f '{{.Id}}' "$IMAGE")", "gpu": "${GPU:-cpu}",
 "licence": "CC BY-NC-SA 4.0 by inheritance (study only, see docs/LICENCES-VOIX-G296.md)",
 "activated": false, "trained_at": "$(date -Is)"}
JSON
say "Modèle : $WORKDIR/models/eidolon-$stamp.onnx (sha256 $sha)."

bench "$WORKDIR/models/eidolon-$stamp.onnx"
