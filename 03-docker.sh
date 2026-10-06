#!/usr/bin/env bash

# ==========================================================
# Projet       : Eidolon Bootstrap Framework
# Script       : 03-docker.sh
# Version      : 1.0.0-alpha
# Description  : Installation de Docker CE et du runtime
#                NVIDIA pour Eidolon Core.
# Statut       : En développement
# ==========================================================

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------
# Eidolon Core Technologies
# ----------------------------------------------------------

readonly COMPANY_NAME="Eidolon Core Technologies"
readonly COMPANY_SHORT="ECT"
readonly COMPANY_MOTTO="Local AI • Modular • Reliable • Reproducible"

# ----------------------------------------------------------
# Framework
# ----------------------------------------------------------

readonly FRAMEWORK_NAME="Eidolon Bootstrap Framework"
readonly FRAMEWORK_VERSION="1.0.0"
readonly FRAMEWORK_STANDARD="Bootstrap Standards v1.0.0"

# ----------------------------------------------------------
# Composant
# ----------------------------------------------------------

readonly COMPONENT_NAME="03-docker"
readonly COMPONENT_TITLE="Installation de Docker"
readonly COMPONENT_VERSION="1.0.0-alpha"
readonly COMPONENT_STATUS="En développement"
readonly COMPONENT_NEXT="Eidolon Core"

# ----------------------------------------------------------
# Identité du nœud Eidolon
# ----------------------------------------------------------

readonly HOSTNAME="Eidolon-Core-Alpha"
readonly DOMAIN="local"

readonly PRIMARY_USER="toytoy"

readonly TIMEZONE="Europe/Paris"
readonly LOCALE="fr_FR.UTF-8"

# ----------------------------------------------------------
# Répertoires
# ----------------------------------------------------------

readonly EIDOLON_HOME="/opt/eidolon"
readonly TEMP_DIR="/tmp/eidolon-bootstrap"
readonly LOGFILE="/var/log/eidolon-bootstrap.log"

# ----------------------------------------------------------
# Services
# ----------------------------------------------------------

readonly DOCKER_SERVICE="docker"

# ----------------------------------------------------------
# Outils requis
# ----------------------------------------------------------

readonly REQUIRED_COMMANDS=(
    apt-get
    systemctl
)

# ----------------------------------------------------------
# Paquets requis
# ----------------------------------------------------------

readonly REQUIRED_PACKAGES=(
    ca-certificates
    curl
    gnupg
)

# ----------------------------------------------------------
# Docker
# ----------------------------------------------------------

readonly DOCKER_DAEMON_CONFIG="/etc/docker/daemon.json"

readonly DOCKER_KEYRING_DIR="/etc/apt/keyrings"
readonly DOCKER_GPG_URL="https://download.docker.com/linux/debian/gpg"
readonly DOCKER_GPG_KEY="$DOCKER_KEYRING_DIR/docker.asc"
readonly DOCKER_REPOSITORY_FILE="/etc/apt/sources.list.d/docker.list"

readonly DOCKER_PACKAGES=(
    docker-ce
    docker-ce-cli
    containerd.io
    docker-buildx-plugin
    docker-compose-plugin
)

# ----------------------------------------------------------
# NVIDIA Container Toolkit
# ----------------------------------------------------------

readonly NVIDIA_GPG_URL="https://nvidia.github.io/libnvidia-container/gpgkey"

readonly NVIDIA_REPOSITORY_URL="https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list"

readonly NVIDIA_GPG_KEY="$DOCKER_KEYRING_DIR/nvidia-container-toolkit-keyring.gpg"

readonly NVIDIA_REPOSITORY_FILE="/etc/apt/sources.list.d/nvidia-container-toolkit.list"

readonly NVIDIA_PACKAGES=(
    nvidia-container-toolkit
)

# ----------------------------------------------------------
# Validation GPU
# ----------------------------------------------------------

readonly CUDA_TEST_IMAGE="nvidia/cuda:12.9.1-base-ubuntu24.04"

# ----------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------

separator() {
    echo "========================================================="
}

header() {

    clear

    echo
    echo "#########################################################"
    echo "#                                                       #"
    echo "#          Eidolon Bootstrap Framework                  #"
    echo "#                                                       #"
    echo "#                 Script 03 - Docker                    #"
    echo "#                                                       #"
    echo "#########################################################"
    echo
    echo "Ce script va :"
    echo
    echo "  • Vérifier le pilote NVIDIA"
    echo "  • Installer Docker CE"
    echo "  • Installer NVIDIA Container Toolkit"
    echo "  • Configurer le runtime NVIDIA"
    echo "  • Valider le GPU depuis Docker"
    echo
    echo "Machine            : $(hostname)"
    echo "Utilisateur cible  : ${PRIMARY_USER}"
    echo "Date               : $(date)"
    echo

    read -rp "Continuer ? [Entrée] "
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

check_command() {
    command -v "$1" >/dev/null 2>&1
}

cleanup() {

    rm -rf "$TEMP_DIR" 2>/dev/null || true

}


# ----------------------------------------------------------
# SECTION 01
# Vérification Root
# ----------------------------------------------------------

section_check_root() {

    title "Vérification des privilèges"

    if [[ $EUID -ne 0 ]]; then
        error "Ce script nécessite des privilèges administrateur (root)."
    fi

    ok "Privilèges root confirmés"

}

# ----------------------------------------------------------
# SECTION 02
# Vérification NVIDIA
# ----------------------------------------------------------

section_check_nvidia() {

    title "Vérification du GPU NVIDIA"

    info "Recherche d'un GPU NVIDIA..."

    if ! lspci -nn | grep -Fqi "NVIDIA"; then
        error "Aucun GPU NVIDIA détecté."
    fi

    ok "GPU NVIDIA détecté"

    info "Validation du fonctionnement du pilote NVIDIA..."

    if ! check_command nvidia-smi; then
        error "La commande 'nvidia-smi' est introuvable."
    fi

    if ! nvidia-smi -L >/dev/null 2>"$TEMP_DIR/nvidia.err"; then
        warning "Sortie de nvidia-smi :"
        [[ -s "$TEMP_DIR/nvidia.err" ]] && cat "$TEMP_DIR/nvidia.err" || true
        error "Le pilote NVIDIA n'est pas opérationnel."
    fi

    ok "Pilote NVIDIA opérationnel"

}

# ----------------------------------------------------------
# SECTION 03
# Vérification Internet
# ----------------------------------------------------------

section_check_network() {

    title "Vérification de la connectivité Internet"

    info "Validation de la résolution DNS..."

    if ! getent hosts deb.debian.org >/dev/null 2>&1; then
        error "La résolution DNS ne fonctionne pas."
    fi

    ok "Résolution DNS opérationnelle"

    info "Validation de l'accès aux dépôts APT..."

    if ! apt-get update >"$TEMP_DIR/apt.out" 2>"$TEMP_DIR/apt.err"; then

        [[ -s "$TEMP_DIR/apt.out" ]] && cat "$TEMP_DIR/apt.out" || true
        [[ -s "$TEMP_DIR/apt.err" ]] && cat "$TEMP_DIR/apt.err" || true

        error "La mise à jour des dépôts APT a échoué."

    fi

    ok "Mise à jour des dépôts APT réussie"

}

# ----------------------------------------------------------
# SECTION 04
# Validation des dépendances
# ----------------------------------------------------------

section_prechecks() {

    title "Validation des dépendances"

    info "Validation des outils requis..."

    local cmd

    for cmd in "${REQUIRED_COMMANDS[@]}"; do

        if ! check_command "$cmd"; then
            error "Commande '$cmd' introuvable."
        fi

    done

    ok "Tous les outils requis sont disponibles"

}

# ----------------------------------------------------------
# SECTION 05
# Installation des dépendances
# ----------------------------------------------------------

section_install_dependencies() {

    title "Installation des dépendances"

    info "Installation des paquets requis..."

    if ! apt-get install --yes "${REQUIRED_PACKAGES[@]}" \
        >"$TEMP_DIR/dependencies.out" \
        2>"$TEMP_DIR/dependencies.err"; then

        warning "Diagnostic de apt-get :"

        [[ -s "$TEMP_DIR/dependencies.out" ]] && cat "$TEMP_DIR/dependencies.out" || true
        [[ -s "$TEMP_DIR/dependencies.err" ]] && cat "$TEMP_DIR/dependencies.err" || true

        error "L'installation des dépendances a échoué."

    fi

    ok "Paquets requis installés"

}

# ----------------------------------------------------------
# SECTION 06
# Installation de Docker CE
# ----------------------------------------------------------

section_install_docker() {

    title "Installation de Docker CE"

    info "Création du répertoire des clés APT..."

    install -m 0755 -d "$DOCKER_KEYRING_DIR" \
        || error "Impossible de créer le répertoire '$DOCKER_KEYRING_DIR'."

    ok "Répertoire des clés créé"

    info "Téléchargement de la clé GPG Docker..."

    if ! curl -fsSL "$DOCKER_GPG_URL" \
        -o "$DOCKER_GPG_KEY"; then
        error "Impossible de télécharger la clé GPG Docker."
    fi

    [[ -s "$DOCKER_GPG_KEY" ]] \
        || error "La clé GPG Docker est vide."

    chmod a+r "$DOCKER_GPG_KEY" \
        || error "Impossible de modifier les permissions de la clé GPG Docker."
    ok "Clé GPG Docker installée"

    info "Configuration du dépôt Docker..."

    local architecture=""
    local codename=""

    architecture="$(dpkg --print-architecture)"
    codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"

    [[ -n "$codename" ]] \
        || error "Impossible de déterminer la version de Debian."

    cat >"$DOCKER_REPOSITORY_FILE" <<EOF
deb [arch=${architecture} signed-by=${DOCKER_GPG_KEY}] https://download.docker.com/linux/debian ${codename} stable
EOF

    [[ -s "$DOCKER_REPOSITORY_FILE" ]] \
        || error "Le dépôt Docker n'a pas été créé."

    ok "Dépôt Docker configuré"

    info "Actualisation des dépôts APT..."

    if ! apt-get update \
        >"$TEMP_DIR/docker-update.out" \
        2>"$TEMP_DIR/docker-update.err"; then

        warning "Diagnostic de apt-get :"

        [[ -s "$TEMP_DIR/docker-update.out" ]] && cat "$TEMP_DIR/docker-update.out" || true
        [[ -s "$TEMP_DIR/docker-update.err" ]] && cat "$TEMP_DIR/docker-update.err" || true

        error "Impossible de mettre à jour les dépôts Docker."

    fi

    ok "Dépôts Docker mis à jour"

    info "Installation de Docker CE..."

    if ! apt-get install --yes "${DOCKER_PACKAGES[@]}" \
        >"$TEMP_DIR/docker-install.out" \
        2>"$TEMP_DIR/docker-install.err"; then

        warning "Diagnostic de apt-get :"

        [[ -s "$TEMP_DIR/docker-install.out" ]] && cat "$TEMP_DIR/docker-install.out" || true
        [[ -s "$TEMP_DIR/docker-install.err" ]] && cat "$TEMP_DIR/docker-install.err" || true

        error "L'installation de Docker CE a échoué."

    fi

    ok "Docker CE installé"

}

# ----------------------------------------------------------
# SECTION 07
# Activation du service Docker
# ----------------------------------------------------------

section_enable_docker() {

    title "Activation du service Docker"

    info "Activation du démarrage automatique..."

    if ! systemctl enable "$DOCKER_SERVICE" \
        >"$TEMP_DIR/docker-enable.out" \
        2>"$TEMP_DIR/docker-enable.err"; then

        warning "Diagnostic de systemctl :"

        [[ -s "$TEMP_DIR/docker-enable.out" ]] && cat "$TEMP_DIR/docker-enable.out" || true
        [[ -s "$TEMP_DIR/docker-enable.err" ]] && cat "$TEMP_DIR/docker-enable.err" || true

        error "Impossible d'activer le service Docker."

    fi

    ok "Démarrage automatique activé"

    info "Démarrage du service Docker..."

    if ! systemctl start "$DOCKER_SERVICE" \
        >"$TEMP_DIR/docker-start.out" \
        2>"$TEMP_DIR/docker-start.err"; then

        warning "Diagnostic de systemctl :"

        [[ -s "$TEMP_DIR/docker-start.out" ]] && cat "$TEMP_DIR/docker-start.out" || true
        [[ -s "$TEMP_DIR/docker-start.err" ]] && cat "$TEMP_DIR/docker-start.err" || true

        error "Impossible de démarrer le service Docker."

    fi

    if ! systemctl is-active --quiet "$DOCKER_SERVICE"; then

        warning "État du service Docker :"

        systemctl --no-pager --full status "$DOCKER_SERVICE" || true

        error "Le service Docker n'est pas actif."

    fi

    ok "Service Docker actif"

}

# ----------------------------------------------------------
# SECTION 08
# Ajout de l'utilisateur au groupe Docker
# ----------------------------------------------------------

section_add_user_group() {

    title "Configuration de l'utilisateur Docker"

    info "Vérification de l'utilisateur..."

    if ! id "$PRIMARY_USER" >/dev/null 2>&1; then
        error "L'utilisateur '$PRIMARY_USER' est introuvable."
    fi

    ok "Utilisateur détecté"

    info "Vérification du groupe Docker..."

    if ! getent group "$DOCKER_SERVICE" >/dev/null; then
        error "Le groupe '$DOCKER_SERVICE' est introuvable."
    fi

    ok "Groupe Docker détecté"

    info "Ajout de l'utilisateur au groupe Docker..."

    if id -nG "$PRIMARY_USER" | grep -qw "$DOCKER_SERVICE"; then

        ok "L'utilisateur appartient déjà au groupe Docker"

    else

        if ! usermod -aG "$DOCKER_SERVICE" "$PRIMARY_USER" \
            >"$TEMP_DIR/usermod.out" \
            2>"$TEMP_DIR/usermod.err"; then

            warning "Diagnostic de usermod :"

            [[ -s "$TEMP_DIR/usermod.out" ]] && cat "$TEMP_DIR/usermod.out" || true
            [[ -s "$TEMP_DIR/usermod.err" ]] && cat "$TEMP_DIR/usermod.err" || true

            error "Impossible d'ajouter l'utilisateur au groupe Docker."

        fi

        ok "Utilisateur ajouté au groupe Docker"

    fi

    info "Une nouvelle session sera nécessaire pour appliquer ce changement."

}

# ----------------------------------------------------------
# SECTION 09
# Installation du NVIDIA Container Toolkit
# ----------------------------------------------------------

section_install_nvidia_toolkit() {

    title "Installation du NVIDIA Container Toolkit"

    info "Téléchargement de la clé GPG NVIDIA..."

    if ! curl -fsSL "$NVIDIA_GPG_URL" \
        | gpg --dearmor --yes \
        -o "$NVIDIA_GPG_KEY"; then

        error "Impossible d'installer la clé GPG NVIDIA."

    fi

    [[ -s "$NVIDIA_GPG_KEY" ]] \
        || error "La clé GPG NVIDIA est vide."

    chmod a+r "$NVIDIA_GPG_KEY" \
        || error "Impossible de modifier les permissions de la clé GPG NVIDIA."

    ok "Clé GPG NVIDIA installée"

    info "Configuration du dépôt NVIDIA..."

    if ! curl -fsSL "$NVIDIA_REPOSITORY_URL" \
        | sed "s#^deb https://#deb [signed-by=$NVIDIA_GPG_KEY] https://#" \
        >"$NVIDIA_REPOSITORY_FILE"; then

        error "Impossible de configurer le dépôt NVIDIA."

    fi

    [[ -s "$NVIDIA_REPOSITORY_FILE" ]] \
        || error "Le dépôt NVIDIA n'a pas été créé."

    ok "Dépôt NVIDIA configuré"

    info "Actualisation des dépôts APT..."

    if ! apt-get update \
        >"$TEMP_DIR/nvidia-update.out" \
        2>"$TEMP_DIR/nvidia-update.err"; then

        warning "Diagnostic de apt-get :"

        [[ -s "$TEMP_DIR/nvidia-update.out" ]] && cat "$TEMP_DIR/nvidia-update.out" || true
        [[ -s "$TEMP_DIR/nvidia-update.err" ]] && cat "$TEMP_DIR/nvidia-update.err" || true

        error "Impossible de mettre à jour les dépôts NVIDIA."

    fi

    ok "Dépôts NVIDIA mis à jour"

    info "Installation du NVIDIA Container Toolkit..."

    if ! apt-get install --yes "${NVIDIA_PACKAGES[@]}" \
        >"$TEMP_DIR/nvidia-install.out" \
        2>"$TEMP_DIR/nvidia-install.err"; then

        warning "Diagnostic de apt-get :"

        [[ -s "$TEMP_DIR/nvidia-install.out" ]] && cat "$TEMP_DIR/nvidia-install.out" || true
        [[ -s "$TEMP_DIR/nvidia-install.err" ]] && cat "$TEMP_DIR/nvidia-install.err" || true

        error "L'installation du NVIDIA Container Toolkit a échoué."

    fi

    ok "NVIDIA Container Toolkit installé"

}

# ----------------------------------------------------------
# SECTION 10
# Configuration du runtime NVIDIA
# ----------------------------------------------------------

section_configure_runtime() {

    title "Configuration du runtime NVIDIA"

    info "Validation de l'outil NVIDIA Container Toolkit..."

    if ! check_command nvidia-ctk; then
        error "La commande 'nvidia-ctk' est introuvable."
    fi

    ok "Outil NVIDIA Container Toolkit détecté"

    info "Configuration du runtime NVIDIA pour Docker..."

    if ! nvidia-ctk runtime configure --runtime=docker \
        >"$TEMP_DIR/nvidia-runtime.out" \
        2>"$TEMP_DIR/nvidia-runtime.err"; then

        warning "Diagnostic de nvidia-ctk :"

        [[ -s "$TEMP_DIR/nvidia-runtime.out" ]] && cat "$TEMP_DIR/nvidia-runtime.out" || true
        [[ -s "$TEMP_DIR/nvidia-runtime.err" ]] && cat "$TEMP_DIR/nvidia-runtime.err" || true

        error "Impossible de configurer le runtime NVIDIA."

    fi

    ok "Configuration du runtime appliquée"

    info "Validation de la configuration Docker..."

    [[ -s "$DOCKER_DAEMON_CONFIG" ]] \
        || error "Le fichier '$DOCKER_DAEMON_CONFIG' est introuvable."

    if ! grep -Fq '"runtimes"' "$DOCKER_DAEMON_CONFIG"; then
        error "La configuration des runtimes Docker est absente."
    fi

    if ! grep -Fq '"nvidia"' "$DOCKER_DAEMON_CONFIG"; then
        error "Le runtime NVIDIA n'a pas été ajouté à Docker."
    fi

    ok "Configuration Docker validée"

}

# ----------------------------------------------------------
# SECTION 11
# Redémarrage de Docker
# ----------------------------------------------------------

section_restart_docker() {

    title "Redémarrage du service Docker"

    info "Redémarrage du service Docker..."

    if ! systemctl restart "$DOCKER_SERVICE" \
        >"$TEMP_DIR/docker-restart.out" \
        2>"$TEMP_DIR/docker-restart.err"; then

        warning "Diagnostic de systemctl :"

        [[ -s "$TEMP_DIR/docker-restart.out" ]] && cat "$TEMP_DIR/docker-restart.out" || true
        [[ -s "$TEMP_DIR/docker-restart.err" ]] && cat "$TEMP_DIR/docker-restart.err" || true

        error "Impossible de redémarrer le service Docker."

    fi

    ok "Redémarrage du service terminé"

    info "Validation de l'état du service Docker..."

    if ! systemctl is-active --quiet "$DOCKER_SERVICE"; then

        warning "État du service Docker :"

        systemctl --no-pager --full status "$DOCKER_SERVICE" || true

        error "Le service Docker n'est pas actif."

    fi

    ok "Service Docker actif"

}

# ----------------------------------------------------------
# SECTION 12
# Validation GPU Docker
# ----------------------------------------------------------

section_test_gpu() {

    title "Validation GPU Docker"

    info "Validation de Docker..."

    if ! check_command docker; then
        error "La commande 'docker' est introuvable."
    fi

    ok "Docker détecté"

    if ! systemctl is-active --quiet "$DOCKER_SERVICE"; then
        error "Le service Docker n'est pas actif."
    fi

    ok "Service Docker actif"

    info "Validation de l'accès au GPU NVIDIA depuis Docker (téléchargement de l'image si nécessaire)..."

    if ! docker run --rm \
        --gpus all \
        "$CUDA_TEST_IMAGE" \
        nvidia-smi \
        >"$TEMP_DIR/docker-gpu.out" \
        2>"$TEMP_DIR/docker-gpu.err"; then

        warning "Diagnostic de Docker :"

        [[ -s "$TEMP_DIR/docker-gpu.out" ]] && cat "$TEMP_DIR/docker-gpu.out" || true
        [[ -s "$TEMP_DIR/docker-gpu.err" ]] && cat "$TEMP_DIR/docker-gpu.err" || true

        warning "Version de Docker :"

        docker version || true

        error "La validation GPU Docker a échoué."

    fi

    if ! grep -Fq "NVIDIA-SMI" "$TEMP_DIR/docker-gpu.out"; then

        warning "Sortie de Docker :"

        cat "$TEMP_DIR/docker-gpu.out" || true

        error "La sortie de 'nvidia-smi' est invalide."

    fi

    ok "GPU NVIDIA accessible depuis Docker"

    info "Sortie de nvidia-smi :"

    cat "$TEMP_DIR/docker-gpu.out"

}

# ----------------------------------------------------------
# SECTION 13
# Résumé
# ----------------------------------------------------------

section_summary() {

    title "Bootstrap Docker terminé"

    ok "Installation terminée avec succès"
    ok "Docker CE est opérationnel"
    ok "Le runtime NVIDIA est opérationnel"
    ok "Le GPU est accessible depuis Docker"

    echo

    info "État du système :"

    if systemctl is-active --quiet "$DOCKER_SERVICE"; then
        ok "Service Docker actif"
    else
        warning "Service Docker inactif"
    fi

    if id -nG "$PRIMARY_USER" | grep -qw "$DOCKER_SERVICE"; then
        ok "L'utilisateur '$PRIMARY_USER' appartient au groupe Docker"
    else
        warning "L'utilisateur '$PRIMARY_USER' n'appartient pas au groupe Docker"
    fi

    echo

    info "Une nouvelle session utilisateur est nécessaire pour appliquer définitivement l'appartenance au groupe Docker."

    echo

    info "Commande de validation manuelle :"

    printf "  docker run --rm --gpus all %s nvidia-smi\n" "$CUDA_TEST_IMAGE"

    echo

    ok "Bootstrap Docker terminé"

}

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

main() {

    trap cleanup EXIT INT TERM

    rm -rf "$TEMP_DIR" 2>/dev/null || true

    mkdir -p "$TEMP_DIR" \
        || error "Impossible de créer le répertoire temporaire '$TEMP_DIR'."

    header

    section_check_root

    section_check_nvidia

    section_check_network

    section_prechecks

    section_install_dependencies

    section_install_docker

    section_enable_docker

    section_add_user_group

    section_install_nvidia_toolkit

    section_configure_runtime

    section_restart_docker

    section_test_gpu

    section_summary

}

main