# C-015 — budget global d'invocations, preuve locale

Base fa7e9bc. 79 tests ciblés réussis (42,374 s), dont 13 nouveaux groupes.
Tests Core/actions/abandon également rejoués, avec vrais workers Python.
La nouvelle limite par défaut est 64 ; aucune donnée utilisateur touchée.

Vérifiés : reprise avec compteur inchangé, rappels vides/en erreur et modèle
indisponible comptés, réservation avant worker, rollback audit+compteur,
réconciliation sans remboursement, refus avant outil faute de place pour sa
vérification, résultat déjà retourné conservé à épuisement, approbation non
consommée après contrôles préalables, incompatibilité si limite modifiée,
ancien mode explicitement sans budget et sortie JSON CLI.

La suite globale sera enregistrée après intégration de G047 et correction de
SIGTERM. Ce lot ne prétend pas résoudre rétention, quota global de serveur ou
restauration cohérente d'une ancienne base.
