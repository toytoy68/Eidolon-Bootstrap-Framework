# C-014a — preuve locale, 07/10/2026

Base de code : 51942215 (C-013 publié). 99 tests ciblés réussis, dont
22 nouveaux tests de garde. Commande dans targeted-tests.txt ; aucun Internet.

Vrais processus arrêtés brutalement : avant contact, pendant contact, avant
la pause, après la pause. À chaque reconstruction : zéro nouveau contact,
WEB_RESEARCH_UNCERTAIN. Un vrai serveur HTTP loopback a renvoyé 429 avant
l'arrêt du lecteur : un seul contact constaté malgré la seconde invocation.

Un processus encore vivant bloque exécution/revue ; après SIGKILL l'intention
reste incertaine. Tests SQLite : échec avant intention (zéro appel), après
rapport (intention conservée), pendant revue (rollback intégral). Tests de
révision, corruption/audit, plafond d'historique, horloge, absence de texte
privé, fichiers privés et CLI sans création ni relance.

Garde globale optionnelle, pas le journal par saut complet. Pas de validation
Windows, stockage réseau, coupure électrique ou fournisseur externe.

Suite Python complète : 677 tests exécutés en 120,337 s, **671 réussis**,
6 intégrations mémoire non exécutées. Journal full-python-tests.txt.
