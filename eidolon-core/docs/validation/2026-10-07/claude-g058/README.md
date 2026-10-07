# G058 — contre-revue indépendante de l'historique des requêtes nettoyées (C-019)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G058](../../../../collaboration/tasks/C-TASK-G058.md).

Cible figée : `0050e48`, en copie `git archive`. Ses fichiers
`query_history.py`, `research_guard.py`, `research.py` et
`query_cleanup.py` sont identiques à la base de la fiche, `7b737f4`.
Sources non modifiées.

```sh
python3 docs/validation/2026-10-07/claude-g058/probes_g058.py <copie>/eidolon-core/src
```

Les sondes sont **indépendantes** : ce n'est pas un rejeu des tests de
Codex.

- Requêtes synthétiques (`example.invalid`, adresses de documentation).
- Fournisseur, lecteur et DNS simulés ; le fournisseur compte ses contacts.
- Pannes par `os._exit` dans des sous-processus.
- Altérations sur des copies.

Sortie : [probes.txt](probes.txt).

## Résultats

| Thème | Cas | Résultat |
| --- | --- | --- |
| Migration | lecture d'historique (API et CLI) sur un journal de schéma 1 | refus `QUERY_HISTORY_NOT_ENABLED`, **schéma inchangé** |
| | ouverture `create=False` avec `retain_queries` | refus, schéma inchangé |
| | migration explicite | schéma 2 ; anciennes fiches **identiques octet pour octet** ; anciennes recherches comptées `legacy`, aucun texte inventé |
| | objet ancien resté en schéma 1 après migration | refus `UNSUPPORTED_RESEARCH_GUARD` |
| Pannes | arrêt **avant** le commit de l'intention | rien n'est écrit, 0 contact, recherche suivante possible |
| | arrêt **pendant** l'appel | intention et texte présents, émission `UNKNOWN`, nouvelle recherche refusée `WEB_RESEARCH_UNCERTAIN` |
| Altérations isolées | ligne orpheline ajoutée, ligne supprimée seule | `QUERY_HISTORY_BINDING_MISMATCH` (lecture **et** recherche), 0 contact |
| | texte modifié seul, U+200B ajouté | `INVALID_QUERY_HISTORY_RECORD`, 0 contact |
| | ligne de 50 000 octets, clé JSON dupliquée | `INVALID_RESEARCH_RECORD`, 0 contact |
| Pagination | 7 entrées par pages de 3 | 3 + 3 + 1, sans doublon, ordre chronologique |
| | curseur : décalage > total, négatif, autre journal, révision fausse, espace final, 151 caractères | refusés ; un décalage égal au total donne une page vide, sans curseur |
| | nouvelle recherche entre deux pages | `QUERY_HISTORY_RESET_REQUIRED` |
| | limite 0, 51, `True`, `3.0` | refusées |
| SQLite occupé | verrou d'écriture tenu 4 s | lecture **et** recherche refusées en 2,0 s (`RESEARCH_GUARD_UNAVAILABLE`), 0 contact ; tout redevient normal ensuite |
| Données | données personnelles brutes dans la base | **aucune** (courriel, téléphone, adresse IP retirés avant stockage) |
| | empreinte de la requête brute (SHA-256 ou `digest`) dans la lecture | **aucune** |
| | modes | dossier 0700, base et verrou 0600 ; base en 0644 → refus |
| Bornes | requête de 999 caractères | gardée entière |
| | 200 anciennes + 56 nouvelles | la 257ᵉ est refusée : les anciennes, sans texte, **comptent** dans le plafond |

## Hors garantie : réécritures cohérentes (rapportées, pas des défauts)

| Réécriture | Résultat |
| --- | --- |
| Nouveau texte, avec les empreintes recalculées dans la ligne, la fiche **et** l'audit | lu comme authentique |
| Texte supprimé **et** lien retiré du descripteur partout | la recherche devient une « ancienne » sans texte (`legacy` +1) |

## G058-1 (P3) — une recherche récente peut passer pour une ancienne

La seconde réécriture ci-dessus est la même faiblesse que G048-1 et G052-1.
Rien ne date la migration : une recherche **postérieure** à la migration,
privée de son texte et de son lien, ressemble à une recherche d'avant
l'historique.

Proposition (Codex décide), sur le modèle de `receipt_hash_required_from` :

- noter dans `metadata`, à la migration, l'identité de la dernière fiche
  ancienne ;
- refuser ensuite toute fiche plus récente sans `query_history_sha256`.

Pas de diff joint : `research_guard.py` est réservé, et sa table `metadata`
n'accepte aujourd'hui qu'une ligne.

## Observation pour C-D17 (archivage automatique)

Les anciennes recherches sans texte comptent dans le plafond de 256. La
rotation devra pouvoir les archiver aussi. Le prototype G057 les accepte
déjà, puisqu'il sélectionne par état et non par présence de texte.

## Limites

- Linux, Python 3.11, système de fichiers local.
- La migration n'est pas interrompue **pendant** sa transaction, faute de
  point d'injection sans modifier la source.
- Les pannes sont placées à deux frontières choisies.
- Réécritures cohérentes rapportées, conformément au contrat de C-019.
