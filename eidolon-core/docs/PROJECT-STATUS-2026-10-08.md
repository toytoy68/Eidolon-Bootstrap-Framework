# Eidolon Core — état du 8 octobre 2026, séance de 11 h 11

Le noyau et la consultation serveur–PC fonctionnent sur les scénarios bornés.
La validation réelle VM100/PC Windows et le choix d'un modèle contrôleur restent
à faire. Ce bilan concerne la branche feat/eidolon-core-v0.1 ; main est inchangée.

## Ajouts utiles de cette séance

| Lot | Résultat |
| --- | --- |
| C-042 | Une autre base de pauses ne peut plus remplacer silencieusement celle liée aux missions. Migration explicite des anciennes bases, pauses/audits conservés, coupures et concurrence testées |
| C-043 | Une création de recherche sans exécution retourne correctement 0. La levée manuelle des pauses du runtime vérifie la liaison au Store |
| C-044 | Diagnostic de liaison en lecture seule : distingue identité correcte, ancienne liaison à examiner, remplacement et élément manquant |
| C-045 | Consultation SQL bornée en octets, BLOB inattendus refusés et WAL refusé avant ouverture sur les parcours sans mutation |
| Claude G066 | Panneau d'archives connecté, lecture paginée sur demande, liste figée si le catalogue change ou devient indisponible |
| Claude G067–G071 | Revues de lecture SQLite, prototype de rotation amélioré, recette indépendante et revues des interruptions/API reçus ; la rotation reste isolée |

## Ce qui reste bloquant pour qualifier la bêta

1. Rejouer la recette sur VM100 puis depuis le PC Windows et son tunnel SSH.
2. Tester un modèle réel sur le serveur : les recettes actuelles de planificateur
   utilisent des serveurs simulés. Aucun résultat ne qualifie la V100.
3. Terminer les contre-revues restantes et aligner les limites du producteur
   d'archives avec celles du lecteur avant intégration de la rotation.
4. Traiter séparément les limites de rappel Memory Engine déjà signalées
   (négation coupée et messages répétés entre versions d'une conversation).

Le chat généraliste, l'accès opérationnel au NAS/documents Windows, la voix,
la webcam et le robot ne sont pas livrés par ces corrections.

Les estimations du bilan du 07/10 restent **environ 80 % pour la bêta de
consultation et 40 % pour la vision complète**. Ce sont des estimations de
périmètre ; la qualification sur les machines de toytoy reste une étape décisive,
indépendante du nombre de tests ou de commits.

[Preuves, commandes et limites de la séance](validation/2026-10-08/codex-hour-1111/README.md).
[File active de Claude](../collaboration/tasks/QUEUE.md).

Validation finale : **971 tests Python réussis**, 59 tests client réussis et
14 Chromium non exécutés. Paquet installé : 55 modules identiques, 25 contrôles
bêta réussis. G071 rejoué : 51/51. G070 rejoué : 20/21, un contrôle de présence
d’orphelin non observable ici via /proc ; à confirmer sur VM. Les 971 tests ne
masquent pas cette limite du banc indépendant.
