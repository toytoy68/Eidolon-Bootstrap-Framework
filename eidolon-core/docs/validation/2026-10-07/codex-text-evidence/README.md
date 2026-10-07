# C-020 — texte décodé et challenge Unicode, 07/10/2026

Codex/GPT, base 1ddf902 (arbre publié 2a98a9a). Deux limites connues de G049
traitées : ellipse Unicode de challenge et doublons texte UTF-8 avec BOM.

**102 tests ciblés réussis**, dont deux nouvelles familles : dix combinaisons
HTML/texte mal étiqueté, articles légitimes, mêmes textes HTML/brut/BOM et
cache, BOM seul vide. Recherche, extraction, transport lecteur, garde et
historique C-019 inclus. Les empreintes source demeurent distinctes ; seule
l’empreinte du texte sert à dédupliquer les trois contenus identiques.

Pas de fournisseur réel ni navigateur. Détection par libellés connus, toujours
non exhaustive ; absence de challenge reconnu ne prouve pas un accès libre.
