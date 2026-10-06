#!/usr/bin/env bash

# ==========================================================
# Projet       : Eidolon Bootstrap Framework
# Script       : 01-system.sh
# Version      : 1.0.0-alpha
# Description  : Préparation d'une Debian 13 Trixie fraîche
#                pour recevoir Eidolon Core.
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

readonly COMPONENT_NAME="01-system"
readonly COMPONENT_TITLE="Préparation du système"
readonly COMPONENT_VERSION="1.0.0-alpha"
readonly COMPONENT_STATUS="En développement"
readonly COMPONENT_NEXT="02-nvidia"

# ----------------------------------------------------------
# Identité du nœud Eidolon
# ----------------------------------------------------------

readonly HOSTNAME="Eidolon-Core-Alpha"
readonly DOMAIN="local"

readonly PRIMARY_USER="toytoy"

readonly TIMEZONE="Europe/Paris"
readonly LOCALE="fr_FR.UTF-8"

# ----------------------------------------------------------
# Configuration réseau (Profil Eidolon Lab)
# ----------------------------------------------------------

readonly STATIC_IP="192.168.1.135/24"
readonly GATEWAY="192.168.1.254"

readonly DNS_SERVERS=(
    "192.168.1.254"
    "1.1.1.1"
    "8.8.8.8"
)


# ----------------------------------------------------------
# Répertoires
# ----------------------------------------------------------

readonly EIDOLON_HOME="/opt/eidolon"

# ----------------------------------------------------------
# Paquets système
# ----------------------------------------------------------

readonly REQUIRED_PACKAGES=(

    # Dépôts et certificats
    ca-certificates

    # Développement
    sudo
    git
    shellcheck

    # Téléchargement et API
    curl
    wget
    jq

    # Compilation
    build-essential
    cmake

    # Python
    python3-pip
    python3-venv

    # Éditeurs
    nano
    vim
    less

    # Terminal
    tree
    tmux
    screen

    # Supervision
    htop
    btop
    ncdu

    # Compression
    zip
    unzip
    p7zip-full

    # Synchronisation
    rsync

    # Outils système
    lsof
    pciutils
    usbutils
    bind9-dnsutils
    ethtool
    iperf3
    smartmontools
    nvme-cli
    net-tools
    openssh-client

)

# ----------------------------------------------------------
# Fonctions d'affichage
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

    "$@" || error "Échec : $MESSAGE"

    ok "$MESSAGE"

}

# ----------------------------------------------------------
# Accueil
# ----------------------------------------------------------

clear

echo
echo "#########################################################"
echo "#                                                       #"
echo "#          Eidolon Bootstrap Framework                  #"
echo "#                                                       #"
echo "#                 Script 01 - System                    #"
echo "#                                                       #"
echo "#########################################################"
echo
echo "Ce script va :"
echo
echo "  • Vérifier le système"
echo "  • Vérifier la connexion Internet"
echo "  • Mettre Debian à jour"
echo "  • Installer les outils système"
echo "  • Configurer l'utilisateur ${PRIMARY_USER}"
echo "  • Préparer l'environnement Eidolon"
echo
echo "Machine            : $(hostname)"
echo "Utilisateur cible  : ${PRIMARY_USER}"
echo "Date               : $(date)"
echo

read -rp "Continuer ? [Entrée] "

# ----------------------------------------------------------
# Vérification Root
# ----------------------------------------------------------

[[ $EUID -eq 0 ]] || error "Ce script doit être exécuté en tant que root."

# ----------------------------------------------------------
# Vérification Debian
# ----------------------------------------------------------

title "Vérification du système"

command -v apt >/dev/null 2>&1 || \
    error "APT est introuvable."

source /etc/os-release

[[ "$ID" == "debian" ]] || \
    error "Distribution non supportée."

[[ "$VERSION_CODENAME" == "trixie" ]] || \
    error "Debian 13 Trixie requise."

ok "Debian 13 Trixie détectée"

# ----------------------------------------------------------
# Configuration du système
# ----------------------------------------------------------

title "Configuration du système"

if [[ "$(hostnamectl --static)" != "$HOSTNAME" ]]; then

    run "Configuration du nom d'hôte" \
        hostnamectl set-hostname "$HOSTNAME"

else

    info "Nom d'hôte déjà configuré."

fi

run "Configuration du fuseau horaire" \
    timedatectl set-timezone "$TIMEZONE"

run "Configuration de la locale" \
    localectl set-locale LANG="$LOCALE"

# ----------------------------------------------------------
# Vérification Internet
# ----------------------------------------------------------

title "Connexion Internet"

ping -c1 deb.debian.org >/dev/null 2>&1 || \
    error "Connexion Internet indisponible."

ok "Connexion Internet disponible"

# ----------------------------------------------------------
# Mise à jour du système
# ----------------------------------------------------------

title "Mise à jour du système"

run "Actualisation des dépôts APT" \
    apt update

run "Mise à niveau du système" \
    apt -y full-upgrade

run "Suppression des dépendances inutiles" \
    apt autoremove -y

run "Nettoyage du cache APT" \
    apt autoclean

# ----------------------------------------------------------
# Installation des outils système
# ----------------------------------------------------------

title "Installation des outils système"

run "Installation des paquets système" \
    apt install -y "${REQUIRED_PACKAGES[@]}"

# ----------------------------------------------------------
# Configuration de l'utilisateur
# ----------------------------------------------------------

title "Configuration de l'utilisateur"

if id "$PRIMARY_USER" >/dev/null 2>&1; then

    if id -nG "$PRIMARY_USER" | grep -qw sudo; then

        info "L'utilisateur appartient déjà au groupe sudo."

    else

        run "Ajout de l'utilisateur au groupe sudo" \
            usermod -aG sudo "$PRIMARY_USER"

    fi

else

    warning "Utilisateur '${PRIMARY_USER}' introuvable."

fi

# ----------------------------------------------------------
# Préparation de l'environnement Eidolon
# ----------------------------------------------------------

title "Création de l'environnement Eidolon"

mkdir -p \
    "${EIDOLON_HOME}/bootstrap" \
    "${EIDOLON_HOME}/core" \
    "${EIDOLON_HOME}/config" \
    "${EIDOLON_HOME}/logs" \
    "${EIDOLON_HOME}/models" \
    "${EIDOLON_HOME}/plugins" \
    "${EIDOLON_HOME}/scripts" \
    "${EIDOLON_HOME}/venv" \
    "${EIDOLON_HOME}/backups"

[[ -d "$EIDOLON_HOME" ]] || \
    error "Impossible de créer l'environnement Eidolon."

ok "Arborescence Eidolon créée"

# ----------------------------------------------------------
# Validation des outils
# ----------------------------------------------------------

title "Validation de l'environnement"

run "Validation de Git" \
    git --version

run "Validation de Curl" \
    curl --version

run "Validation de Wget" \
    wget --version

run "Validation de Python" \
    python3 --version

run "Validation de Pip" \
    pip3 --version

run "Validation de GCC" \
    gcc --version

run "Validation de CMake" \
    cmake --version

run "Validation de jq" \
    jq --version

run "Validation de ShellCheck" \
    shellcheck --version

[[ -d "$EIDOLON_HOME" ]] || \
    error "L'environnement Eidolon est introuvable."

ok "Environnement système validé"

# ----------------------------------------------------------
# Résumé système
# ----------------------------------------------------------

title "Résumé du système"

echo
echo "Machine        : $(hostnamectl --static)"
echo "Utilisateur    : ${PRIMARY_USER}"

echo
echo "Processeur :"
awk -F': ' '/model name/ {print $2; exit}' /proc/cpuinfo

echo
echo "Mémoire :"
free -h | head -2

echo
echo "Stockage :"
df -h /

echo
echo "Répertoire Eidolon : ${EIDOLON_HOME}"

# ----------------------------------------------------------
# Fin du bootstrap
# ----------------------------------------------------------

title "Préparation du système terminée"

echo
ok "Préparation du système terminée."
echo

separator
echo "Prochaine étape :"
separator
echo
echo "    sudo ./${COMPONENT_NEXT}.sh"
echo
echo "Une reconnexion de l'utilisateur"
echo "'${PRIMARY_USER}' est nécessaire"
echo "pour appliquer les droits sudo."
echo

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
        info "Reconnectez-vous avant de lancer ${COMPONENT_NEXT}.sh"
        ;;

esac