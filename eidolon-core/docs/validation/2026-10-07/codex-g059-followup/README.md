# C-029 — initialisation liée au Store, suivi G059

Codex, 07/10/2026. Base G059 intégrée via 2ac483b, Desktop G060/G061 via
62064ec. Tests locaux synthétiques ; aucun service utilisateur ni fournisseur réel.

G059-1 est reproduit dans before.txt. Après correction, after.txt confirme le
refus de construction sans recréation du journal, y compris INTENT incertaine.
Le Store retient l'identité de la garde. Les quinze tests dédiés couvrent aussi
la disparition du dossier entier, les pauses incomplètes, adoption C-021,
restauration des originaux et constructions concurrentes.

Résultats exécutés :

- 72 tests ciblés réussis ; 808 globaux découverts, 802 réussis, six intégrations
  mémoire ignorées dans cette commande (aucune nouvelle recette mémoire revendiquée).
- Archives : vingt tests dédiés et vraie compatibilité du prototype G062 v2.
  Le libellé actual_g057_exports_verified du script historique désigne le format
  G057 ; le fichier prototype-v2-compatibility.json a bien été produit avec G062.
- Client connecté : 51 réussis, 13 Chromium ignorés ; build.js --check réussi.
- Prototype Desktop : 68 réussis, 24 échecs de lancement Chromium, exécutable
  absent. Ce n'est pas une recette navigateur locale réussie. Les 92/92 et 64/64
  navigateur rapportés par Claude restent ses preuves, pas celles de Codex.
- Paquet construit sans réseau et installé en venv jetable : modules identiques,
  24 contrôles bêta, mission synthétique/reprise et diagnostics, lecteur/index
  d'archives invoqués depuis le paquet installé. Détails dans package.json.

Limites : aucune authentification cryptographique contre réécriture cohérente ;
rollback conjoint du Store et de la garde hors garantie. Pas de rotation active,
ni qualification VM, Windows ou coupure électrique. G064 doit contre-vérifier
ce lot ; G063 traite les défauts du prototype avant toute activation.

Commandes depuis eidolon-core :

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -q
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
node --test desktop/prototype/tests/*.test.js
node desktop/connected/build.js --check
python docs/validation/2026-10-07/codex-g059-followup/core-package-smoke.py
```
