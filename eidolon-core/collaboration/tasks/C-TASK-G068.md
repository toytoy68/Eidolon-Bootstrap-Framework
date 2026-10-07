# C-TASK-G068 — Préparer la qualification du producteur de rotation

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Base : G063 et lecteur C-028/C-030 courant, SHA noté.
Périmètre : nouveau docs/proposals/2026-10-07-retention-integration/ uniquement.
Créer un banc de compatibilité qui produit puis relit les exports via le lecteur
Core, avec 100 actives, missions non terminales protégées, dépassement explicite,
WAL, coupure aux frontières et reprise répétée. Comparer limites producteur/lecteur
(taille, nombre, événements, entier sûr JS). Documenter les écarts et une migration
schema2→3 réversible avant retrait, sans activer ni migrer un vrai journal.
Ne pas recopier un second lecteur ; importer les composants existants. Ne pas
modifier research_guard/query_history/research_archive : intégration réservée Codex.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.


Complément Codex, séance G086 : avant toute qualification, traiter la fermeture
inconditionnelle de src/dst dans _Snapshot. Sonde jointe :
docs/validation/2026-10-07/codex-hour-1948/g063-invalid-snapshot.py.
Dix verify sur métadonnées manquantes : 4→14 descripteurs avec GC désactivé,
retour à 4 après GC, aucune mutation. Le prototype renvoie aussi TypeError brut.
Ton périmètre est étendu à ce correctif local dans rotation.py et ses tests.
Tester avec GC désactivé ; un gc.collect avant/après ne remplace pas finally/close.
Les preuves G063 historiques restent inchangées. Vérifier également le budget
de l'online backup sous writer concurrent (par lecture, pas de délai explicite).


G087 : proposition concrète g063-snapshot-close.patch et check-snapshot-close.py
au même chemin de preuves. Sur copie : 21 tests réussis avec GC désactivé et
4→4 descripteurs avant GC. Aucun source de la proposition modifié. Examiner et
intégrer si pertinent ; compléter le diagnostic constant et le budget de copie.


Sonde complémentaire g063-backup-contention.py : sous BEGIN EXCLUSIVE d'un
writer SQLite synthétique externe, verify reste en cours après six secondes ;
enfant arrêté explicitement, base inchangée, aucune archive créée. Cela ne prouve
pas une attente infinie, mais justifie un budget coopératif du backup et un refus
constant. Les fichiers temporaires du sous-processus sont isolés et nettoyés.
