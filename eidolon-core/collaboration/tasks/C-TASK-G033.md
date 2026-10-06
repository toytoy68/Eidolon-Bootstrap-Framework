# G033 — Corriger les frontières APT du lot C040

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Après G032.
Autorisation de rectification Bootstrap déjà relayée dans C040, intégration
demandée par toytoy le 06/10 à 18 h 29. Ne pas exécuter/source les installateurs.

Deux défauts reproduits par Codex, fonction extraite seule sur fichiers fictifs :

1. `deb https://deb.debian.org/debian trixie main # commentaire` reçoit les
   composants APRÈS le # : ils restent commentés.
2. `deb https://vendor.example/debian trixie main` est modifié malgré la
   promesse « seules entrées Debian ».

Clarifier le périmètre des miroirs Debian (pas de devinette par sous-chaîne
de domaine), préserver les sources tierces, commentaires et deb822 multiligne.
Privilégier un refus explicite/diagnostic pour une forme non prise en charge.
Revoir fichier temporaire, échec d'écriture et permissions conservées sans
ajouter de migration implicite. Tests synthétiques avant/après et bash -n.
Réserver 02-nvidia.sh et tests/docs Bootstrap. Pas de changement système.
