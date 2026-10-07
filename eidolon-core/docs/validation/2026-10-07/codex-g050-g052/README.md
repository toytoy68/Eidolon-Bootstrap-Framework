# Corrections après G050/G052 — 07/10/2026

Codex/GPT, base 7934a8b (arbre publié 621d71b). Propositions Claude conservées
sans modification dans leurs rapports ; corrections adaptées dans les sources.

- G050-1 : formes courantes proposées retirées ; port IPv6 entre crochets ajouté.
- G050-2 : le reçu nettoyage/2 et le rapport n’exportent plus le hash brut.
  Le hash du texte nettoyé reste une référence, pas une garantie de confidentialité.
- G052-1 : première frontière couvrant aussi les reçus déjà munis de hash C-012.
- G052-2 : hash sous la frontière refusé, détection par objet JSON décodé.
  Les anciens reçus sans hash restent lisibles avant la frontière ; une réécriture
  cohérente de toute la base reste hors garantie.

Validation locale : **84 tests ciblés réussis** (targeted-tests.txt). Sondes G052
rejouées avec un vrai checkout archivé C-012 pour l’ancienne version ; résultat
séparé dans g052-probes.txt. Données synthétiques, aucun fournisseur réel.
Les preuves historiques Claude ne sont pas réécrites.
