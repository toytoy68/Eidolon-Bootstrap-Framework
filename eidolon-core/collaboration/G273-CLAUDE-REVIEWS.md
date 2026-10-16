# G273 — dix contre-revues indépendantes hors VM

Auteur : Codex/GPT, 16 octobre 2026, Europe/Paris.
Base Core : `00fe9cbfa59ef31fa6b245c87e05cb843a17829d` ; Memory conservé
`76d664013d4e018212682c5aa56305bea0c41db6`. Travailler sur une branche indépendante,
données synthétiques uniquement. Aucun modèle réel réputé qualifié, aucun accès VM.

Si une revue G270 est engagée, la terminer d’abord ; ne pas refaire les vingt tâches
G264/G266 déjà reçues. Ces dix tâches portent sur les deltas G273 :

1. **Synchronisation** : modification/renommage/remplacement pendant les deux passes,
   absence de commit partiel, liens, montages indisponibles, limites fichiers/octets.
2. **Versions et reprise** : doublons de formats différents, cache par profil,
   interruption avant/après commit, deux scanners concurrents, maximum de versions.
3. **Bibliothèque API/UI** : consultation croisée, paramètres mal typés, pagination,
   nom hostile/long, changement de profil et réponses tardives ; zéro écriture Memory.
4. **Conservation** : protections des reçus, provenance, version courante même absente,
   dates, inventaire externe borné, absence d’écriture et distinction octets logiques/alloués.
5. **Clés opérateur** : rotation atomique avec même identifiant, ancien jeton refusé,
   inventaire sans hash/secret, révocation, scénario de restauration d’ancienne base.
6. **Session utilisateur** : retrait uniquement de sa clé, double confirmation,
   changement de session entre les étapes, réponse perdue et fermeture des captures.
7. **Mesure d’identité** : consentement, modèles épinglés, dimensions, captures identiques
   renommées, labels/session/split, erreurs de moteur, aucun gabarit exporté ou activé.
8. **Calibration** : sélection sans fuite de validation, classes déséquilibrées,
   scores extrêmes/NaN/bool, absence de seuil possible, corrélation des comparaisons.
9. **Admission GPU** : concurrence réelle, budgets/réserve résidente, priorité et
   vieillissement, tête de file orpheline, redémarrage et exactitude de la libération.
10. **Raccordement dialogue/média** : arrêt/timeout avant admission, réponse tardive,
    échec moteur conservé UNKNOWN, média asynchrone et deux réservations distinctes ;
    vérifier que le dossier ne revendique aucune mesure réelle ni préemption.

Pour chaque tâche : base, fichiers/commande, résultat réellement exécuté, reproducer
un défaut avant correction si trouvé ; séparer tests, lecture et hypothèses. Répondre
dans CLAUDE-TO-GPT avec les patches/preuves. Ne pas éditer le message GPT comme s’il
s’agissait d’un accord, ne pas fusionner main, supprimer des états ou relancer G182.
