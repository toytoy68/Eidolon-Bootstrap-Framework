# C-019 — validation locale, 07/10/2026

Codex/GPT. Base précédente 3743c1d (corrections G050/G052, arbre publié 34e61b1).
Contrat : [QUERY-HISTORY.md](../../../QUERY-HISTORY.md).

## Résultats reproduits ici

- **71 tests ciblés réussis**, dont 16 nouveaux tests d’historique : atomicité
  texte/intention avant fournisseur, échecs d’insertion/fermeture, SQLite occupé,
  exclusion de processus, capacité, suppression/altération des lignes, pagination,
  migration, CLI et absence de valeurs retirées dans les fichiers.
- Coupures de vrais processus `os._exit(43)` pendant la transaction, avant le
  contact et après le contact synthétique ; les deux derniers cas conservent
  INTENT/UNKNOWN et refusent la relance. Revue explicite sans nouvel envoi.
- Suite globale : **719 tests, 713 réussis, 6 intégrations mémoire ignorées**,
  128,408 s (full-tests.txt), Python 3.12.14/Linux.
- Puis **six intégrations mémoire réellement réussies**, 0,889 s : source moteur
  isolée `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, dépendance inchangée,
  corpus temporaires synthétiques et vérification des octets canoniques.
  Le moteur actuel sur VM n’est pas qualifié par cette exécution.
- Démonstration sans réseau : demo.json. Aucun texte brut dans l’historique ou
  empreinte brute dans le rapport ; texte nettoyé consultable localement.
- `git diff --check` réussi.

## Limites

Plafond global inchangé : 256 recherches, pas de rotation livrée (G057).
Conservation explicite, schéma 2 ; pas de rétrogradation automatique, pas de
rétention temporelle décidée. Pas de fournisseur réel, Windows, coupure électrique,
NFS ou VM. Le statut COMPLETED n’est pas une confirmation de réception réseau.
Le journal suit la recherche entière ; pas encore les appels/sauts individuels.
