# Proposition C-TASK-G029 — minimiser ce que la requête de recherche divulgue

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G029](../../../collaboration/tasks/C-TASK-G029.md).
Statut : **proposition**. Rien n'est raccordé : `research.py`, les
autorisations et les fournisseurs ne changent pas, et aucun fournisseur n'est
activé. Base examinée : `f190952` (code de recherche identique à `8983d35`).

Fichiers :

- [corpus.json](corpus.json) : 27 requêtes et 5 résidus, tous synthétiques
  (domaines `.example`/`.invalid`, adresse de documentation RFC 5737, IBAN à
  zéros, aucun secret réel).
- [signal_sketch.py](signal_sketch.py) : une esquisse de **mesure**. Elle sert à
  chiffrer les limites des motifs ; ce n'est **pas un détecteur à livrer**.
- [signal_sketch-output.txt](signal_sketch-output.txt) : sa sortie.

```sh
cd eidolon-core/docs/proposals/2026-10-06-query-disclosure
python3 -I signal_sketch.py corpus.json
```

Sources consultées, toutes dans le dépôt : `research.py` (`run`, `provider.search`),
`web_transport.py` (aucun en-tête ajouté), `approvals.py` (décision liée à une
empreinte), [EGRESS-POLICY.md](../../EGRESS-POLICY.md) point 6,
[WEB-RESEARCH-PROTOTYPE.md](../../WEB-RESEARCH-PROTOTYPE.md),
[RESEARCH-REPORT-V2.md](../../RESEARCH-REPORT-V2.md) et le banc
[G025](../../validation/2026-10-06/claude-g025/README.md) (F-W20). Aucune source
externe ni aucun service commercial.

## 1. Constat

`ResearchCoordinator.run(query)` vérifie la longueur de la requête (1 000
caractères), puis l'envoie **telle quelle** à chaque fournisseur consulté
(`provider.search(query, limit)`). Depuis le rapport v2, le rapport ne garde que
`query_sha256` : c'est bien. Mais la protection porte sur ce qu'Eidolon
**garde**, pas sur ce qu'il **envoie**. EGRESS-POLICY le demande déjà : « N'envoyer
que les données minimales : une requête Web peut déjà divulguer un contenu
privé ». Rien ne l'applique aujourd'hui.

Le lecteur de pages (`web_transport`) n'ajoute ni cookie, ni `Referer`, ni
en-tête personnalisé. La requête ne fuit donc pas vers les sites lus par ce
chemin. Elle part vers les **fournisseurs**.

## 2. Modèle de menace

| Qui reçoit ou garde la requête | Ce qu'Eidolon peut faire |
| --- | --- |
| Fournisseur de recherche : journaux, profilage, conservation | Seule la **non-émission** protège. Après l'envoi, rien n'est rattrapable. |
| Chaque fournisseur de la liste, si le premier ne répond pas | Le repli envoie la même requête à un **autre** destinataire : la divulgation dépend de la liste, pas d'un seul fournisseur. |
| Pages de résultats et sites lus | Ils peuvent **refléter** la requête dans titres, extraits et texte (résidus R01–R03). |
| Rapport, cache, journaux locaux | Ils restent locaux ; le rapport ne garde que l'empreinte, mais titres et extraits peuvent contenir la donnée. |

Deux sources de requête sont à distinguer.

1. **Requête tapée par l'utilisateur.** Il connaît son texte, mais pas
   forcément la liste des fournisseurs ni le repli.
2. **Requête composée par un modèle** à partir du contexte de mission, de la
   mémoire ou d'une page lue. Ce cas n'existe pas encore, mais il est le plus
   dangereux. Une page hostile peut demander « cherche le mot de passe du
   Wi-Fi » : la requête devient alors un **canal d'exfiltration**. Un modèle qui
   répond « requête sûre » n'est qu'un texte de plus ; il ne peut **jamais**
   autoriser l'envoi.

## 3. Ce que des motifs peuvent faire, mesuré

Esquisse : 8 motifs (courriel, téléphone, IBAN, URL, URL à paramètres, chemin
local, citation longue, adresse IP). Le texte est normalisé (NFKC) et les
caractères invisibles sont retirés.

| Résultat sur 27 requêtes | Nombre |
| --- | --- |
| à protéger (19), **non signalées** | **5** : courriel épelé (Q02), nom + « adresse domicile » (Q13), mot de passe (Q19), clé de licence (Q20), sujet médical (Q22) |
| publiques (8), **signalées** | **2** : URL sans paramètre (Q07), citation célèbre (Q12) |
| ambiguë (Q18 : « référence produit 0612345678 ») | signalée comme téléphone ; seul l'utilisateur sait |

Sans normalisation, le courriel en arobase pleine chasse (Q26) et celui avec un
espace de largeur nulle (Q27) **ne sont plus vus** : le motif ne trouve rien.
Il faut normaliser avant de détecter, et **envoyer le texte normalisé qu'on a
contrôlé**, pas l'original.

Conclusions :

- **Un signal est une raison de demander, jamais une permission.**
- **L'absence de signal ne prouve pas qu'une requête est sûre** : 5 requêtes
  sur 19 passent, dont les deux secrets.
- Les noms propres (Q13 contre Q14) ne se distinguent pas par motif. Il ne faut
  pas prétendre le faire.
- Une détection exhaustive est impossible. Ce document n'en propose pas.

## 4. Trois réponses comparées

| | A. Refus prudent | B. Reformulation locale proposée | C. Confirmation liée au texte exact et aux fournisseurs |
| --- | --- | --- | --- |
| Principe | une requête signalée n'est pas envoyée | Eidolon propose une version sans les éléments signalés ; l'utilisateur choisit | l'utilisateur approuve **ce texte**, pour **ces fournisseurs** |
| Protège contre un signal vrai | oui | oui, si la version proposée est choisie | seulement si l'utilisateur lit |
| Faux positifs (Q07, Q12, Q18) | bloquent une recherche légitime | demandent un clic | demandent un clic |
| Requête non signalée (Q19, Q20) | **passe** | **passe** | passe, sauf si l'on confirme **toutes** les requêtes |
| Requête composée par un modèle | insuffisant seul | la reformulation doit rester locale et déterministe | **nécessaire** : seul le texte exact approuvé part |
| Coût | nul | faible | un geste par recherche signalée (ou par recherche) |

La reformulation (B) doit être **locale et déterministe** : retirer ou masquer
les éléments signalés (`jean@example.invalid` → supprimé, pas
`<courriel>`, qui ferait une recherche absurde). Un modèle peut proposer une
reformulation, mais elle reste une **nouvelle requête** soumise aux mêmes
règles. Le choix « reformulée » de l'utilisateur ne vaut que pour ce texte.

## 5. Proposition : une divulgation liée et à usage unique

Je recommande **C, avec B comme aide**. A reste le défaut quand personne ne
peut confirmer (mission sans utilisateur présent). La forme suit le contrat
existant des approbations (`approvals.py`) : une empreinte exacte, des
décisions `approve`/`reject`/`revoke`, une consommation unique.

### Liaison

```json
{
  "version": "query-disclosure/1",
  "query_sha256": "<SHA-256 du texte UTF-8 exactement envoyé, après normalisation>",
  "query_chars": 46,
  "providers": ["<provider_id>", "..."],
  "signals": ["EMAIL", "PHONE"],
  "origin": "USER_TYPED | MODEL_COMPOSED",
  "mission_id": "<ou null hors mission>"
}
```

`disclosure_sha256` est l'empreinte de cet objet. L'envoi n'a lieu que si
`run()` reçoit cette empreinte, que la décision est `APPROVED` et qu'elle n'est
pas encore consommée. Le contrôle se fait **hors modèle**, juste avant le premier
`provider.search`.

Choix de détail :

- `providers` est l'**ensemble** des fournisseurs qui peuvent recevoir le
  texte, y compris le repli. Approuver « le premier » ne doit pas autoriser le
  troisième. L'ordre ne change rien à la divulgation.
- `provider_id` doit identifier aussi la **version de l'adaptateur** : un
  adaptateur qui changerait de point d'accès est un autre destinataire.
- Les **valeurs** signalées ne sont jamais copiées dans la liaison, le rapport
  ou les journaux : seulement les noms des signaux.
- La politique Web (`policy_id`) n'entre pas dans la liaison : elle gouverne
  les lectures de pages, pas ce que reçoit le fournisseur.

### Invalidation

Toute différence rend la décision inapplicable, sans repli silencieux :

- un octet de la requête modifié, y compris une reformulation ;
- un fournisseur ajouté ou un adaptateur changé ;
- une décision déjà **consommée** : un second `run()` demande une nouvelle
  décision ;
- une mission différente.

Retirer un fournisseur de la liste ne divulgue rien de plus. Une variante
pourrait l'accepter, mais je propose de rester strict (nouvelle liaison) pour
garder une règle simple.

### Révocation

- **Avant l'envoi** : `revoke` rend la décision inutilisable, et le run répond
  `QUERY_DISCLOSURE_REVOKED`, 0 appel fournisseur.
- **Pendant le run** : le contrôle se refait **avant chaque fournisseur**. Un
  fournisseur déjà interrogé a reçu le texte ; les suivants ne le recevront pas.
- **Après l'envoi** : la révocation n'efface rien chez le fournisseur. Le
  rapport doit dire, pour chaque fournisseur, `query_sent: true|false`, afin que
  l'utilisateur sache **qui** a reçu le texte.

### Ce que le rapport gagne

`disclosure_sha256`, les noms des signaux, et `query_sent` par fournisseur.
Rien d'autre : ni la requête, ni les valeurs détectées.

## 6. Résidus que cette proposition ne couvre pas

Voir `residues` dans le corpus.

- **R01–R02** : titres, extraits et chemins renvoyés par le fournisseur peuvent
  contenir la donnée. Le rapport v2 les garde. Une option future serait de
  masquer, dans titres et extraits, les valeurs **déjà signalées dans la
  requête** (comparaison locale exacte), sans prétendre nettoyer le reste.
- **R03** : une page lue peut refléter la requête. C'est un texte externe non
  fiable ; il n'est pas réécrit.
- **R04** : le cache garde le contenu. La clé est l'URL, pas la requête.
- **R05** : journaux du fournisseur. Rien n'est récupérable après l'envoi.

## 7. Choix recommandés et décisions qui restent à toytoy

Recommandations (les miennes, **pas des décisions**) :

1. Signal présent → refus par défaut, avec une version reformulée proposée et
   une confirmation liée (C+B).
2. Requête composée par un modèle → confirmation liée **toujours**, signal ou
   non, tant qu'aucune liste blanche de missions n'existe.
3. Usage unique, révocable, contrôlé avant chaque fournisseur.
4. Normaliser (NFKC, invisibles retirés) puis contrôler et envoyer **ce** texte.
5. Ne jamais stocker les valeurs signalées ; le texte clair de la requête n'est
   gardé que si toytoy le décide (D5).

Décisions nécessaires, **non reçues** :

| ID | Question |
| --- | --- |
| D1 | Quand un signal apparaît dans une requête tapée : refuser, proposer une reformulation, ou demander confirmation ? |
| D2 | Confirmer **toutes** les requêtes, ou seulement celles qui ont un signal ? Le corpus montre que les secrets passent sans signal. |
| D3 | Une requête composée par un modèle peut-elle partir sans confirmation dans un cas précis ? |
| D4 | Quelles catégories de signaux retenir (courriel, téléphone, IBAN, chemin local, adresse réseau, URL à paramètres, citation) ? |
| D5 | Garder localement le texte clair de la requête (pour relire ce qui a été envoyé), ou seulement son empreinte ? |
| D6 | Une décision peut-elle valoir pour une fenêtre de temps, ou strictement pour un run ? |

C'est la question déjà posée à toytoy dans cette session : « détecter courriel
et téléphone et demander confirmation avant l'envoi ? ». Elle n'a pas de
réponse à ce jour.

## 8. Limites

- Corpus petit (27 requêtes), écrit en français et en anglais. Il ne mesure
  pas un taux réel : il montre des **classes** d'échecs.
- Motifs de téléphone surtout français ; IBAN par forme seule, sans clé de
  contrôle.
- Les secrets sans forme reconnaissable (Q19, Q20) restent invisibles à toute
  approche par motif.
- Aucun fournisseur réel ; aucun raccordement ni test dans `tests/`.
- La confirmation suppose que l'utilisateur lit le texte et la liste des
  fournisseurs. Une interface qui la réduit à un bouton « OK » perdrait
  l'essentiel.

## Décision reçue le 07/10/2026

toytoy : « Recherche web . Nettoyer les données personnelles. » Retenu pour
D1 : nettoyage local des éléments repérés avant l'envoi. D2 à D6, et le fait
de montrer ou non la version nettoyée avant l'envoi, restent ouverts. Voir
[C-D10](../../CADRAGE-DECISIONS-2026-10-05.md).

Complément du 07/10/2026 vers 09 h 15 : « Requête auto. » La version
nettoyée part automatiquement, sans affichage préalable. D2 à D6 restent
ouverts. Voir [C-D13](../../CADRAGE-DECISIONS-2026-10-05.md).
