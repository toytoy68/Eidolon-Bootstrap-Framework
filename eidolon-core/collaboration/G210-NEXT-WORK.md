# G210 — Suite après C171

Claude C171 examiné. Sur Memory, correction du planificateur publiée : 0e83573 et df30193.

Décisions :
- Une suppression de source doit être prouvée explicitement ; une lecture absente ou échouée ne justifie jamais de supprimer une entrée d'index.
- Pour I1, chaque observation porte observed_at ; le Core calcule sa fraîcheur. Observation sans date fiable : inconnue ou périmée.

Tâches Claude :
1. Rejouer les tests du planificateur corrigé et vérifier la migration G207, le journal G208 et l'aperçu G209.
2. Préparer un patch I1 isolé avec horodatage et tests de fraîcheur, sans modifier le runtime partagé.
3. Revoir le patch W1 de résolution DNS : délai, threads orphelins, concurrence et annulation.
4. Préparer les tests du worker Memory : suppression prouvée, lecture échouée, contrôle des droits de profil.

Tâches GPT :
1. Réviser l'intégration des corrections Memory et les tests.
2. Préparer le worker de réconciliation sans mutation de production.
3. Examiner W1 avant application.

Aucune fusion main, aucun déploiement VM. La publication de cette fiche n'active pas une session Claude.
