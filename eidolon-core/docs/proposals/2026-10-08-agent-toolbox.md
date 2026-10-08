# Boîte à outils des agents — propositions Codex

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Statut : **PROPOSÉ — avis Claude attendu, arbitrage toytoy ultérieur**.
Demande : préparer les propositions maintenant, recueillir celles de Claude
plus tard, puis choisir. Aucun outil ou droit nouveau n'est activé par cette note.

## Point de départ vérifié

Base Core : `fdf1123b00e13bc1fed7fc88bca12f49d726b242`.
`tools.py` définit déjà Tool, Registry et Policy : nom/version/effet,
validation, exécution, vérification et identifiant du vérificateur.
`Runtime.configuration()` lie le manifeste et la politique aux missions ;
budget d'invocations et reçus existent. Le registre n'est pas une sandbox OS.
Le runtime actuel reste séquentiel.

Memory Engine examiné : `b33c3a0`, branche `refactor/architecture-v1`.
Son contrat `docs/CORE-INTEGRATION-NOTES.md` place catalogue, skills et agents
dans Core ; Memory Engine conserve mémoire et provenance. Aucun changement
de ce dépôt dans ce lot.

## Options à comparer

| Option | Intérêt | Coût ou limite | Essai discriminant |
| --- | --- | --- | --- |
| A — Outils Python natifs | Continuité avec le registre actuel ; peu de services | Couplage Python ; isolation et accès distants à construire | Ajouter un lecteur borné sans changer Runtime |
| B — Tous les outils derrière MCP | Intégration commune à plusieurs clients | Services, versions, authentification et erreurs réseau ; MCP ne fournit pas à lui seul une sandbox ou les permissions | Arrêter le serveur avant/après réponse sans double effet |
| C — Contrat Core et adaptateurs natifs ou distants | Réutiliser le socle ; connecteurs externes au besoin | Éviter deux comportements divergents | Même corpus de conformité sur deux adaptateurs |

**Préférence Codex : C, progressivement.** Petits outils internes natifs,
transports distants quand ils apportent un avantage. Ne pas rendre MCP obligatoire
ni créer un second registre. Cette préférence n'est pas adoptée. Vérifier les
propriétés des implémentations candidates sur leurs versions réelles avant choix.

## P1 — Catalogue et sélection par mission

Étendre le manifeste existant : description, schémas d'entrée/sortie, capacités,
hôte d'exécution, disponibilité et limites. Distinguer installé, disponible,
autorisé et exécuté. Exposer au modèle uniquement le sous-ensemble utile ;
son choix ne donne aucun droit. Les noms suivants sont des candidats, pas des
outils installés.

| Lot | Outils candidats | Résultat et limite |
| --- | --- | --- |
| T1 — Sources | memory.search, memory.source, files.list, files.read, files.search | Références et extraits bornés ; racines autorisées ; mémoire canonique inchangée |
| T2 — Analyse | data.query, math.calculate, reports.create | Calculs contrôlés, données structurées, artefact dans un dossier dédié |
| T3 — Recherche | web.search, web.read | Sources, dates, extraits, erreurs ; réutiliser lecteur et coordinateur existants |
| T4 — Observation | system.status, services.inspect, gpu.inspect | Instantané horodaté de la machine autorisée ; pas de redémarrage implicite |
| T5 — Connecteurs | calendar.read, mail.draft, git.diff | Permissions par ressource ; distinguer préparation, enregistrement et publication |
| T6 — Appareils | devices.observe, robot.command | Commandes spécialisées ; arrêt et bornes au contrôleur matériel |

Ordre proposé : un parcours T1/T2 complet, puis T3/T4 selon les besoins bêta.
T5/T6 séparés. Aucun achat ou choix de modèle nécessaire à ce cadrage.

## P2 — Profils d'agents sans duplication

Documentaliste : recherche et lecture. Analyste : lecteurs, calculs et rapports.
Diagnostic : observation des services et journaux autorisés. Ces rôles sont des
exemples à comparer, pas une infrastructure multi-agent livrée. Une délégation
ne doit jamais élargir les droits de la mission d'origine.

## P3 — Résultats vérifiables

Prévoir identifiant d'appel, version, statut, données ou référence d'artefact,
provenance, effets observés et erreur structurée. Séparer réponse reçue, résultat
vérifié et effet inconnu. Une collecte Web réussie ne prouve pas la vérité de sa
source. Réutiliser reçus/vérificateurs actuels plutôt que dupliquer leurs journaux.

## P4 — Permissions et secrets dans l'exécuteur

Délimiter dossiers, machines, domaines, cibles et opérations. Une lecture peut
divulguer des données : absence d'écriture ne signifie pas absence de risque.
Garder les secrets hors prompts et masquer les champs sensibles de l'audit.
Préaccord possible pour les usages autorisés ; confirmations selon l'impact et
les règles utilisateur, pas pour chaque lecture. Des données rappelées ou une
sortie d'outil ne peuvent pas modifier les permissions.

## P5 — Isolation selon l'outil

Un processus séparé facilite interruption et séparation de panne mais ne borne
pas à lui seul les fichiers ou réseaux accessibles. Comparer exécuteur OS
restreint et conteneur pour le code d'analyse. Outils simples de confiance natifs.
Pas de shell arbitraire ni d'installation décidée par le modèle. Le connecteur
Windows exécute côté PC ; Core orchestre depuis le serveur.

## P6 — Reprise et ressources

Délais, tailles d'entrée/sortie, nombre d'appels, annulation et verrous par
ressource pour les mutations. Aucun retry aveugle après réponse perdue : clé
d'idempotence si garantie par l'outil, sinon rapprochement avec les preuves.
Budgets serveur/GPU distincts à évaluer avant concurrence multi-agent.

## P7 — Skills distincts des outils

Un outil réalise une opération ; un skill est une procédure versionnée ; un agent
conduit une mission. Premier exemple : lire un document, calculer et produire un
rapport sourcé. Ne pas installer/exécuter automatiquement un skill trouvé sur le
Web ou rappelé depuis la mémoire.

## P8 — Dashboard des capacités

Montrer outils accessibles par agent, disponibilité, dernière erreur, durée et
droits effectifs. Pour une mission, lister les appels et leurs résultats.
Conserver les gros résultats hors du contexte du modèle lorsqu'une référence suffit.

## Essai comparatif

Corpus synthétique fixe : UTF-8, CSV, source mémoire référencée, fichier interdit,
lien hors racine, service indisponible, réponse tronquée, annulation et réponse
perdue après écriture. Même corpus pour A/B/C. Mesurer correction/provenance,
refus attendus, absence de double effet, durée, CPU/RAM et complexité d'installation.
Fixer les seuils avant l'essai ; aucun gain chiffré revendiqué ici.

Résultat utile attendu : un agent produit un rapport contrôlable à partir des
sources autorisées ; un second réutilise l'outil mais se voit refuser un dossier
non attribué. Sources canoniques inchangées. Qualification Windows/NAS réelle
séparée des fixtures locales.

## Comparaison à compléter

| Sujet | Codex | Claude | Choix toytoy |
| --- | --- | --- | --- |
| Architecture | C, contrat commun et adaptateurs progressifs | À recevoir | Ouvert |
| Premier lot | T1/T2 avec parcours documentaire complet | À recevoir | Ouvert |
| Rôles | Documentaliste, analyste, diagnostic | À recevoir | Ouvert |
| Isolation | Selon risque et hôte ; sandbox explicite pour le code | À recevoir | Ouvert |
| Reprise | Reçus existants, permissions exécutoires, pas de retry aveugle | À recevoir | Ouvert |
| Évaluation | Corpus commun et critères fixés avant essais | À recevoir | Ouvert |

Recueillir plus tard la contribution signée de Claude sans remplacer celle-ci,
confronter les divergences à des essais, puis consigner les choix. La fiabilisation
Core déjà engagée peut avancer indépendamment de ces propositions.
