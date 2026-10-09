# Étude G077 — Contexte d'activité et reprise suggérée

Auteur : Claude. Date : 08/10/2026, Europe/Paris. Statut : **ÉTUDE — choix et seuils à arbitrer par toytoy**.
Fiche : C-TASK-G077. Complète [les propositions Codex P10–P11](2026-10-08-dashboard-context.md).

Aucun collecteur, aucune capture du PC, aucune extension, aucune webcam. Les
scénarios ci-dessous sont des **raisonnements** sur données synthétiques : aucun
code n'a été exécuté pour cette étude.

## Le besoin, reformulé

Quand toytoy revient à son poste, Eidolon pourrait dire : « tu travaillais sur
*X* ; dernier fait conservé : *Y* ; je propose de regarder *Z* ».

Le risque : qu'un contexte **ancien, bruité ou d'un autre poste** fasse croire à
une reprise, ou pire, en déclenche une. Toute la conception sert à empêcher cela.

## Trois niveaux de collecte comparés

| Niveau | Ce qui est connu | Utilité | Coût / confidentialité |
| --- | --- | --- | --- |
| **M — Déclaration manuelle** | « je travaille sur le projet P » (et sa mission liée), saisi ou cliqué par toytoy | Exacte, utile dès le premier jour, testable sans rien installer | Une action à faire, et une déclaration oubliée devient périmée |
| **L — Métadonnées locales** | application au premier plan, début/fin, **domaine** d'onglet (sans chemin ni paramètre), projet **suggéré** | Regroupe automatiquement ; détecte l'interruption | Le nom d'application ou de domaine révèle déjà des choses ; classification imparfaite ; un module par navigateur |
| **E — Contenu enrichi ciblé** | texte d'un document ou d'une page **désignés** pour une tâche | Comprend vraiment le travail | Très sensible, volumineux ; demande des droits et une revue au cas par cas |

Je propose **M d'abord**, puis L en option explicite. **E seulement par
désignation**, document par document, jamais en flux. Je rejoins Codex. J'ajoute
une règle : **L ne peut que suggérer un projet** ; il ne remplace jamais une
déclaration M plus récente.

## Événement minimal proposé

```json
{
  "schema": "eidolon-activity-event/1",
  "id": "a-<uuid>",
  "kind": "DECLARED | OBSERVED | INFERRED",
  "origin": {"device": "pc-<id>", "session": "s-<id locale>", "collector": "manual | foreground/1"},
  "observed_at": "2026-10-08T09:12:00+02:00",
  "received_at": "rempli par Core",
  "valid_until": "2026-10-08T21:12:00+02:00",
  "subject": {"project": "p-<id> ou null", "mission": "m-<id> ou null",
              "application": "nom court ou null", "domain": "exemple.org ou null"},
  "confidence": "USER | HIGH | LOW",
  "private_mode": false
}
```

Règles :

- **Trois natures distinctes** :
  - `DECLARED` vient de toytoy : c'est une **instruction**, la seule qui fixe
    le projet actif ;
  - `OBSERVED` vient d'un collecteur : c'est une **observation**, pas une
    intention ;
  - `INFERRED` vient de Core : c'est une **inférence** et elle cite les
    observations utilisées.
- `observed_at` est l'horloge du poste, `received_at` celle de Core. Un écart de
  plus de quelques minutes marque l'événement `LOW` ; les deux heures ne sont
  jamais confondues.
- Expiration par défaut, à arbitrer : 12 h pour `DECLARED`, 30 min pour
  `OBSERVED`. Un événement expiré **ne produit plus de suggestion**, il reste
  seulement consultable.
- Pas de titre complet, d'URL avec chemin ou paramètres, de contenu ni de
  capture d'écran dans le premier lot.
- Doublons : même `id` → ignoré ; même contenu à moins de 5 s → fusionné.

## Ce qu'une suggestion a le droit de faire

Une **carte de reprise** affiche séparément :

- le dernier fait conservé, avec sa date ;
- la mission liée et son **état actuel relu** ;
- la raison (« déclaré à 9 h 12 », ou « observé, confiance faible ») ;
- l'action proposée.

Elle ne peut **jamais** :

- lancer, reprendre ou relancer une mission ;
- accorder une permission ou consommer un accord ;
- réactiver une collecte désactivée ;
- proposer « Réessayer » sur un **effet inconnu** : seulement « Voir les
  preuves » (règle de G070) ;
- s'afficher sur un autre poste que celui de l'observation, sauf si toytoy a
  déclaré le projet sur ce poste.

Avant d'afficher la carte, Core **relit l'état de la mission**. Terminée
ailleurs, la carte devient « déjà terminée » puis disparaît. Effet inconnu : la
carte ne propose que la preuve.

## Cas difficiles

| Cas | Comportement proposé |
| --- | --- |
| Bruit (alt-tab rapides) | seuil de présence, par exemple 2 min au premier plan, avant qu'une observation compte |
| Poste partagé | collecte suspendue tant qu'une session n'est pas celle de toytoy ; pas de session = pas d'événement |
| Onglet ancien resté ouvert | le *domaine* seul ne prouve rien : il faut un passage au premier plan récent, sinon il est ignoré |
| Veille, redémarrage | un événement `SLEEP` / `BOOT` ferme les observations ouvertes ; au réveil, la carte demande confirmation (« Tu reprends P ? ») au lieu de l'affirmer |
| Tâche terminée ailleurs | relecture de l'état avant affichage (voir plus haut) |
| Mode privé | aucun événement ; le collecteur ne note même pas qu'un mode privé était ouvert |
| Désactivation | bascule visible, effet immédiat. Les événements en transit après la désactivation sont **rejetés** à la réception et ne la réactivent jamais |
| Effacement | « tout effacer » supprime le journal local et les événements reçus, puis le confirme |

## Rôles de Core et de Memory Engine

- **Core** reçoit les événements, en garde un **journal court**, calcule les
  suggestions et affiche les cartes. C'est la seule autorité sur les missions et
  les permissions.
- **Memory Engine** reste la source canonique de la mémoire durable. Il ne reçoit
  **aucun flux brut**, seulement un résumé que toytoy a **choisi de retenir**
  (« retenir que j'ai fini la recette V100 le 08/10 »), via un contrat
  d'ingestion à définir avec le moteur. Aucune écriture dans ses sources ici.
- Le connecteur Windows n'écrit jamais directement dans Memory Engine.

## Rétention proposée (à arbitrer)

| Variante | Contenu | Pour | Contre |
| --- | --- | --- | --- |
| **R1 — session seulement** | rien sur disque ; tout est perdu au redémarrage | la plus discrète | inutile après un redémarrage, alors que c'est le cas principal |
| **R2 — journal roulant 24 h** (ma préférence pour l'essai) | événements M et L sur disque, privés, effaçables, purgés après 24 h | couvre la nuit et le redémarrage | 24 h de métadonnées à protéger |
| **R3 — résumés retenus** | en plus de R2, des résumés choisis vont dans Memory Engine | continuité sur plusieurs jours | chaque résumé est une décision de mémoire |

## Cinq scénarios discriminants (données synthétiques)

| # | Situation simulée | Attendu | Ce qui distingue les niveaux |
| --- | --- | --- | --- |
| S1 | Déclaration M « projet recette V100 » à 9 h 12, veille à 12 h, réveil à 14 h | carte « Tu reprends la recette V100 ? » avec le dernier résultat relu ; **rien lancé** | M suffit ; L n'apporte rien |
| S2 | Aucune déclaration ; 40 min d'éditeur sur `eidolon-core`, puis 3 min de navigateur sur un domaine de documentation | suggestion `INFERRED` faible « projet Eidolon Core ? », à confirmer | seul L produit quelque chose ; teste le seuil et la confiance |
| S3 | Déclaration M sur le PC A ; toytoy ouvre le client sur le portable B | **aucune** carte sur B, sauf déclaration sur B | teste le lien au poste et à la session |
| S4 | Carte prête pour la mission « diagnostic vm100 » ; entre-temps la mission passe `REVIEW_REQUIRED` (effet inconnu) | la carte ne propose que « Voir les preuves » ; aucun « Réessayer » | teste la relecture d'état et la règle G070 |
| S5 | Collecte L désactivée à 10 h 00 ; 3 événements horodatés 9 h 59 arrivent à 10 h 02 | rejetés, collecte toujours désactivée, et l'effacement les inclut | teste la désactivation et la course réseau |

Réussite : aucun état inventé, aucune reprise ni collecte déclenchée par le seul
contexte, et la bonne carte en moins de 3 actions. Mesurer l'utilité sur une
semaine avec M seul **avant** de construire L.

## Coût, confidentialité, utilité

| | M | L | E |
| --- | --- | --- | --- |
| Développement | faible (une saisie, un événement) | moyen (collecteur Windows, module navigateur, filtrage) | élevé (droits, volumes, revue) |
| Données sensibles | projet choisi | applications et domaines | contenus |
| Utilité attendue | bonne si la déclaration est faite | meilleure sans effort, mais bruitée | forte sur une tâche précise |
| Risque principal | déclaration périmée | fausse inférence | fuite de contenu |

## Questions pour toytoy

1. Faut-il commencer par M seul pendant une semaine (ma recommandation), ou
   directement M + L ?
2. Quelle rétention : R1, R2 ou R3 ?
3. Quelles expirations par défaut (12 h et 30 min proposés) ?
4. Faut-il exclure dès le départ certaines applications ou domaines (banque,
   santé, messagerie) ?
