#!/usr/bin/env bash

# ==========================================================
# Projet      : Eidolon Bootstrap Framework
# Script      : 02-nvidia.sh
# Version     : 1.5.0-alpha
# Description : Installation des pilotes NVIDIA (Debian 13)
# ==========================================================

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------
# Fonctions
# ----------------------------------------------------------

separator() {
    echo "========================================================="
}

title() {
    echo
    separator
    echo "$1"
    separator
}

ok() {
    echo "[OK] $1"
}

info() {
    echo "[INFO] $1"
}

warning() {
    echo "[ATTENTION] $1"
}

error() {
    echo
    echo "[ERREUR] $1"
    echo
    echo "Le bootstrap est interrompu."
    exit 1
}

run() {

    local MESSAGE="$1"
    shift

    echo
    info "$MESSAGE"

    if "$@"; then

        ok "$MESSAGE"
        return 0

    else

        error "Échec : $MESSAGE"

    fi

}

# ----------------------------------------------------------
# Vérification Root
# ----------------------------------------------------------

[[ $EUID -eq 0 ]] || error "Ce script doit être exécuté en tant que root."

# ----------------------------------------------------------
# Accueil
# ----------------------------------------------------------

clear

echo
echo "#########################################################"
echo "#                                                       #"
echo "#          Eidolon Bootstrap Framework                  #"
echo "#                                                       #"
echo "#                 Script 02 - NVIDIA                    #"
echo "#                                                       #"
echo "#########################################################"
echo
echo "Ce script va :"
echo
echo "  • Vérifier le système"
echo "  • Configurer les dépôts Debian"
echo "  • Installer les dépendances NVIDIA"
echo "  • Installer le pilote propriétaire"
echo "  • Préparer le système pour CUDA"
echo
read -rp "Continuer ? [Entrée] "

# ----------------------------------------------------------
# Vérification Debian
# ----------------------------------------------------------

title "Vérification du système"

source /etc/os-release

[[ "$ID" == "debian" ]] || error "Ce script est prévu pour Debian."

[[ "$VERSION_ID" == "13" ]] || \
    error "Ce script est prévu pour Debian 13."

ok "Debian $VERSION_ID détecté"

# ----------------------------------------------------------
# Vérification Internet
# ----------------------------------------------------------

title "Connexion Internet"

ping -c1 deb.debian.org >/dev/null 2>&1 || \
    error "Connexion Internet indisponible."

ok "Connexion Internet disponible"

# ----------------------------------------------------------
# Détection GPU
# ----------------------------------------------------------

title "Détection du GPU NVIDIA"

GPU_INFO=$(lspci -nn | grep -i nvidia || true)

[[ -n "$GPU_INFO" ]] || error "Aucun GPU NVIDIA détecté."

echo
echo "$GPU_INFO"
echo

ok "GPU NVIDIA détecté"

# ----------------------------------------------------------
# Vérification d'une installation existante
# ----------------------------------------------------------

title "Vérification du pilote"

if nvidia-smi >/dev/null 2>&1; then

    warning "Le pilote NVIDIA semble déjà installé."

    DRIVER_VERSION=$(nvidia-smi \
        --query-gpu=driver_version \
        --format=csv,noheader \
        | head -1)

    info "Version détectée : $DRIVER_VERSION"

fi

# ----------------------------------------------------------
# Configuration des dépôts Debian
# ----------------------------------------------------------

title "Configuration des dépôts Debian"

if [[ -f /etc/apt/sources.list ]]; then

    [[ -f /etc/apt/sources.list.bak ]] || \
        cp /etc/apt/sources.list /etc/apt/sources.list.bak

    sed -i \
        -e 's/\bmain\b/main contrib non-free non-free-firmware/g' \
        /etc/apt/sources.list

    ok "sources.list configuré"

fi

if [[ -f /etc/apt/sources.list.d/debian.sources ]]; then

    [[ -f /etc/apt/sources.list.d/debian.sources.bak ]] || \
        cp /etc/apt/sources.list.d/debian.sources \
           /etc/apt/sources.list.d/debian.sources.bak

    sed -i \
        's/^Components: main$/Components: main contrib non-free non-free-firmware/' \
        /etc/apt/sources.list.d/debian.sources

    ok "debian.sources configuré"

fi

run "Mise à jour de l'index des paquets" \
    apt update

# ----------------------------------------------------------
# Installation des dépendances
# ----------------------------------------------------------

title "Installation des dépendances"

run "Installation des dépendances" \
    apt install -y \
        linux-headers-amd64 \
        dkms \
        build-essential \
        firmware-misc-nonfree \
        psmisc

# ----------------------------------------------------------
# Désactivation de Nouveau
# ----------------------------------------------------------

title "Configuration des modules du noyau"

cat >/etc/modprobe.d/blacklist-nouveau.conf <<EOF
blacklist nouveau
options nouveau modeset=0
EOF

ok "Pilote Nouveau désactivé"

# ----------------------------------------------------------
# Installation du pilote NVIDIA
# ----------------------------------------------------------

title "Installation du pilote NVIDIA"

run "Installation du pilote NVIDIA" \
    apt install -y \
        nvidia-driver \
        nvidia-kernel-dkms

# ----------------------------------------------------------
# Mise à jour de l'initramfs
# ----------------------------------------------------------

title "Mise à jour de l'initramfs"

run "Mise à jour de l'initramfs" \
    update-initramfs -u

# ----------------------------------------------------------
# Chargement du module NVIDIA
# ----------------------------------------------------------

title "Chargement du module NVIDIA"

info "Chargement du module NVIDIA..."

if modprobe nvidia 2>/dev/null; then

    ok "Module NVIDIA chargé"

    if nvidia-smi >/dev/null 2>&1; then

        echo
        nvidia-smi

        DRIVER_VERSION=$(
            nvidia-smi \
                --query-gpu=driver_version \
                --format=csv,noheader \
                | head -1
        )

        CUDA_VERSION=$(
            nvidia-smi \
                | awk '/CUDA Version/ {print $9}'
        )

        echo
        ok "Version du pilote : $DRIVER_VERSION"

        [[ -n "$CUDA_VERSION" ]] && \
            ok "Version CUDA : $CUDA_VERSION"

    else

        warning "Le pilote est installé mais nvidia-smi ne répond pas encore."
        warning "Le redémarrage finalisera probablement l'installation."

    fi

else

    warning "Le module NVIDIA n'a pas pu être chargé."
    warning "C'est normal après une première installation."
    warning "Le redémarrage finalisera probablement l'installation."

fi

# ----------------------------------------------------------
# Résumé
# ----------------------------------------------------------

title "Bootstrap NVIDIA terminé"

echo
ok "Installation du pilote NVIDIA terminée."
echo

separator
echo "Vérification après redémarrage :"
separator
echo
echo "    nvidia-smi"
echo
echo "Si votre Tesla V100 apparaît correctement,"
echo "vous pourrez poursuivre avec :"
echo
echo "    bash 03-docker.sh"
echo

# ----------------------------------------------------------
# Confirmation du redémarrage
# ----------------------------------------------------------

separator

read -rp "Redémarrer maintenant ? [O/n] : " REP

separator

case "$REP" in

    ""|o|O|y|Y)

        echo
        info "Redémarrage du système..."
        reboot
        ;;

    *)

        echo
        warning "Redémarrage annulé."
        info "N'oubliez pas de redémarrer avant d'exécuter 03-docker.sh"
        ;;

esac