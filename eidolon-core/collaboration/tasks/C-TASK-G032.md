# G032 — Robustesse de l'extracteur HTML avant raccordement

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Après G031.
Base G026 intégrée ; ses 16 tests sont reproduits par Codex.

Relire/sonder les bornes et contenus malformés : profondeur, titres imbriqués,
balises cachées/ignorées, entités produisant des contrôles, limites falsy,
contenu trop long en un segment. Vérifier que le contrat de visibilité et de
bornage correspond au résultat. Tests avant/après pour chaque défaut confirmé,
correctif minimal dans html_extract.py et tests dédiés. Aucun raccordement au
WebReader, aucune classification heuristique présentée comme certaine.
Fournir résultat, coût sur entrée maximale et limites résiduelles. Puis G033.
