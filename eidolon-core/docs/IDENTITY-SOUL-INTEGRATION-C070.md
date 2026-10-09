# C-070 — Identité, SOUL et personnalité évolutive : plan d'intégration

Date : 2026-10-09. Statut : étude d'architecture, **aucun runtime livré**.
Source normative de personnalité : `/SOUL.md` (administrateur), `/SOUL-EVOLVING.md` (propositions validées uniquement).
Référence d'identité : Eidolon Core ; Memory Engine conserve l'historique, il ne décide pas de l'identité.
Ne pas modifier le flux C-068/C-069 tant que sa recette n'est pas terminée.

## Décisions retenues

1. L'identité de l'instance est indépendante du matériel, du modèle, de l'OS et du processus ; son histoire peut évoluer.
2. La personnalité initiale est un socle administrateur en lecture seule pour les agents.
3. La personnalité évolutive est une couche distincte, soumise à une validation, un journal et un rollback.
4. L'ignorance, l'échec et l'étude sont acceptables ; inventer une réponse, une observation ou un résultat pour masquer l'échec est interdit.
5. Le modèle de soi peut exploiter une télémétrie sourcée et datée, sans inventer l'état du vaisseau.
6. Le Policy Engine reste seul responsable des permissions : aucune instruction SOUL ne peut les élargir.
7. La conscience fonctionnelle est une hypothèse de travail philosophique, non une preuve de conscience subjective.

## Contrat proposé

- `IdentityManifest` : `instance_id` immuable, `created_at`, `lineage`, `schema_version`, `origin`, `revision`. Création explicite une seule fois ; sauvegarde indépendante de la mémoire vectorielle. Pas de régénération silencieuse après perte du manifeste.
- `PersonalitySnapshot` : empreintes SHA-256 du socle et de la couche évolutive, version, date de chargement, validation, avertissements. Composition déterministe et taille bornée. Une absence du socle doit bloquer la composition, pas générer une personnalité de secours inventée.
- `PersonalityProposal` : identifiant, modification structurée, observations datées et références, auteur, impact, statut, validation, ancienne/nouvelle empreinte. Aucun agent ne doit disposer d'une écriture directe sur `SOUL.md`.
- `SelfObservation` : source, timestamp, TTL, état mesuré, degré de confiance ; données périmées ou absentes présentées comme inconnues.
- `MissionOutcome` : conserver `SUCCESS`, `FAILED`, `UNKNOWN`, `NEEDS_RESEARCH`, `BLOCKED` comme **taxonomie conceptuelle** ; ne pas modifier les enums ou invariants actuels sans audit de compatibilité. Séparer statut d'exécution, résultat épistémique et raison d'arrêt.

## Plan d'implémentation, par ordre

**P0 — Audit et spécification (sans migration)** : cartographier la construction des prompts, les contrôles d'autorisation, la gestion des statuts de mission, les snapshots, la persistance et la restauration. Établir la table de compatibilité avant tout changement d'enum ou de schéma.

**P1 — Chargement en lecture seule** : module de lecture des fichiers autorisés par chemin configuré, contrôle de taille, encodage, empreinte et ordre de composition ; empêcher injection de fichiers provenant d'un outil ou d'un souvenir. Ne pas confondre contenu SOUL et politique système.

**P2 — Identité persistante** : manifeste signé ou protégé selon le modèle de menace, versionné et restaurable ; tests de clone et de migration. Une copie exécutée en parallèle doit recevoir une filiation distincte.

**P3 — Évolution contrôlée** : propositions en attente, validation explicite selon criticité, écriture atomique, journal, rollback ; réévaluation des prompts et de la suite de qualification après changement.

**P4 — Observabilité et réflexion** : télémétrie du vaisseau, mémoire autobiographique et réflexive avec provenance, sans écriture automatique non contrôlée dans les souvenirs canoniques.

**P5 — Mission Manager** : rendre visibles l'incertitude et le besoin d'étude, sans transformer un résultat non vérifié en succès. Conserver les raisons et les preuves.

## Tests de réception minimaux

- Socle absent, corrompu, trop volumineux ou modifié sans autorisation : refus explicite, aucune mutation.
- Un outil tente d'écrire le socle : rejet par permissions OS et couche applicative.
- Changement évolutif incompatible avec le socle : rejet et journal.
- Crash entre validation et écriture : récupération atomique, aucun état partiel.
- Rollback : empreinte précédente restaurée et historique conservé.
- Changement de modèle : même identité ; personnalité recomposée ; tests agent rejoués.
- Clone indépendant : nouvelle branche de filiation, sans écraser l'identité source.
- Réponse inconnue : sortie honnête, sans résultat inventé.
- Télémétrie absente/périmée : inconnue, pas d'affirmation de perception.
- Vérification que les règles SOUL ne contournent jamais le Policy Engine.

## Répartition pour revue ChatGPT / Claude

ChatGPT : contrats, menaces, matrice de tests, frontières Core/Memory/OS.
Claude (à sa reprise) : revue contradictoire du contrat, cartographie des points d'injection dans le Core, propositions de tests et compatibilité avec le Mission Manager. Aucun travail n'est déclenché automatiquement pour Claude.

## Conditions de livraison

Pas de fusion `main`, pas de déploiement VM, pas de modification Memory Engine.
Toute implémentation doit être testée en isolation puis validée sur VM et PC avec consentement explicite.
