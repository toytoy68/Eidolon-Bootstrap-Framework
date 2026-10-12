# Dashboard — lots Claude G155–G160, 12 octobre 2026
Demande explicite de toytoy : vérifier C146 puis donner le travail de déploiement du dashboard et ajouter le monitoring machine.
Codex a relu le diff 73fa2a5..674255f et rejoué sur Core 59 tests test_comm*.py et 14 tests communication Node : réussis. ResourceWarning de socket observé ; aucun vrai moteur/caméra/micro ainsi qualifié.

**Feu vert au câblage proposé par C146** dans build.js, index.html et main.js. Claude réserve ces fichiers et leurs tests. Codex réserve darme*.py, sondes, unités et endpoint privé ; ne pas modifier ces fichiers sans coordination.

| Lot | Travail et résultat attendu |
|---|---|
| G155 | Raccorder communication.js au build et à la page, commandes visibles, capture éteinte, transcriptions dans le champ sans envoi automatique ; recompiler app.js. |
| G156 | Dashboard machine : cartes CPU, charge, RAM, swap, disque et services, badge DARME avec périmètre/fraîcheur visibles ; jamais afficher gris comme sécurisé ni inventer des métriques GPU absentes. |
| G157 | Adaptateur serveur de monitoring séparé, authentifié par clé client appairée, CORS/Host exacts, lecture seule du socket DARME. Refuser jeton lecture public et client révoqué, borner lecture/délai, aucune commande fournie par le navigateur. Réserver un module monitoring séparé et un port loopback distinct, proposer le contrat avant activation. |
| G158 | Tests dashboard : indisponibilité, données périmées, erreur/refus, machine manquante, aucune capture au chargement, polling borné et interrompu à déconnexion ; page texte reste utilisable. |
| G159 | Préparer installation/reprise et tunnel Windows des services nécessaires, cohérence origin/ports, guide de démarrage et rollback. Ne pas écraser les configs actives ou copier des clés dans Git. Tu n'as pas d'accès VM : fournis scripts et prévols revus, Codex exécutera et publiera la recette VM. |
| G160 | Revue de sécurité et recette de bout en bout ; distinguer moteurs simulés, appels VM réels et périphériques Windows non testés. Corriger le ResourceWarning rencontré au rejeu ; publier preuves et réservations. |

Contrat de télémétrie réservé par Codex : socket privé /run/eidolon-darme/status.sock, requête STATUS\n, JSON eidolon-darme-service/1. Champs existants badge, visibility, sources, generated_at, scope, authorizes_execution=false. Nouveau champ machine prévu : CPU/charge/RAM/swap/disque, sans contenu de processus, adresse utilisateur, token ou log brut ; valeurs indisponibles null avec erreur générique. Intervalle 10 s. Source locale distincte sur Core et Memory, sans prétendre disposer du GPU de VM101 à travers le Core CPU. Ne pas imposer de forme aux nouveaux champs tant que le contrat exact n'est pas publié.

L'utilisateur a autorisé modifications/publications/déploiements nécessaires. Cette affectation vaut coordination des fichiers indiqués ; elle ne lance pas une session et ne donne aucun accès supplémentaire à Claude.
