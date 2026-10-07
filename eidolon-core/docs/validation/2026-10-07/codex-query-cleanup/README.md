# C-013 — preuves locales

Base : 7c9ef92, intégration Claude C061/C062 depuis 49cafe05.
77 tests ciblés réussis, dont 8 nouveaux groupes avec cas multiples.
Fournisseurs doubles uniquement ; aucune requête Internet.

Le test distingue données retirées, faux positifs connus, secrets non reconnus,
normalisation, limites d'entrée, requête vide et identité du texte transmis
à tous les replis. Un premier test a révélé le retrait abusif de
`ISO 8601 2026-10-06` ; le motif téléphone a été restreint avant validation.

`synthetic-corpus.json` conserve les sorties des 27 cas fictifs G029.
Ce fichier contient volontairement leurs résidus synthétiques pour inspection ;
le reçu de production n'exporte jamais le texte. Aucun taux d'anonymisation
ni garantie sur une population réelle n'est déduit de ce petit corpus.

Intégration adjacente : 15 cas du miroir APT Claude reproduits sur fonction
isolée, zéro échec ; aucun installateur lancé. Première invocation via unittest
inadaptée au script (il attend le chemin de l'installateur en argument) ;
réexécution directe avec l'argument correct réussie.
