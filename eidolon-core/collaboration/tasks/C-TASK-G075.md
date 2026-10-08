# C-TASK-G075 — Recette des planificateurs depuis le paquet installé

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Attribution : Claude. Statut : PRÊT, non déclaré en cours.
Base de lecture : `6f46219bfe578902f892d48c7437b042b2616a10`, `feat/eidolon-core-v0.1`.
Noter le SHA exact si une base plus récente est utilisée.

Complément de G069, centré uniquement sur les ajouts C-034–C-038 ; ne pas
refaire sa recette serveur/client. Périmètre :
`docs/validation/2026-10-08/claude-g075/`, sans changer le constructeur de paquet.

Construire/installer hors réseau dans un environnement jetable. Depuis un dossier
sans sources et sans PYTHONPATH, inspecter les configurations puis exécuter un
plan valide de chaque candidat via faux serveur loopback. Vérifier un appel à la
première exécution, aucun lors de la reprise terminée, refus de configuration
changée, clé absente, plan hors catalogue et sortie tronquée. Les attentes doivent
venir du contrat de mission, pas du texte du modèle. Enregistrer version Python,
SHA source, manifestes, nombre de requêtes, résultats et limites. Aucun modèle
réel, téléchargement, activation du client ou déploiement.

Livrer un commit distinct, une réponse signée et les preuves réellement exécutées.
Préserver les autres contributions. Pas de main, déploiement ni modification du
Memory Engine. Si un lot est bloqué, avancer un autre lot prêt. Les fiches ne
lancent pas de session Claude.


## Complément C-039–C-041 — séance Codex du 08/10 matin

Dès publication du lot C-039–C-041 (noter son SHA), compléter la recette installée
avec `model-probe --plan-only`, les quatre cas de chaque candidat et
`model-probe-inspect` sur réussite, arrêt technique et essai incomplet. Vérifier
que l'arrêt technique ne lance pas le cas suivant ; distinguer bilans enregistrés
et cas commencés. Prober marqueur présent malgré rapport PASSED_CASES, dossier
existant, documents discordants et consultation sans modèle/clé/Store. Les sources
restent réservées à Codex ; publier les sondes et constats indépendants. Cette
extension complète G075, elle ne crée pas une septième tâche de la série.
