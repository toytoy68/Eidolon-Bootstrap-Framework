# C-002c — Suspensions Web persistantes

Codex/GPT, 06/10/2026. `ResearchPauses`, protocole eidolon-research-pauses/1,
Python standard/SQLite. Ce lot complète le transport C-002b ; G030 l'avait
nommé C-002b par erreur. L'archive G030 conserve cette ancienne désignation.

## Fonctionnement livré

Le coordinateur peut recevoir `pauses=ResearchPauses(path)`. Il vérifie les pauses
avant un fournisseur, avant une lecture HTTP non cachée et, avec WebReader,
avant chaque saut de redirection. Chaque fournisseur reste un adaptateur de code
de confiance ; la table de pauses ne remplace pas la politique réseau.

Les refus ACCESS_DENIED, limitations RATE_LIMITED, challenges/login détectés,
Retry-After valides ou ambigus deviennent des suspensions enregistrées. Les clés
sont soit provider_id, soit le couple canonique (hôte, port). Le schéma HTTP/HTTPS
est volontairement absent de la clé : changer le schéma sur le même port ne lève
pas la pause. Un quota après redirection suspend origine initiale et finale dans
une transaction ; les origines intermédiaires ne sont pas toutes suspendues.

**Une pause commise ne disparaît pas automatiquement**, même si le délai est
écoulé, si le coordinateur est reconstruit ou si la politique/reader change.
Une reprise exige une revue explicite avec identifiant, révision attendue,
acteur et raison. Le plus long délai connu est conservé entre observations.
Une nouvelle observation invalide la révision utilisée pour lever la pause.
Une levée n'effectue aucune recherche ni lecture ; la politique normale devra
encore autoriser une nouvelle demande explicite.

| Donnée | Sens |
| --- | --- |
| id | empreinte du périmètre, non secrète, pas une identité authentifiée |
| scope | fournisseur nommé ou hôte/port ; pas de chemin URL ni requête de recherche |
| revision | incrémentée à chaque observation et levée |
| status | ACTIVE / RELEASED, historique conservé |
| reason | dernier type de refus observé, pas un verdict sur la véracité d'une source |
| observed_at_ms | horloge murale locale en millisecondes |
| not_before_ms | minimum avant levée explicite ; null si aucune borne chiffrée connue |
| review_required | ambiguïté signalée par le transport ; toutes les pauses exigent néanmoins une levée explicite |
| released_at_ms | date de levée lorsqu'elle a été enregistrée |

Pour un 429 sans délai exploitable, une borne prudente de 60 secondes est utilisée ;
elle ne prétend pas connaître le délai réel du fournisseur. Une valeur ambiguë
reste marquée pour revue. Le délai borné par le transport vaut au plus 86400 s ;
une valeur extérieure reste une ambiguïté à examiner, pas une autorisation après
60 secondes. Le temps écoulé seul ne libère rien.

## Persistance et erreurs

Base distincte `research-pauses.sqlite3` : table pauses (au plus 256 périmètres
**ACTIVE**) et journal pause_events. Une transaction SQLite réunit changement
de pause et audit. Les pauses initiale/finale d'une redirection sont atomiques.
Aucune éviction pour faire de la place : capacité atteinte = erreur bloquante.
Avant un appel fournisseur, une lecture non cachée et chaque saut de WebReader,
`check_capacity(scopes)` vérifie dans une transaction de lecture la place pour
les périmètres à suspendre en cas de refus. Sur redirection, origines initiale
et courante sont comptées ensemble, sans doublon.

Depuis le suivi G024, une ligne **RELEASED libère une place active**, tout en
conservant son identité, sa révision et son audit. Réobserver ce périmètre
consomme une place et incrémente la révision existante ; une ancienne revue
ne devient jamais valable par réutilisation d'un identifiant. Une observation
ACTIVE existante peut évoluer à capacité pleine. Lever une pause exige toujours
la revue explicite et le délai minimal ; aucune levée automatique pour gagner
de la place. Le nombre total de lignes historiques peut dépasser 256.
Le décompte valide les lignes en flux, sans les charger toutes en mémoire ;
son coût est linéaire dans l'historique. Indexation, plafond disque et rétention
restent des limites d'exploitation à traiter avant utilisation réelle.

Ce contrôle ne réserve pas de place : un écrivain concurrent, un crash ou une
panne de disque après l'appel restent soumis aux limites ci-dessous. Un lecteur
injecté sans read_guarded ne fournit pas le contrôle des sauts intermédiaires.

Après les consultations persistantes, le budget et l'annulation sont revérifiés
avant l'appel. Ce délai reste coopératif : il n'interrompt pas SQLite ou un
adaptateur déjà en cours ; un résultat déjà reçu reste observable.
Le journal n'est pas purgé automatiquement ; quotas/rétention restent à construire.

Un échec de stockage lève PauseStorageError, sans corps SQL brut. Il interrompt la
recherche au lieu de produire une liste vide ou de basculer sur un autre fournisseur.
Le coordinateur concerné conserve aussi un blocage en RAM après cet échec.
Exception précise : `PauseCapacityError` lors du **précontrôle en lecture seule**
garde le diagnostic PAUSE_CAPACITY_REACHED sans blocage permanent de l'instance.
Après revue et levée explicites, une nouvelle demande peut refaire les contrôles.
Une capacité refusée pendant l'écriture d'une observation après échange garde le
blocage prudent : le reçu peut avoir été perdu. Examiner
l'état persistant avant de le reconstruire ; ne pas le traiter comme une erreur
réseau permettant une nouvelle tentative automatique.

Une pause normalement commise survit à un arrêt du processus. **L'échange HTTP et
l'écriture SQLite ne sont pas atomiques** : crash entre réponse et enregistrement,
ou enregistrement impossible, peuvent laisser une observation non persistée.
Ce lot ne fournit pas de journal durable préalable des appels en vol. L'exploitation
réelle devra traiter ces interruptions comme incertaines avant de relancer, plutôt
que reconstruire aveuglément le coordinateur. Pas de garantie « exactement une fois ».

Deux appels déjà engagés avant l'enregistrement d'une pause peuvent se croiser ;
la consultation n'est pas une réservation atomique de quota ni une annulation
d'un appel en cours. Les adaptateurs et exécutants de confiance devront encore
être isolés et encadrés avant usage avec des outils réels.

## API et CLI

```python
from eidolon_core.research_pauses import ResearchPauses
from eidolon_core.research import ResearchCoordinator

pauses = ResearchPauses('/chemin/etat/research-pauses.sqlite3')
# Fournisseurs, reader et resolver sont configurés explicitement par l'appelant.
coordinator = ResearchCoordinator(providers, reader, resolver=resolver, pauses=pauses)
```

Sans argument pauses, le coordinateur conserve son fonctionnement candidat en
RAM. **La persistance est optionnelle**, non activée implicitement dans tous les
exemples existants. Les commandes suivantes exigent une base de pauses existante
et ne construisent ni Runtime ni base de missions :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat research-pauses
PYTHONPATH=src python -m eidolon_core --state /chemin/etat research-release p-EMPREINTE --revision 3 --actor operateur --reason 'Observation examinée ; nouvelle tentative explicite autorisée'
PYTHONPATH=src:. python -m examples.research_pauses_demo --format human
```

La clé/révision provient de research-pauses ; ne pas recopier le placeholder.
JSON par défaut, présentation ECT avec `--format human`. Code 0 = consultation
ou levée enregistrée, jamais texte lu ou mission réussie ; code 2 = refus/erreur.
STALE_PAUSE impose une nouvelle inspection ; RETRY_DELAY_PENDING empêche de lever
avant le minimum connu. Une levée déjà enregistrée reste observable dans la table.

## Limites et prochaine tranche

- Actor est un libellé local non authentifié. Pas de bouton modèle de levée,
  authentification distante, outil mission ou extension d'autorisation réelle.
- L'horloge UTC locale sert au minimum de levée ; recul avant observed_at refusé.
  Un saut en avant peut rendre ce minimum prématurément échu, mais ne lève aucune
  pause automatiquement. Une horloge fiable reste une exigence d'exploitation.
- Un cache RAM valide peut être relu sans nouvelle requête HTTP ; sa date/provenance
  restent conservées. Le résolveur peut encore être appelé avant un blocage d'origine.
  « Aucun nouvel appel HTTP » ne signifie pas « aucune résolution DNS ».
- Hôtes et identifiants fournisseurs distincts ne constituent pas un quota global
  par opérateur. Aucune rotation d'identité, proxy ni contournement de challenge.
- Pas de garantie contre SQL brut, fichier supprimé/remplacé, clone ou restauration
  ancienne. La copie de revue C-008d ne sauvegarde que missions.sqlite3, pas cette base.
- Les détections HTML challenge/login restent celles, partielles, du coordinateur.
  Aucun nouveau parseur universel, fournisseur réel ou intégration Memory Engine.
- Avant utilisation réelle : journal des appels en vol/reconciliation, stratégie
  de sauvegarde cohérente, quotas/rétention et permissions d'exploitation.

[Tests et démo](validation/2026-10-06/codex-research-pauses/README.md).

## Refus et problèmes de lecture — audit du 06/10/2026

Les statuts HTTP 401/403/429 validés gardent leur signification même si le corps
est trop grand ou incomplet ; aucun texte de ce corps n'est retenu comme source.
Après réception, un refus ou Retry-After est mis en pause même si la nouvelle
vérification DNS de l'URL finale échoue. L'origine initiale et l'origine finale
syntaxiquement validée sont suspendues ; cela ne permet aucune connexion à une
destination refusée. Le rapport conserve le statut HTTP reçu et le refus de
politique courant. Un crash avant cette écriture conserve la limite déjà décrite.

Le transport standard ne lit déjà pas les corps non-2xx. La correction des corps
concerne le contrat Page des lecteurs injectés, testé avec un lecteur simulé ;
la correction DNS est éprouvée via WebReader avec transport/résolveur simulés.
