#!/usr/bin/env bash

# ==========================================================
# Projet       : Eidolon Bootstrap Framework
# Script       : video-generation/install-comfyui.sh
# Version      : 0.1.0-alpha
# Description  : Installation de ComfyUI pour la génération
#                vidéo locale (Wan 2.2) sur GPU NVIDIA Volta
#                (Tesla V100, sm_70).
# Statut       : En développement
# Prérequis    : 01-system, 02-nvidia (pilote fonctionnel)
# ==========================================================

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------
# Composant
# ----------------------------------------------------------

readonly COMPONENT_NAME="video-generation"
readonly COMPONENT_TITLE="Installation de ComfyUI (génération vidéo)"
readonly COMPONENT_VERSION="0.1.0-alpha"

# ----------------------------------------------------------
# Configuration (surchargeable par variables d'environnement)
# ----------------------------------------------------------

readonly PRIMARY_USER="${PRIMARY_USER:-toytoy}"

readonly EIDOLON_HOME="${EIDOLON_HOME:-/opt/eidolon}"
readonly COMFY_DIR="${COMFY_DIR:-$EIDOLON_HOME/comfyui}"
readonly VENV_DIR="$COMFY_DIR/venv"
readonly LOGFILE="${LOGFILE:-/var/log/eidolon-comfyui-install.log}"

readonly COMFY_REPO="https://github.com/comfyanonymous/ComfyUI.git"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
# Révisions fixées, sans mise à jour implicite au prochain lancement.
# shellcheck source=sources.lock
source "$SCRIPT_DIR/sources.lock"

# Volta (sm_70) : PyTorch 2.14 est la dernière version publiée
# avec des binaires Volta, sur l'index CUDA 12.6.
# CUDA 13 ne prend plus en charge les GPU antérieurs à Turing.
readonly TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu126}"
readonly TORCH_SPEC="torch==2.14.0+cu126"

readonly COMFY_PORT="${COMFY_PORT:-8188}"
readonly COMFY_LISTEN="${COMFY_LISTEN:-0.0.0.0}"
readonly COMFY_GPUS="${COMFY_GPUS:-0}"
readonly SERVICE_NAME="eidolon-comfyui"

readonly APT_PACKAGES=(
    git
    sudo
    python3
    python3-venv
    python3-dev
    build-essential
    ffmpeg
    curl
)

# Nœuds personnalisés : nom|dépôt|révision
readonly CUSTOM_NODES=(
    "ComfyUI-Manager|https://github.com/Comfy-Org/ComfyUI-Manager.git|$MANAGER_REV"
    "ComfyUI-GGUF|https://github.com/city96/ComfyUI-GGUF.git|$GGUF_REV"
    "ComfyUI-VideoHelperSuite|https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git|$VHS_REV"
    "ComfyUI-MultiGPU|https://github.com/pollockjj/ComfyUI-MultiGPU.git|$MULTIGPU_REV"
)

# ----------------------------------------------------------
# Fonctions d'affichage
# ----------------------------------------------------------

separator() { echo "========================================================="; }

title() {
    echo
    separator
    echo "$1"
    separator
}

ok()      { echo "[OK] $1"; }
info()    { echo "[INFO] $1"; }
warning() { echo "[ATTENTION] $1"; }

error() {
    echo
    echo "[ERREUR] $1"
    echo
    echo "L'installation est interrompue. Journal : $LOGFILE"
    exit 1
}

run() {
    local MESSAGE="$1"
    shift
    info "$MESSAGE"
    if "$@" >>"$LOGFILE" 2>&1; then
        ok "$MESSAGE"
    else
        error "Échec : $MESSAGE"
    fi
}

# Exécute une commande en tant qu'utilisateur principal
as_user() {
    sudo -u "$PRIMARY_USER" -H "$@"
}

# ----------------------------------------------------------
# Fonctions de vérification
# ----------------------------------------------------------

check_root() {
    [[ $EUID -eq 0 ]] || error "Ce script doit être exécuté en tant que root."
    ok "Exécution en tant que root"
}

check_user() {
    id "$PRIMARY_USER" >/dev/null 2>&1 \
        || error "L'utilisateur '$PRIMARY_USER' n'existe pas (exécuter 01-system d'abord)."
    ok "Utilisateur '$PRIMARY_USER' présent"
}

check_nvidia() {
    command -v nvidia-smi >/dev/null 2>&1 \
        || error "nvidia-smi introuvable : exécuter 02-nvidia d'abord."

    nvidia-smi >/dev/null 2>&1 \
        || error "nvidia-smi ne répond pas : pilote NVIDIA non fonctionnel."

    ok "Pilote NVIDIA fonctionnel"

    local CAPS
    CAPS="$(nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader 2>/dev/null || true)"

    if [[ -n "$CAPS" ]]; then
        while IFS= read -r LINE; do
            info "GPU détecté : $LINE"
        done <<<"$CAPS"
    fi

    if ! grep -q "7\.0" <<<"$CAPS"; then
        warning "Aucun GPU Volta (7.0) détecté : la configuration PyTorch cu126/<2.15 reste valide, mais n'est pas optimale pour un GPU plus récent."
    fi
}

check_network() {
    curl -fsS -m 10 -o /dev/null https://github.com \
        || error "GitHub injoignable : vérifier la connexion réseau."
    ok "Accès réseau à GitHub"
}

# ----------------------------------------------------------
# Fonctions d'installation
# ----------------------------------------------------------

install_packages() {
    run "Mise à jour de l'index APT" apt-get update
    run "Installation des paquets système" apt-get install -y "${APT_PACKAGES[@]}"
}

create_directories() {
    mkdir -p "$EIDOLON_HOME"
    if [[ ! -d "$COMFY_DIR" ]]; then
        mkdir -p "$COMFY_DIR"
    fi
    chown "$PRIMARY_USER":"$PRIMARY_USER" "$COMFY_DIR"
    ok "Répertoire $COMFY_DIR prêt"
}

install_comfyui() {
    if [[ -d "$COMFY_DIR/.git" ]]; then
        ok "Dépôt ComfyUI présent"
    elif [[ -z "$(ls -A "$COMFY_DIR" 2>/dev/null)" ]]; then
        run "Clonage de ComfyUI" as_user git clone "$COMFY_REPO" "$COMFY_DIR"
    else
        error "$COMFY_DIR n'est pas vide et n'est pas un dépôt ComfyUI."
    fi
    pin_checkout "$COMFY_DIR" "$COMFY_REV"
}

pin_checkout() {
    local DIR="$1" REV="$2"
    [[ "$REV" =~ ^[0-9a-f]{40}$ ]] || error "Révision Git invalide : $REV"
    [[ -z "$(as_user git -C "$DIR" status --porcelain --untracked-files=no)" ]] \
        || error "Modifications locales dans $DIR : sauvegarder avant installation."
    run "Récupération de $REV" as_user git -C "$DIR" fetch origin "$REV"
    run "Sélection de $REV" as_user git -C "$DIR" checkout --detach "$REV"
}

install_venv() {
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        run "Création de l'environnement Python" as_user python3 -m venv "$VENV_DIR"
    else
        ok "Environnement Python déjà présent"
    fi
    run "Mise à jour de pip" as_user "$VENV_DIR/bin/pip" install --upgrade pip wheel
}

install_torch() {
    run "Installation de PyTorch ($TORCH_SPEC, $TORCH_INDEX)" \
        as_user "$VENV_DIR/bin/pip" install "$TORCH_SPEC" torchvision torchaudio \
        --index-url "$TORCH_INDEX"

    # Verrouille torch/torchvision/torchaudio : les dépendances de
    # ComfyUI ne doivent pas les remplacer par une version CUDA 13.
    as_user "$VENV_DIR/bin/pip" freeze \
        | grep -E "^(torch|torchvision|torchaudio)==" \
        | as_user tee "$COMFY_DIR/eidolon-constraints.txt" >/dev/null

    # S'applique aussi aux futurs pip de ce venv, dont ceux du Manager.
    as_user "$VENV_DIR/bin/pip" config --site set global.constraint "$COMFY_DIR/eidolon-constraints.txt"
    as_user "$VENV_DIR/bin/pip" config --site set global.extra-index-url "$TORCH_INDEX"

    ok "Contraintes PyTorch écrites dans eidolon-constraints.txt"
}

install_requirements() {
    run "Installation des dépendances ComfyUI" \
        as_user "$VENV_DIR/bin/pip" install \
        -r "$COMFY_DIR/requirements.txt" \
        -c "$COMFY_DIR/eidolon-constraints.txt"
}

install_custom_nodes() {
    local ENTRY NAME REPO DEST REV REST
    for ENTRY in "${CUSTOM_NODES[@]}"; do
        NAME="${ENTRY%%|*}"
        REST="${ENTRY#*|}"
        REPO="${REST%%|*}"
        REV="${REST##*|}"
        DEST="$COMFY_DIR/custom_nodes/$NAME"

        if [[ -d "$DEST/.git" ]]; then
            ok "Dépôt $NAME présent"
        else
            run "Clonage de $NAME" as_user git clone "$REPO" "$DEST"
        fi
        pin_checkout "$DEST" "$REV"

        if [[ -f "$DEST/requirements.txt" ]]; then
            run "Dépendances de $NAME" \
                as_user "$VENV_DIR/bin/pip" install \
                -r "$DEST/requirements.txt" \
                -c "$COMFY_DIR/eidolon-constraints.txt"
        fi
    done
}

create_model_directories() {
    local DIR
    for DIR in diffusion_models unet text_encoders vae loras; do
        as_user mkdir -p "$COMFY_DIR/models/$DIR"
    done
    ok "Répertoires de modèles prêts"
}

configure_service() {
    cat >"/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Eidolon - ComfyUI (génération vidéo locale)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$PRIMARY_USER
WorkingDirectory=$COMFY_DIR
Environment=CUDA_DEVICE_ORDER=PCI_BUS_ID
Environment=CUDA_VISIBLE_DEVICES=$COMFY_GPUS
Environment=PIP_CONSTRAINT=$COMFY_DIR/eidolon-constraints.txt
Environment=PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ExecStart=$VENV_DIR/bin/python main.py --listen $COMFY_LISTEN --port $COMFY_PORT --force-fp16 --preview-method auto
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    run "Rechargement de systemd" systemctl daemon-reload
    run "Activation du service $SERVICE_NAME" systemctl enable "$SERVICE_NAME"
}

# ----------------------------------------------------------
# Fonctions de validation
# ----------------------------------------------------------

validate_torch() {
    local OUT
    OUT="$(as_user env CUDA_VISIBLE_DEVICES="$COMFY_GPUS" "$VENV_DIR/bin/python" - <<'PY' 2>&1
import torch
assert torch.cuda.is_available(), "CUDA indisponible"
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("archs", " ".join(torch.cuda.get_arch_list()))
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print(f"gpu{i}", p.name, f"sm_{p.major}{p.minor}", f"{p.total_memory // 2**20} Mo")
    if (p.major, p.minor) == (7, 0):
        assert "sm_70" in torch.cuda.get_arch_list(), "Build sans sm_70"
    x = torch.randn(1024, 1024, device=f"cuda:{i}", dtype=torch.float16)
    y = x @ x
    assert torch.isfinite(y).all().item(), f"Résultat fp16 non fini sur GPU {i}"
    assert y.abs().sum().item() > 0, f"Résultat fp16 nul sur GPU {i}"
    torch.cuda.synchronize(i)
    print(f"gpu{i} fp16 matmul ok")
    del x, y
PY
)" || error "Validation PyTorch impossible :
$OUT"

    while IFS= read -r LINE; do info "$LINE"; done <<<"$OUT"

    local HAS_VOLTA ARCH_VOLTA
    HAS_VOLTA="$(grep -c '^gpu.* sm_70 ' <<<"$OUT" || true)"
    ARCH_VOLTA="$(grep '^archs' <<<"$OUT" | grep -c 'sm_70' || true)"

    if [[ "$HAS_VOLTA" -gt 0 && "$ARCH_VOLTA" -eq 0 ]]; then
        error "Ce build PyTorch ne contient pas sm_70 : les V100 ne seront pas utilisables."
    fi

    ok "PyTorch accède au GPU en fp16"
}

# ----------------------------------------------------------
# Résumé
# ----------------------------------------------------------

summary() {
    title "Résumé"
    ok "ComfyUI installé dans $COMFY_DIR"
    ok "Service systemd : $SERVICE_NAME (non démarré)"
    echo
    info "Étapes suivantes :"
    echo "  1. Télécharger les modèles :"
    echo "       sudo -u $PRIMARY_USER bash $(dirname "$(readlink -f "$0")")/download-models.sh 5b"
    echo "  2. Démarrer ComfyUI :"
    echo "       systemctl start $SERVICE_NAME"
    echo "  3. Interface : http://<ip-du-serveur>:$COMFY_PORT"
    echo
}

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

main() {
    : >"$LOGFILE" 2>/dev/null || true

    title "$COMPONENT_TITLE ($COMPONENT_NAME $COMPONENT_VERSION)"

    title "Vérifications"
    check_root
    check_user
    check_nvidia

    title "Installation"
    install_packages
    check_network
    create_directories
    install_comfyui
    install_venv
    install_torch
    install_requirements
    install_custom_nodes
    create_model_directories
    run "Cohérence des dépendances" as_user "$VENV_DIR/bin/pip" check

    title "Validation"
    validate_torch

    # Aucun service créé/activé si les validations précédentes échouent.
    configure_service

    summary
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi

