# Consignes pour les agents — projets Eidolon

## Reprise et collaboration Core

Pour le chantier Core, commencer par [eidolon-core/ECHANGES.md](eidolon-core/ECHANGES.md)
et suivre le [protocole de collaboration](eidolon-core/collaboration/README.md).
Vérifier les messages reçus, déclarer le lot pris en charge et préserver les
contributions de l'autre auteur. Les propositions du brainstorming ne valent
pas décision utilisateur ; les fichiers ne lancent aucune session d'agent.

## Identité et présentation

Avant de créer/modifier un en-tête source, une CLI destinée à l'utilisateur ou
un parcours d'installation, lire et appliquer
[Eidolon Presentation Standard v1](standards/EIDOLON-PRESENTATION-v1.md).

- Identité exacte : **Eidolon Core Technologies (ECT)**.
- Devise exacte : **Local AI • Modular • Reliable • Reproducible**.
- Garder le nom spécifique du produit : Bootstrap, Core ou Memory Engine.
- Utiliser les modèles d'en-tête du standard pour les nouveaux fichiers source.
- Réutiliser les fonctions d'affichage communes du composant ; pour Core,
  `eidolon_core.presentation`. Éviter une nouvelle bannière par commande.
- Une sortie JSON reste strictement exploitable par machine ; réserver la
  décoration au mode humain. Les statuts et codes de retour restent inchangés.
- `[OK]` exige une vérification réelle. L'affichage ne donne jamais une permission
  et ne prouve pas à lui seul une installation ou une exécution.

## Périmètre des changements

Le standard ne demande pas de réécrire globalement les fichiers existants.
Harmoniser les composants dans des lots explicites, sans altérer leur logique
métier. Les installateurs ont des effets système : ne pas les exécuter ou les
`source` pour examiner leur présentation.

`eidolon-core/` est un sous-projet autonome. Maintenir la séparation avec les
installateurs Bootstrap. Le moteur mémoire est une dépendance distincte ; ne
pas modifier un autre dépôt au seul motif d'appliquer ce standard.

## Réutilisation dans un autre dépôt Eidolon

Copier `standards/EIDOLON-PRESENTATION-v1.md` avec sa version, puis reprendre la
section « Identité et présentation » dans le `AGENTS.md` de ce dépôt en adaptant
les chemins et le module d'affichage. Conserver ses autres consignes. Pour les
agents qui ne lisent pas AGENTS.md, utiliser le bloc de consigne du standard.
