# Rectification des installateurs Bootstrap 01/02/03

Auteur : Claude, 06/10/2026, **sur autorisation explicite de toytoy**
(« tu as l'autorisation pour apporter des rectifications aux 3 premiers
scripts »). Suite des constats I1 et I2 de la
[vérification globale](../claude-audit-global/README.md).
Les scripts n'ont été **ni exécutés ni sourcés** (AGENTS.md).

## I1 — fins de ligne : commit `67d2025`

- `01-system.sh`, `02-nvidia.sh` et `03-docker.sh` passent de CRLF à **LF**
  (456, 342 et 858 lignes). `git diff --ignore-cr-at-eol` est **vide** : seules
  les fins de ligne changent.
- Un `.gitattributes` (`*.sh text eol=lf`) empêche le retour du CRLF, même
  après un envoi depuis Windows.
- Les trois scripts passent maintenant `bash -n`.

## I2 — dépôts Debian dans `02-nvidia.sh` : commit suivant

Les deux `sed` sont remplacés par une fonction `add_debian_components`
(`awk`) qui :

- n'agit que sur les lignes `deb`/`deb-src` et les champs `Components:` qui
  contiennent déjà `main` ;
- n'ajoute que ce qui manque parmi `contrib`, `non-free` et
  `non-free-firmware`, donc **sans doublon**. Une seconde exécution ne change
  rien ;
- traite `Components: main non-free-firmware` en deb822, que l'ancien `sed`
  ignorait ;
- laisse intactes les lignes commentées et les autres dépôts (Docker,
  NVIDIA) ;
- remplace le fichier seulement après une écriture complète, et appelle
  `error` en cas d'échec.

La sauvegarde `.bak` existante est conservée.

[Test](test_add_debian_components.py) ([sortie](test-output.txt)) : seule la
fonction, extraite du script, est jouée par bash sur des fichiers fictifs.
Deux passages donnent un résultat identique. Chaque ligne Debian concernée a
chaque composant une seule fois ; les lignes commentées et Docker sont
intactes.

## Contrôles

[scripts-check.txt](scripts-check.txt) :

- `bash -n` OK pour les trois scripts ;
- `git ls-files --eol` : LF ;
- shellcheck 0.11 : seulement SC1091 (`/etc/os-release` non suivi, normal) et
  30 SC2034. Ces derniers portent sur les variables d'identité ECT déclarées
  mais non affichées ; je ne les ai pas modifiées.

## Non fait, non vérifié

- Aucune exécution sur Debian 13 : le contenu réel de `debian.sources` sur la
  machine de toytoy n'est pas connu ici.
- Logique d'installation inchangée par ailleurs : NVIDIA, Docker,
  utilisateur, réseau.
