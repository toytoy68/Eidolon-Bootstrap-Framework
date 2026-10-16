> Mise à jour G275 : audit G274 et corrections intégrées ; consulter [la contre-vérification](CONTRE-VERIFICATION-G275.md). Les validations PC/VM et extensions ci-dessous restent ouvertes.

# Backlog bêta actuel — G273, 16 octobre 2026

G273 réalise les cinq compléments hors VM demandés : bibliothèque versionnée avec
suivi périodique, aperçu de conservation, renouvellement/retrait des clés et parcours
de session, mesure/calibration de captures existantes, admission GPU partagée.
Voir [la procédure](../weekend/2026-10-17/SERVICES-HORS-VM-G273.md) et le
[rapport unique](../weekend/2026-10-17/RAPPORT-UNIQUE.md) pour le périmètre exact.

| Priorité | Prochaine étape | Ce qui est déjà développé | Ce qui reste réellement ouvert |
| --- | --- | --- | --- |
| P0 | Inventaire, comptes, sauvegarde/restauration, configurations privées | Dossier, diagnostic, copies contrôlées et rollback | Recette sous les vrais UID/montages, choix C187, réconciliation des magasins |
| P0 | Core/Memory/Windows sur les machines | Chat, ponts, index, Web, documents, profils par clé, résident | Services/modèles/corpus réels, périphériques, tunnels, endurance et ressources |
| P1 | Suivi de bibliothèque | Scans périodiques Linux/NAS/partage PC, SHA, versions, doublons, reprise et consultation appairée | Installation/mesure sur les montages ; agent Windows natif autonome et très grands arbres hors de ce lot |
| P1 | Conservation | Tailles/protections et aperçu d’anciens extraits ; historiques/médias/sauvegardes inventoriables sans lecture des contenus | Durées métier et sauvegardes à décider ; exécuteur de purge multi-magasins absent, aucune suppression automatique |
| P1 | Profils et sessions | Fermeture locale, changement par clé explicite, retrait de sa clé, inventaire et rotation opérateur conservant la liaison | Activation des trois profils ; administration Web et reconnaissance multipersonne comme connexion non livrées |
| P1 | Voix/visage | Mesure de corpus consentis existants, modèles épinglés, séparation des sessions, FAR/FRR et seuil candidat | Captures/poids réels, précision, représentativité, usurpation et calibration revue ; aucun seuil activé |
| P1 | GPU partagé | Admission durable dialogue/média, budgets, priorité/vieillissement, incertitudes et reprise opérateur | Mesures VRAM/latences, configuration des réserves ; autres clients/moteurs non raccordés automatiquement, pas de préemption ni ordonnanceur CUDA |
| P2 | Médias avancés et extensions | Contrats/worker existants et réservation commune optionnelle | Vidéo longue, galerie/rétention, mobile, robotique et autres extensions selon périmètre adopté |

Les cinquante cas du dossier sont NOT_RUN sur les machines cibles. Les tests et
simulations n’établissent pas leur résultat. Les valeurs d’exemple ne constituent
pas des seuils de charge, VRAM, reconnaissance ou conservation validés.

C191 reste le dernier message Claude observé. Les contre-revues G270 ne sont pas
prétendues exécutées ; les résultats G262/G264/G266 et C191 sont déjà intégrés.
G182 ne doit pas être relancé avant récupération de ses journaux.
