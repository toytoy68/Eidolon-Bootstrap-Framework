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

# Ajoute contrib, non-free et non-free-firmware aux seules entrées des
# miroirs Debian officiels (deb.debian.org, security.debian.org,
# ftp.debian.org, ftp.<pays>.debian.org ; chemin /debian ou
# /debian-security) qui contiennent déjà « main », sans doublon : relancer
# le script ne modifie plus rien. Formats : ligne « deb … » (sources.list),
# commentaire de fin de ligne compris, et strophe deb822 (debian.sources).
# Sources tierces, lignes commentées et formes non prises en charge restent
# intactes ; les deux dernières sont signalées sur la sortie d'erreur.
# Le fichier n'est remplacé que s'il change, après une écriture complète,
# en gardant ses droits et son propriétaire.
add_debian_components() {

    local file="$1"
    local deb822=0
    local tmp

    [[ "$file" == *.sources ]] && deb822=1

    tmp=$(mktemp "${file}.eidolon-XXXXXX") || return 1

    if ! awk -v deb822="$deb822" '
        BEGIN { split("contrib non-free non-free-firmware", wanted, " ") }

        function note(message) {
            print FILENAME ":" (at ? at : FNR) ": " message " ; laissé intact" > "/dev/stderr"
        }

        # Miroir officiel : hôte exact et chemin exact, jamais une sous-chaîne.
        function official(uri,    rest, slash, host, path) {
            if (substr(uri, 1, 7) == "http://") rest = substr(uri, 8)
            else if (substr(uri, 1, 8) == "https://") rest = substr(uri, 9)
            else return 0
            slash = index(rest, "/")
            if (slash == 0) return 0
            host = substr(rest, 1, slash - 1)
            path = substr(rest, slash)
            sub(/\/+$/, "", path)
            if (host != "deb.debian.org" && host != "security.debian.org" \
                && host != "ftp.debian.org" && host !~ /^ftp\.[a-z][a-z]\.debian\.org$/) return 0
            return path == "/debian" || path == "/debian-security"
        }

        function has(list, word,    n, i, words) {
            n = split(list, words, /[ \t]+/)
            for (i = 1; i <= n; i++) if (words[i] == word) return 1
            return 0
        }

        function missing(list,    w, out) {
            out = ""
            for (w = 1; w <= 3; w++) if (!has(list, wanted[w])) out = out " " wanted[w]
            return out
        }

        function one_line(line,    body, comment, gap, p, type, rest, n, t, uri, components, i) {
            if (line !~ /^[ \t]*deb(-src)?[ \t]/) { print line; return }
            body = line; comment = ""
            p = index(body, "#")
            if (p) { comment = substr(body, p); body = substr(body, 1, p - 1) }
            gap = ""
            if (match(body, /[ \t]+$/)) { gap = substr(body, RSTART); body = substr(body, 1, RSTART - 1) }
            match(body, /^[ \t]*deb(-src)?/)
            rest = substr(body, RLENGTH + 1)
            sub(/^[ \t]+/, "", rest)
            if (substr(rest, 1, 1) == "[") {
                p = index(rest, "]")
                if (!p) { note("options [ ] non fermées"); print line; return }
                rest = substr(rest, p + 1)
            }
            n = split(rest, t, /[ \t]+/)
            if (t[1] == "") { for (i = 1; i < n; i++) t[i] = t[i + 1]; n-- }
            if (n < 3) { print line; return }
            uri = t[1]; components = ""
            for (i = 3; i <= n; i++) components = components " " t[i]
            if (!has(components, "main")) { print line; return }
            if (!official(uri)) { note("source non Debian officielle (" uri ")"); print line; return }
            print body missing(components) (comment == "" ? gap : (gap == "" ? " " : gap) comment)
        }

        # deb822 : une strophe est modifiée seulement si toutes ses URIs sont
        # officielles et si « Components: » tient sur une ligne.
        function flush(    i, name, value, field, uris, comp_line, comp_multi, n, u, ok, components) {
            uris = ""; comp_line = 0; comp_multi = 0; field = ""; at = first
            for (i = 1; i <= count; i++) {
                if (lines[i] ~ /^#/) continue
                if (lines[i] ~ /^[ \t]/) {
                    if (field == "uris") uris = uris " " lines[i]
                    if (field == "components") comp_multi = 1
                    continue
                }
                name = tolower(lines[i]); sub(/:.*/, "", name)
                value = lines[i]; sub(/^[^:]*:/, "", value)
                field = name
                if (name == "uris") uris = value
                if (name == "components") comp_line = i
            }
            if (comp_line) {
                components = lines[comp_line]; sub(/^[^:]*:/, "", components)
                if (has(components, "main")) {
                    n = split(uris, u, /[ \t]+/); ok = 0
                    for (i = 1; i <= n; i++) if (u[i] != "") { if (!official(u[i])) { ok = -1; break } ok = 1 }
                    if (comp_multi) note("Components sur plusieurs lignes, non pris en charge")
                    else if (ok != 1) note("strophe avec une URI non Debian officielle")
                    else { sub(/[ \t]+$/, "", lines[comp_line]); lines[comp_line] = lines[comp_line] missing(components) }
                }
            }
            for (i = 1; i <= count; i++) print lines[i]
            count = 0; at = 0
        }

        deb822 && /^[ \t]*$/ { flush(); print; next }
        deb822 { if (!count) first = FNR; lines[++count] = $0; next }
        { one_line($0) }
        END { if (deb822) flush() }
    ' "$file" >"$tmp"; then
        rm -f "$tmp"
        return 1
    fi

    if cmp -s "$file" "$tmp"; then
        rm -f "$tmp"
        return 0
    fi

    if ! chmod --reference="$file" "$tmp" \
        || ! chown --reference="$file" "$tmp" \
        || ! mv -f "$tmp" "$file"; then
        rm -f "$tmp"
        return 1
    fi

}

if [[ -f /etc/apt/sources.list ]]; then

    [[ -f /etc/apt/sources.list.bak ]] || \
        cp /etc/apt/sources.list /etc/apt/sources.list.bak

    add_debian_components /etc/apt/sources.list \
        || error "Impossible de configurer sources.list."

    ok "sources.list configuré"

fi

if [[ -f /etc/apt/sources.list.d/debian.sources ]]; then

    [[ -f /etc/apt/sources.list.d/debian.sources.bak ]] || \
        cp /etc/apt/sources.list.d/debian.sources \
           /etc/apt/sources.list.d/debian.sources.bak

    add_debian_components /etc/apt/sources.list.d/debian.sources \
        || error "Impossible de configurer debian.sources."

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