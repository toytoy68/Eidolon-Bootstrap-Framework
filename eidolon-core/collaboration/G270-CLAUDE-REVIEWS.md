# Dix contre-revues G270

Bases : sources de la branche Core après C-MSG-G270, Memory 76d664013d4e018212682c5aa56305bea0c41db6. Vérifier les SHA exacts avant travail. Branche Claude indépendante ; ne pas réécrire les fichiers de Codex en parallèle. Pour chaque tâche : attaque discriminante, preuve rouge si défaut, correction proposée et limites. Aucune VM réelle ni corpus privé.

| Nº | Sujet | Résultat attendu |
| --- | --- | --- |
| 1 | API appairée et profils | Jeton de lecture refusé, profil/acteur/racine non imposables par la requête, lecture croisée impossible |
| 2 | Mémorisation après coupure | Doubles confirmations concurrentes, perte de réponse après commit, reprise exacte sans doublon ; conflit de clé refusé |
| 3 | Liaison Memory | Même racine sous deux identités refusée, liaison changée/absente pendant service, tokens lecture/écriture distincts |
| 4 | Passages incrémentaux | Réemploi seulement sous bonne preuve ; changements d'archive, panne/copieur/alias et activité conservent ancien alias |
| 5 | Activité entre VM | Observation fraîche/périmée, arrêt/reprise Core, demande longue, changement d'heure ; un poll ne crée pas d'activité |
| 6 | Quotas Internet | Deux clients d'un profil, concurrence, crash et redémarrage, horloge reculée, aucun renvoi implicite |
| 7 | Transport Internet | Adresse privée et redirections, requête exactement confirmée, source vide/inaccessible non inventée |
| 8 | Fichiers NAS/PC | Traversées, liens, objets spéciaux, fichier trop grand/changé ; aucune écriture et aucun transfert PC implicite |
| 9 | Windows | Parsing PS 5.1, empreintes, aperçus sans effet, conflit startup, cycle tray/fenêtre/tunnel ; séparer CI et PC physique |
| 10 | Livraison | Manifestes/pins/36 cas, unités/templates incomplets non installés, contradictions docs/rapport et rollback |

Ne pas désactiver un test rouge pour rendre le lot vert. Les changements purement documentaires sont séparés des défauts fonctionnels ; un accord de revue n'autorise pas le déploiement.
