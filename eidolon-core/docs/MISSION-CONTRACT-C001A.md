# C-001a — Objectif de mission et couverture des preuves

Auteur : Codex/GPT, 05/10/2026, Europe/Paris. Base code : `3cb1ae5` ;
fiches Claude publiées dans `9620c478da5aa22ff5530628c10c5fba01404512`.
Implémentation : commit introduisant ce document. Aucun avis Claude reçu sur ce lot.

## Contrat livré

Le module `objectives` reconnaît **uniquement** la demande exacte de la démo,
`Calculer les statistiques du texte synthétique de démonstration.` Le client
fournit cette demande ; le code choisit le type déterministe. Une autre demande,
même accompagnée d'un plan techniquement exécutable, donne CLARIFICATION avant
le moindre rappel/modèle/outil. Pas de classificateur sémantique implicite.

À la création, `objective` conserve version, type, empreinte de la demande,
outil attendu et périmètre `recalled_snapshot`. Après rappel validé, il lie les
références `information_id@revision` et l'empreinte du bundle entier. Une reprise
vérifie cette liaison et les critères attendus. Le plan du modèle ne contient
aucun champ permettant de choisir ou d'assouplir l'objectif.

Le précontrôle examine les permissions et paramètres de **tout** le plan, puis
exige exactement une étape text.stats par référence attendue. Un doublon ou une
couverture incomplète bloque sans lancer d'outil. Même un autre outil autorisé
par Policy ne remplace pas l'outil attendu par le contrat.

`assess` contrôle la couverture des appels VERIFIED, la correspondance de leur
étape au plan, les empreintes de contexte et sortie. `Store.save` recalcule
l'issue ; SUCCEEDED exige ACHIEVED en plus des contrôles de preuve existants.
Le vérificateur d'outil reste responsable des valeurs. Le catalogue, le registre,
les implémentations Python et le stockage local sont de confiance : ceci n'est
pas une défense contre un opérateur modifiant à la fois base, code et empreintes.

## Statut d'exécution et issue de l'objectif

| Issue `outcome.status` | Signification |
| --- | --- |
| PENDING | Mission créée/en rappel ; critères de sources pas encore liés |
| ACHIEVED | Toutes les références du rappel conservé ont un résultat vérifié |
| NOT_ACHIEVED | Sources connues, aucun résultat vérifié satisfaisant |
| PARTIAL | Certaines preuves acquises, couverture incomplète |
| CLARIFICATION | Demande hors catalogue ou contrat absent/incompatible |
| NO_EVIDENCE | Rappel vide, indisponible ou interrompu avant acquisition du contexte |

`covered_references` et `missing_references` sont persistés et journalisés.
Un plan incomplet refusé n'est pas PARTIAL : ses étapes proposées ne sont pas
encore des preuves. Une annulation après la première de deux étapes est
CANCELLED/PARTIAL ; le reçu vérifié reste dans calls. Si toutes les preuves sont
acquises avant une annulation, l'issue peut être ACHIEVED mais l'exécution reste
CANCELLED sans résultat final, conformément à la priorité de l'annulation.

Un reçu RETURNED, tardif ou récupéré ne compte pas avant le vérificateur. Une
approbation humaine ne qualifie pas les sources : leurs statuts épistémiques,
réserves et provenance restent inchangés.

## Rappel vide, reprise et compatibilité

Un rappel valide vide donne BLOCKED/MEMORY_EMPTY, issue NO_EVIDENCE, sans appel
au modèle. Un `run` explicite peut recommencer ce rappel avec la même configuration
et le même identifiant. Les événements conservent les empreintes des rappels et
leurs issues ; le snapshot conserve le dernier contexte. Un contexte non vide
reste figé pendant la mission. Aucun budget global de tentatives n'est ajouté.

Les missions actives anciennes sans objectif ne sont pas qualifiées après coup.
Elles sont bloquées avec MISSION_CONTRACT_REQUIRED ; conserver les preuves et
créer une mission sous contrat après examen. Une phase EXECUTING reste prioritaire
et passe en revue ; réconciliation/abandon conservent les garanties existantes,
mais une réconciliation ne crée pas de contrat à une ancienne mission. Les
missions terminales historiques retournent leur état d'origine ; la présentation
signale l'absence d'évaluation C-001a. Le schéma SQLite reste v1 avec champs JSON
additionnels. Ne pas reprendre un nouvel état avec une ancienne version du code.

Un plan refusé ne peut pas être changé implicitement à la reprise. Pour corriger
la proposition ou changer de configuration, créer une nouvelle mission. L'édition
révisée d'une proposition et les critères A–D complets restent à implémenter.

## Démonstration et limites

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m examples.objective_demo
PYTHONPATH=src python -m eidolon_core --format human --state /tmp/eidolon-c001a demo
```

La première commande exécute quatre missions synthétiques, vérifie leurs issues,
retourne un bilan JSON et supprime son état temporaire. La seconde conserve un
état inspectable via show/run. Aucun GPU, modèle réel, VM, réseau ou corpus privé.

Le périmètre est **le rappel conservé**, pas toutes les informations susceptibles
d'exister dans le corpus. Troncature, exclusions et rang de rappel restent des
réserves mémoire. Les statistiques ne deviennent ni synthèse sourcée, ni diagnostic
de service, ni preuve de vérité. Le modèle interchangeable est conservé ; aucun
contrôleur réel n'est qualifié. La tâche Ollama confiée à Claude est indépendante.

[Preuves de validation](validation/2026-10-05/codex-c001a/README.md).
