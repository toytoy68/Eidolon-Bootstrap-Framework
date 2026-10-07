# Historique local des requêtes nettoyées — C-019

07/10/2026, Codex/GPT. Implémente C-D15 rapportée par Claude : garder localement
le texte nettoyé pour relecture. Le coordinateur reste candidat ; aucun
fournisseur réel, runtime de mission, abonnement ni accès externe activé.

## Activation explicite et données

```python
guard = ResearchGuard('/chemin/prive/recherche', retain_queries=True)
coordinator = ResearchCoordinator(providers, reader, resolver=resolver,
                                  pauses=pauses, guard=guard)
```

La garde conserve le texte **après nettoyage**, le reçu `query-cleanup/2`,
l’identité de tentative et les états de la recherche. Le même objet nettoyé
est utilisé pour l’historique et tous les fournisseurs. Le texte brut et son
empreinte ne sont pas stockés. Une requête nettoyée peut encore contenir des
données privées non reconnues : ce stockage est local, privé et non chiffré.

La table dédiée `cleaned_queries` partage le fichier SQLite de la garde.
L’intention, son événement et le texte sont écrits dans **une transaction**,
avant le premier appel ; aucun fichier séparé ne nécessite une synchronisation
approximative. L’empreinte du texte/du reçu est liée au descripteur d’intention.
Les lignes de garde et leur projection `inspect` ne contiennent pas le texte.
L’API HTTP actuelle ne propose aucune route pour lire cet historique.

Les bases/verrous créés restent en 0600 et le dossier neuf en 0700. Le système
de fichiers local et les restrictions POSIX du contrat de garde restent requis.

## Migration et limites

Le schéma garde 1 devient 2 uniquement à l’ouverture explicite avec
`retain_queries=True, create=True` (valeur `create` par défaut). Migration
transactionnelle ; aucun texte historique n’est inventé. Le compteur
`legacy_runs_without_text` signale ces anciennes tentatives.

Une fois le schéma 2 actif, les nouvelles recherches doivent fournir leur
texte nettoyé même si un nouvel objet est ouvert sans le drapeau. Un objet
resté sur le schéma 1 est refusé après la migration : le rouvrir. Un ancien
binaire n’acceptant que le schéma 1 refusera le journal 2 ; pas de rétrogradation.
Les commandes de lecture n’activent ni ne migrent un journal.

Bornes actuelles fixées par le code, hors modèle : **256 recherches au total**
(anciennes comprises), **1 000 caractères** par texte nettoyé, **50 entrées**
maximum par page. Aucune éviction ni durée de rétention choisie implicitement.
À capacité atteinte : refus avant appel. La rotation explicite est confiée à
Claude G057 ; tant qu’elle n’est pas livrée, ce plafond limite l’usage continu.
Ne pas supprimer le journal pour contourner le plafond.

## États : ce qui est réellement établi

| État | Sens de l’émission affichée |
| --- | --- |
| Texte vide | `NOT_REQUESTED` : le coordinateur n’appelle pas un fournisseur pour cette requête |
| `INTENT` avec texte | `UNKNOWN` : l’intention existe ; un appel peut être actif, interrompu ou ne pas avoir commencé |
| `COMPLETED` avec texte | `CALL_SEQUENCE_COMPLETED` : rapport et fin durables ; cela peut inclure zéro appel (pause, annulation) ou un échec |
| `RESOLVED_UNKNOWN` avec texte | `UNKNOWN` : l’incertitude a été revue, aucune preuve d’émission créée |

`delivery_confirmed=false` dans tous les cas : aucun accusé de réception du
fournisseur n’est inventé. Ce premier lot suit la recherche entière, **pas chaque
appel/repli/saut HTTP**. Les fournisseurs listés sont les candidats configurés,
pas une liste de destinataires qui auraient nécessairement été contactés.

Une panne avant le commit ne laisse ni intention ni texte et n’autorise pas
l’appel. Après le commit, toute panne ou échec de fermeture laisse l’intention
et son texte ; les nouvelles recherches sont bloquées jusqu’à revue explicite.
La revue conserve le texte, ne relance rien et ne libère aucune pause réseau.

## Lecture locale

```sh
python -m eidolon_core.query_history --directory /chemin/prive/recherche --limit 20
python -m eidolon_core.query_history --directory /chemin/prive/recherche --format human
python -m eidolon_core.query_history --directory /chemin/prive/recherche --cursor 'CURSEUR_RETOURNE'
```

JSON par défaut ; affichage humain ECT optionnel. Le curseur ne contient pas de
texte et est lié à l’identité du journal et à sa révision complète. Ajout ou
revue entre deux pages : `QUERY_HISTORY_RESET_REQUIRED`, recommencer sans
curseur. Lecture dans une transaction cohérente ; aucun lancement, aucune
création de base absente. La construction d’une garde pendant un appel actif
reste refusée par le verrou : une CLI peut signaler `WEB_RESEARCH_IN_FLIGHT`.

Une corruption isolée (texte, reçu, ligne supprimée/orpheline) refuse lecture et
nouvelle recherche. La suppression/restauration de toute la base ou sa réécriture
cohérente ne sont pas détectables sans référence externe ; aucun mécanisme
cryptographique d’authenticité n’est prétendu. Pas de Windows/NFS ni de coupure
électrique réelle validés.

## Liaison mission synthétique — C-021

Un descripteur peut maintenant porter `operation_id=m-ID`, une identité de
mission générée par Core. Elle est auditée avec l’intention et relue lors de la
vérification du résultat. Elle ne contient pas la requête. Le texte de demande
brut peut exister dans le magasin local des missions, distinct de cet historique
nettoyé ; voir [RESEARCH-MISSIONS.md](RESEARCH-MISSIONS.md).
