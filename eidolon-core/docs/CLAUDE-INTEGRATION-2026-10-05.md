# Intégration des lots Claude et corrections C-REV-003

Auteur : Codex/GPT, 05/10/2026, Europe/Paris. Aucune heure estimée.
Source : `ccr-d3dc80a2-wouvy3`, commit
`c2792d6bd0dd9595c9b187af6544b13b8914c20f`. Destination :
`feat/eidolon-core-v0.1`, auparavant `be27f79af9e7609a073013781cf73c7fb73568e4`.
Cette dernière est ancêtre de c2792d6 : intégration sans conflit par avance rapide,
puis commit de corrections Codex. Historique et auteurs Claude conservés.

## Travail reçu et vérifié

- C-REV-003 : revue et sondes, N-01/N-02 fermés dans leurs hypothèses locales.
- C-CLAUDE-001 : catalogue pur targets, 11 tests, sans raccordement runtime/CLI.
- C-CLAUDE-002 étape 2 : adaptateur Ollama optionnel, 14 tests, injection Python
  possible mais aucune activation CLI ni choix par défaut. Étape 1 V100 à faire.
- Protocole de numérotation par auteur G/C, contributions au brainstorming,
  décision C-D07 rapportée et correction des heures Claude conservés.

Les heures de commit ont été lues via `git log --format='%h %aI %cI %s'` :
revue `de5cb20` à 12:14:20Z, catalogue `2dd6a67` à 12:19:47Z, adaptateur
`12ec3bb` à 12:24:42Z, fusion `36bce83` à 12:27:05Z, correction des dates
`365e1cf` à 12:30:03Z et intégration matérielle `c2792d6` à 12:31:11Z.
En Europe/Paris ce jour-là, ajouter deux heures. Cela vérifie les métadonnées
Git ; ce n'est pas une preuve de l'instant où chaque phrase a été rédigée.

## Défauts et corrections

| Point | Constat | Traitement |
| --- | --- | --- |
| N-09 | Reproduit : effet synthétique puis exception ; no-effect sans confirmation permet un deuxième effet | Confirmation distincte dès que l'autorisation est vraie/inconnue, même avec reçu d'erreur ; test lease-v1/v2 et maintien en revue |
| N-10 | Lecture du code et test : recréer un verrou supprimé après spawn perd l'identité du verrou d'origine | Ouverture sans création après WORKER_SPAWNED ; absence bloquante même confirmée ; abandon possible |
| N-11 | Récupération d'un reçu dans SQLite avant un refus de réconciliation | Comportement conservé et documenté : consulter show --events après refus |
| Catalogue | Reproduit : modifier la portée d'un manifeste modifie le catalogue | Retours détachés sur manifest/get/resolve/lookup ; constructeur direct copiant et validant |
| Options Ollama | Reproduit : le dictionnaire source peut changer les options sans changer model_id | Copie immuable compatible spawn ; model_id reflète aussi un remplacement explicite de configuration |
| Bornes | Scope mesuré en caractères ; un transport injecté peut dépasser la borne de réponse | Octets UTF-8 pour scope ; vérification du corps brut également dans l'adaptateur |

Le scénario d'effet suivi d'erreur produit maintenant **un seul effet et un seul
CALL_STARTED** lorsque no-effect est tenté sans confirmation ; la mission reste
en revue. Une confirmation mensongère ou erronée peut toujours permettre une
relance : c'est une attestation humaine auditée, pas une preuve automatique.
Un reçu positif continue d'interdire no-effect même confirmé. Les tests de
réparation d'un fournisseur n'ayant pas produit d'effet utilisent désormais la
confirmation explicite et vérifient la conservation de l'historique.

Le contrôle du verrou ne constitue pas une protection contre toute suppression,
substitution ou modification hostile du dossier d'état. Aucun nettoyage n'est
introduit et aucune garantie « exactement une fois » n'est annoncée.

## Validation et suite

**94 tests** reproduits sur la base Claude, puis **102 tests Core + 6 intégrations
Memory Engine** réussis ici sous Python 3.12.14. [Journaux et commandes](validation/2026-10-05/codex-claude-integration/README.md).
Démo C-001a toujours exécutable ; pas de qualification d'un modèle réel.

L'étude moteurs pour **2 × V100 SXM2 32 Go sur adaptateur PCIe avec NVLink sur PCB**
reste ouverte et prioritaire pour Claude dans C-CLAUDE-002 étape 1. Le paquet
contient l'adaptateur candidat mais le modèle simulé reste celui de la démo.
Avant raccordement : contrat de capacités transmis au planificateur, budgets
et politique par cible, qualification du protocole avec serveur réel, puis recette
matérielle séparée. Aucun déploiement ou fusion main ; Memory Engine inchangé.
