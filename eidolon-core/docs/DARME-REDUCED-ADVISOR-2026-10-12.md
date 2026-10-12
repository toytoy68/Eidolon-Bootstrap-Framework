# DARME : relecture et conseiller réduit — 12 octobre 2026

Base de revue : C144 / 7f7bb3a. Code validé localement : d6805fb7eae62a262ce6a5877aa3d7b1e4cb6b8e. Publication sur feat/eidolon-core-v0.1 ; lot communication G146–G151 laissé à Claude.

## R6 et journal

La relecture valide les enregistrements puis construit une projection bornée en mémoire : alertes critiques non acquittées, puis warnings non acquittés, puis événements les plus récents. Les alertes dépassant la projection sont comptées dans unrepresented_alerts et gardent le badge rouge. Les événements omis sont signalés par unrepresented_events ; la visibilité reste partielle. Aucun événement n'est supprimé automatiquement.

Admission du journal : 100 000 événements et 64 Mio de base SQLite par défaut, limites configurables ; transaction BEGIN IMMEDIATE pour empêcher une course entre contrôle du quota et insertion. Les doublons identiques restent idempotents à quota atteint. Une saturation refuse l'écriture avec JournalCapacityError ; le futur service doit signaler cette perte de collecte. Une base historique au-delà de la limite reste relisible. Le quota concerne la base, pas tous les fichiers temporaires de transaction : le futur service doit aussi avoir un quota de répertoire.

Les acquittements nouveaux ont une date UTC par défaut ; une ancienne ligne migrée conserve NULL plutôt qu'une date inventée. Même acteur/motif sans date explicite retrouve le reçu ; une autre date explicitement fournie est refusée.

La santé des sources expire via une horloge monotone et un TTL par défaut de 60 secondes. Un recul de cette horloge ou une sonde périmée dégrade la visibilité. L'alerte connue reste rouge. Ce mécanisme ne signe pas les heartbeats : l'authenticité et les séquences anti-rejeu des collecteurs restent à implémenter avant le service permanent.

## Contrat du conseiller

Entrée : niveau décidé par le moteur, catégorie et observation bornées, extraits numérotés. Sortie du modèle : uniquement explanation et sources=[1,2]. Aucun triage ni action. Le code résout les numéros en information_id@revision ; un numéro absent, booléen ou chaîne est refusé.

Conseil accepté ou texte fixe : Advice porte advisory_only=true et authorizes_execution=false. La sortie n'a aucun lien vers un exécuteur, ne modifie pas le badge ni l'acquittement, et n'est pas écrite automatiquement dans Memory.

L'adaptateur Ollama reprend une configuration locale déjà validée, un prompt borné, réponse limitée à 16 Kio et un timeout demandé au transport de 15 secondes maximum. Une indisponibilité, réponse tronquée, schéma invalide, référence invalide ou incohérence détectée entraîne le texte fixe. La file basse priorité, la limite de fréquence et l'annulation du conseil en concurrence avec le dialogue restent à câbler dans un service distinct.

Les contrôles textuels sont conservateurs et limités : niveaux explicitement contradictoires, négation d'une alerte connue, ordres et certaines constructions modales. « Ne redémarre pas » n'est pas refusé comme un ordre positif. Ce filtre peut se tromper et ne prouve ni cohérence sémantique complète ni immunité aux injections. La frontière d'autorité est le logiciel sans interface d'exécution, pas le filtre LLM.

Le retrait de formats de secrets connus est appliqué au prompt et certaines sorties ; ce n'est pas un détecteur universel de secrets. Les collecteurs doivent retirer les informations sensibles à la source et avant le journal.

## Vérifications

- Sonde R6 de Claude reproduite en échec avant correctif, puis réussie.
- 52 tests ciblés (projection, journal, quota disque, concurrence, migration, acquittements, fraîcheur, conseiller, transport, troncature et R6) réussis.
- Suite complète Core : 1 494 tests exécutés avec toutes les intégrations Memory opt-in, zéro ignoré.
- Client connecté : 112 tests Node réussis, 27 ignorés (notamment navigateur non disponible), zéro échec. Pas une recette Windows matérielle.
- Memory : 2 018 tests pytest et 12 subtests réussis sur un corpus temporaire isolé, source f713623. Premier lancement par unittest dans le venv de recherche était inadapté et manquait pytest ; logs conservés, recette finale dans le venv du dépôt.

## Recette réelle des modèles

Le contrat réduit est comparé sur les 14 scénarios A existants et 40 nouveaux scénarios B figés avant leurs sorties. Gemma3 1B, Qwen3 1.7B, Granite4 350M et Gemma4 12B témoin : 54 cas × 3 graines. Les trois autres petits modèles antérieurs répètent les 14 cas A. CPU forcé pour les six petits candidats, témoin GPU séparé. Les identifiants canoniques ne sont plus demandés au modèle.

Les résultats et mesures détaillés sont dans validation/2026-10-12/darme-reduced/REPORT.md. Les métriques automatiques ne remplacent pas une relecture humaine indépendante de 20 explications : le secours CPU reste non adopté jusque-là. La présence d'un numéro valide ne prouve pas que le contenu de la source soutient l'affirmation.

État réel : bibliothèque et adaptateur livrés ; aucun service DARME permanent ou remédiation activé. La décision logiciel permanent + conseil Core ponctuel reste la cible, avec repli fixe. Les collecteurs authentifiés, API de statut et isolation du compte demeurent les travaux suivants.
