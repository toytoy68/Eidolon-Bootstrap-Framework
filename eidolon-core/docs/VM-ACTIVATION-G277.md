# G277 — activation VM autorisée, 16 octobre 2026

Autorisation toytoy à 19 h 17 : correction, sauvegardes, basculement contrôlé et recette complète disponible sans accès physique au PC.

## Correctifs vérifiés

- Bibliothèque : double empreinte en flux pour les documents exclus de l'extraction, dans un budget distinct de 32 Mio par passage. Les contenus au-delà du budget portent `FILE_TOO_LARGE_CONTENT_UNVERIFIED`, sans extrait ni empreinte de contenu publiée. Aucun blocage des autres documents pour cette seule limite. Les deux passages ne constituent pas un snapshot atomique.
- Lecteur JSON de configuration Core/Memory et prototype d'observation : deuxième lecture bornée comparée aux premiers octets, indépendante de la précision des horodatages.
- Inventaire de copie : double empreinte par lecture et relecture finale du contenu, revérification des chemins des répertoires après parcours. Le budget `max_bytes` reste celui d'un passage ; avec contrôle final, les lectures peuvent atteindre quatre fois ce volume. Un arbre arrêté reste obligatoire ; aucun gel atomique n'est revendiqué.
- Le test historique de limite après contrôle de métadonnées a été renforcé pour exiger le refus désormais possible. La vraie limite après achèvement du contrôle final reste testée séparément.

## Preuves VM

Core Python 3.13.5 : 2 299 réussis, 18 ignorés, 1 avertissement attendu de fixture ZIP, 1 328 sous-tests. Memory Python 3.13.5 : 3 157 réussis, 26 ignorés, 3 xfail existants, 12 sous-tests. Tests complets sous umask 022 ; services privés sous 077. Les erreurs initiales de permissions et de collecte des archives documentaires ont été conservées, puis le périmètre `tests/` exécuté. Les tests de packaging Memory ont été relancés dans un clone Git réel, pas dans l'archive sans `.git`.

Sauvegardes réelles arrêtées/restaurées : Core 50 entrées, Memory 604 entrées, contenus et droits comparés, sources inchangées. Les cinq services API/communication/monitoring/pont/dashboard ont redémarré. Dialogue réel : ANSWER, historique présent, rejeu sans second appel au modèle.

L'activation du profil, de l'index et de la maintenance fait l'objet de la suite du lot. Ce document de qualification du code ne signifie pas que ces raccordements ou les essais Windows sont terminés. Rapport opérationnel consolidé à suivre.
