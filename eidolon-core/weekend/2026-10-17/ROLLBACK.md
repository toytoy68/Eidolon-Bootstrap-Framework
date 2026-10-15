# Retour arrière préparé, à exécuter sur place

Le lot G269 ne modifie aucun schéma canonique et n'exécute aucune migration. Il ajoute des projections d'index distinctes et des checkpoints de maintenance. Le rollback doit préserver les écritures métier intervenues depuis la sauvegarde.

1. Noter l'incident, l'heure, les SHA, le processus/alias en cause et le dernier reçu. Conserver les journaux privés, sans copier les tokens dans le rapport.
2. Arrêter uniquement les processus/timer **candidats** identifiés pendant l'inventaire. Ne pas arrêter les services d'origine par un nom supposé. Fermer le tunnel de recette via son lanceur ou sa fenêtre.
3. Revenir à l'ancien dossier source et à son environnement/configuration enregistrés. Les sources candidates restent séparées : aucun `git reset --hard`, aucun remplacement du dossier vivant n'est nécessaire.
4. Rétablir la sélection explicite de l'ancien alias/configuration. Un alias de passages ne s'ouvre pas avec l'adapter documentaire. Garder les collections candidates et échouées pour revue ; aucune suppression ou bascule silencieuse.
5. Ne pas réutiliser des checkpoints avec un autre corpus, modèle, profil ou alias. Conserver l'ancien dossier d'état intact. Un état REVIEW_REQUIRED ne doit pas être effacé pour obtenir artificiellement un état vert.
6. Pour le corpus : restaurer **dans une nouvelle copie** et vérifier son inventaire et `--check-storage`. Si des souvenirs ont été créés depuis le snapshot, les inventorier avec leurs reçus avant toute décision de restauration. Ne jamais écraser le corpus courant avec la sauvegarde sans réconciliation explicite.
7. Relancer les contrôles de lecture et la recette minimale sur l'ancienne configuration. Consigner le résultat et la réserve dans V12, puis laisser la candidate arrêtée tant que le défaut n'est pas compris.

Les commandes de service et chemins réels seront ceux de MACHINE-INVENTORY.md. Ils ne sont pas préremplis ici : le compte C187 et le déploiement effectif ne sont pas encore validés.
