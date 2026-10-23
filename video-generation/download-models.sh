#!/usr/bin/env bash

# ==========================================================
# Projet       : Eidolon Bootstrap Framework
# Script       : video-generation/download-models.sh
# Version      : 0.1.0-alpha
# Description  : Téléchargement des modèles Wan 2.2 pour
#                ComfyUI, selon la VRAM disponible.
#
# Usage        : download-models.sh <profil> [<profil> ...]
#
# Profils      :
#   5b       Wan 2.2 TI2V 5B fp16 (~10 Go)  — V100 16 Go
#   14b      Wan 2.2 T2V 14B GGUF Q4_K_M (2 × ~9,7 Go) — V100 16 Go
#   14b-q8   Wan 2.2 T2V 14B GGUF Q8_0 (2 × ~15,4 Go) — V100 32 Go
#   lightx2v LoRA d'accélération 4 étapes pour le 14B
#
# Variables    :
#   COMFY_DIR  Répertoire ComfyUI (défaut /opt/eidolon/comfyui)
#   HF_TOKEN   Jeton Hugging Face (facultatif)
#   QUANT      Quantification du profil 14b (défaut Q4_K_M)
# ==========================================================

set -euo pipefail

readonly COMFY_DIR="${COMFY_DIR:-/opt/eidolon/comfyui}"
readonly MODELS="$COMFY_DIR/models"
readonly QUANT="${QUANT:-Q4_K_M}"

readonly HF="https://huggingface.co"
readonly REPACK="$HF/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files"
readonly GGUF="$HF/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main"

ok()    { echo "[OK] $1"; }
info()  { echo "[INFO] $1"; }
error() { echo "[ERREUR] $1"; exit 1; }

usage() {
    sed -n '/^# Usage/,/^# =====/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
    exit 1
}

# fetch <url> <dossier> [nom]
fetch() {
    local URL="$1" DIR="$MODELS/$2" NAME="${3:-${1##*/}}"
    local DEST="$DIR/$NAME"
    local AUTH=()

    mkdir -p "$DIR"

    if [[ -s "$DEST" ]]; then
        ok "Déjà présent : $2/$NAME"
        return 0
    fi

    [[ -n "${HF_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer $HF_TOKEN")

    info "Téléchargement : $2/$NAME"
    curl -fL --retry 5 --retry-delay 5 -C - "${AUTH[@]}" \
        -o "$DEST.part" "$URL" \
        || error "Échec du téléchargement de $URL"
    mv "$DEST.part" "$DEST"
    ok "$2/$NAME"
}

common_text_encoder() {
    fetch "$REPACK/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" text_encoders
}

profile_5b() {
    common_text_encoder
    fetch "$REPACK/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" diffusion_models
    fetch "$REPACK/vae/wan2.2_vae.safetensors" vae
}

profile_14b() {
    local Q="$1"
    common_text_encoder
    fetch "$GGUF/HighNoise/Wan2.2-T2V-A14B-HighNoise-$Q.gguf" unet
    fetch "$GGUF/LowNoise/Wan2.2-T2V-A14B-LowNoise-$Q.gguf" unet
    fetch "$REPACK/vae/wan_2.1_vae.safetensors" vae
}

profile_lightx2v() {
    fetch "$REPACK/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors" loras
    fetch "$REPACK/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors" loras
}

main() {
    [[ $# -ge 1 ]] || usage
    [[ -d "$COMFY_DIR" ]] || error "$COMFY_DIR introuvable : exécuter install-comfyui.sh d'abord."
    command -v curl >/dev/null || error "curl est requis."

    local P
    for P in "$@"; do
        case "$P" in
            5b)       profile_5b ;;
            14b)      profile_14b "$QUANT" ;;
            14b-q8)   profile_14b Q8_0 ;;
            lightx2v) profile_lightx2v ;;
            *)        usage ;;
        esac
    done

    echo
    ok "Modèles prêts dans $MODELS"
    info "Si ComfyUI tourne déjà, rafraîchir l'interface (touche R) pour voir les nouveaux fichiers."
}

main "$@"
