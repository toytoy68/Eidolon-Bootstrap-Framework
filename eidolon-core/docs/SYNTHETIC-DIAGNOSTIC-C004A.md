# Diagnostic de service synthétique — C-004a / C-001b

Auteur : Codex/GPT. Date : 05/10/2026. Base : `7800b10`.
Tranche implémentée, sans accès à la VM100, au NAS, à Windows ou à Internet.

## Contrat de mission

`Runtime.create_diagnostic(reference)` et la commande `diagnose` créent une
intention typée persistante `service_diagnostic.synthetic`. Le code résout la
référence dans le catalogue configuré : identifiant canonique, capacité
`service.observe`, empreinte du catalogue. Une référence absente, ambiguë ou sans
capacité donne BLOCKED/CLARIFICATION avant rappel et avant modèle. L'alias
`service` est volontairement ambigu entre `sim-memory` et `sim-nas`.

Le plan doit contenir exactement un appel `service.observe.synthetic` avec
`{"target": "identifiant-canonique"}`. La politique exige à la fois le nom de
l'outil autorisé, son effet `none`, une capacité déclarée `none` et une permission
explicite pour le couple cible/capacité. Une déclaration de capacité ne donne
pas de permission. La cible, le catalogue et les permissions sont figés dans la
configuration de mission ; une reprise avec une configuration différente bloque.

Le profil de démonstration autorise explicitement les trois fixtures embarquées.
`--allow-target` remplace ces permissions ; plusieurs occurrences sont possibles.
L'API Python accepte `allowed_targets=[]` pour tout refuser. `--targets` charge
un catalogue JSON de 1 Mo maximum ; ses destinations sont des déclarations,
jamais des adresses contactées. Seuls les trois identifiants de fixtures sont
exécutables par l'outil présent, même avec un autre catalogue.

## Preuve et issue

Le fournisseur simulé produit une observation à six champs : cible, état,
source, indicateur synthétique, UUID et date UTC. Le vérificateur contrôle le
schéma exact, la cible, l'état attendu d'après la fixture indépendante du modèle,
la provenance et une date avec fuseau, non future et âgée d'au plus 60 secondes.
Cette borne est versionnée dans la configuration de l'outil. L'empreinte du
résultat et la liaison cible/capacité/catalogue restent dans l'appel persistant.

Une observation vérifiée `DOWN` ou `UNREACHABLE` atteint l'objectif de diagnostic :
**SUCCEEDED décrit la mission, pas la santé du service**. Un résultat non vérifié
n'atteint jamais cet objectif. Le résultat expose l'observation datée, les preuves
compactes et les réserves mémoire. L'observation est petite et également présente
dans `calls[].output` ; ce n'est pas un mécanisme de stockage de documents.

Le rappel reste une étape obligatoire ; une panne mémoire bloque et reste
reprenable. Un rappel valide vide suffit comme contexte de ce diagnostic,
contrairement à la mission de statistiques qui exige des extraits. Un contenu
mémoire affirmant que le NAS fonctionne n'est jamais une observation. Le champ
`_core_mission` transmis au modèle est construit par le runtime et remplace un
éventuel homonyme mémoire ; le précontrôle vérifie ensuite le plan indépendamment.
Aucun statut épistémique n'est promu.

## Reprise

Le protocole durable existant est réutilisé. Une interruption après sauvegarde
du résultat reprend la vérification sans refaire l'outil. Un reçu non vérifié
périmé échoue ; créer une nouvelle mission pour obtenir une nouvelle observation.
Une interruption à effet inconnu reste en revue : adoption explicite du reçu,
revérification, puis reprise, ou abandon. Aucun rejeu automatique.

Une observation déjà VERIFIED ou une mission terminale reste une preuve
historique ; `run` ne la rafraîchit pas. Un nouveau diagnostic exige une nouvelle
mission. La fraîcheur utilise l'horloge locale ; ce prototype ne prouve ni
synchronisation distante, ni authenticité cryptographique de télémétrie.

## Exécution

Depuis `eidolon-core/`, Python 3.11+ sous Linux/POSIX, aucune nouvelle dépendance :

```bash
PYTHONPATH=src:. python -m examples.service_diagnostic_demo
PYTHONPATH=src python -m eidolon_core --profile service-sim --format human --state /tmp/eidolon-services diagnose nas
PYTHONPATH=src python -m eidolon_core --profile service-sim --state /tmp/eidolon-services diagnose nas --create-only
PYTHONPATH=src python -m eidolon_core --profile service-sim --state /tmp/eidolon-services run m-ID
PYTHONPATH=src python -m eidolon_core --profile service-sim --state /tmp/eidolon-services show m-ID --events
PYTHONPATH=src python -m eidolon_core --profile service-sim diagnose service
PYTHONPATH=src python -m eidolon_core --profile service-sim --allow-target sim-memory diagnose nas
```

Les deux dernières commandes retournent 2, sans appel d'outil. `diagnose
--create-only` retourne 0 pour une création ; garder les mêmes options lors de
`run` et `reconcile`. Le profil par défaut `text` reste compatible avec les
missions de statistiques antérieures.

## Validation et prochaine tranche

Les résultats exécutés sont consignés dans
[le bilan C-004a](validation/2026-10-05/codex-c004a/README.md). Les nouveaux tests
couvrent états de santé, sélection, permissions, paramètres, plan mal formé,
indisponibilité mémoire/modèle, injection mémoire, preuve incorrecte/périmée,
annulation et reprise avec/sans reçu sauvegardé. Les interruptions de processus
SIGKILL du socle restent dans la suite de régression ; les frontières nouvelles
emploient des interruptions injectées et une horloge simulée pour la péremption.

C-004 réel reste ouvert : transport de lecture authentifié, politique réseau
(identité/destination/redirection), fraîcheur de télémétrie distante et recette
hors ligne. C-001 A–D complet, reformulation de demande et révision de plan
restent ouverts. Le modèle est simulé ; aucun moteur ni GPU n'est qualifié.
Claude prend séparément la qualification documentaire V100, le validateur pur
de rapports et la contre-revue du socle : C-TASK-G003/G002/G001.
