# Contre-revue C-TASK-G011 — correctifs D1, D2 et C5

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G011](../../../../collaboration/tasks/C-TASK-G011.md).
Cible figée : `e25cd2a8856c9a80513100ed1b30bcd013e6c931`, extraite par `git archive` dans
une copie isolée. Empreintes vérifiées, identiques à
[source-hashes.json](../codex-g008-fixes/source-hashes.json) :

| Fichier | SHA-256 |
| --- | --- |
| `web_transport.py` | `56d590801d45650725b9a9b1e8e3ffcd7683e9b9ac1aa42473b4b72f900641dd` |
| `web_reader.py` | `6f43e1b24009a6f7e78438b09fc3bb26a494af347a675bcf7efb657ad2b739e3` |
| `research.py` | `4eecc52920a62092bae5266fe0e9ed392ff0b7d026f54a050e3ce9fb1041bece` |
| `tests/test_web_review_regressions.py` | `70020f45b0f473a8974dcd69a9232f8f579236c90ce0221012f943f080c3c6ad` |

Les trois modules sont inchangés jusqu'à `37604a1` (C-008a). Ni `src/`, ni
`tests/`, ni les preuves existantes ne sont modifiés ; les sondes G008 d'origine
sont intactes.

```sh
cd eidolon-core
# FROZEN = copie de e25cd2a (git archive e25cd2a eidolon-core/src | tar -x -C FROZEN)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src python docs/validation/2026-10-05/claude-g011/probes_g011.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src python docs/validation/2026-10-05/claude-g011/probes_g008_adapted.py
```

Python 3.11.15, Linux. Seul 127.0.0.1 est contacté. Un serveur de sockets
brutes envoie les octets exacts, pour que les réponses mal formées atteignent
`http.client` telles quelles. Ailleurs, un faux connecteur compte chaque échange.
Sorties : [G011](probes_g011-output.txt) · [G008 adaptées](probes_g008_adapted-output.txt).

Classement : **DÉFAUT** confirmé · **LIMITE** annoncée · **PROPOSITION** ·
**CONFORME**. L'absence de défaut dans ces sondes ne valide pas le Web en général.

## Copie adaptée des sondes G008

[`probes_g008_adapted.py`](probes_g008_adapted.py) applique trois
transformations, et rien d'autre : T1 `FakeConnector.exchange(..., deadline)`
devient `remaining_seconds` ; T2, l'appel direct de P8
`deadline=time.monotonic() + 2` devient `remaining_seconds=2` ; T3 change
l'en-tête et la description. Sur la nouvelle base, l'original lève `TypeError`
sur ces deux appels. C'est le changement de signature voulu, pas un D2 non corrigé.

Résultat : P1 passe de 4 connexions indues à 0 (D1). P10 rend désormais une
lecture saine avec une horloge à 0 et à 1e9 (D2). La valeur `Retry-After` en
chiffres arabes (P2) donne maintenant une suspension en revue au lieu d'être
perdue. P3 à P9 sont inchangés, comme prévu (C1, C3, C4, L1, L3 restent ouverts).

## Défaut

### D3 — Arrondi flottant à la frontière `remaining_seconds` (Q4)

`fetch` calcule `deadline = clock() + total_seconds`, puis
`remaining = deadline - clock()`. Si l'horloge rend deux fois la même valeur,
`(c + t) − c` peut dépasser `t` d'un epsilon. Le connecteur standard exige
alors `0 < remaining_seconds <= total_seconds` et lève `ContractError`.

Reproduction : lecteur à horloge figée sur `237.965`, limites par défaut (30 s),
connecteur standard sur 127.0.0.1. Calcul : `(237.965 + 30.0) − 237.965` =
`30.00000000000003`. Résultat : `ContractError`. Via le coordinateur, la source
devient `READER_ERROR`, sans contact du serveur. Témoin `238.0` : lecture normale.

Fréquence en calcul pur, avec `t = 30` et une horloge tirée au hasard dans
[0, 1000) : environ 3,5 % des valeurs. Avec `t = 0,3` : de 27 à 59 % selon la
plage. En production sous Linux, `time.monotonic` avance entre les deux appels,
et le cas devient très improbable. Il reste certain avec une horloge figée de
test, et possible avec une horloge à résolution grossière.

Gravité faible : le défaut échoue en sécurité (aucun contact). Mais il produit
une erreur de contrat sur une lecture saine, classée `READER_ERROR` au lieu d'un
échec de transport. Correction possible : borner dans `fetch` avec
`remaining = min(deadline − clock(), limits.total_seconds)`.

## Conformes (sondés)

- **D1 sur doubles (Q1)** : 8 anomalies × 429 et 503 (Retry-After dupliqué,
  Content-Type dupliqué, CL + TE, longueur invalide, caractère de contrôle, nom
  d'en-tête invalide, 101 paires, en-têtes > `max_header_bytes`). Chaque fois :
  une seule connexion, suspension en revue, `headers_validated=false`, code
  d'erreur nommé. Aucune valeur brute ni corps d'erreur dans le rapport. Un
  nouveau passage avec 10⁷ s d'horloge synthétique en plus (~115 jours) ne
  recontacte toujours pas le domaine.
- **D1 sur serveur local (Q2)** : 5 réponses mal formées réelles (429/503) →
  un seul contact, statut observé conservé, aucune fuite du corps.
- **Témoins (Q3)** : un 200 avec `Content-Length` dupliqué reste refusé
  (`INVALID_RESPONSE`). Les statuts `"429"`, `429.0`, `True`, `600` et `99` ne
  deviennent jamais une suspension. Pour un 429 mal formé après redirection,
  l'observation garde statut, URL finale, sauts, date et politique.
- **D2 (Q4, P10)** : le budget décroît entre sauts : [28, 21, 14] s pour 5 s
  d'échange et 2 s de garde, donc le temps du garde est bien décompté. Quand le
  budget est épuisé, le saut suivant n'est pas contacté. Le connecteur mesure
  son propre temps : un serveur qui attend 1,5 s avec 0,5 s restante donne
  `DEADLINE_EXCEEDED`.
- **C5 (Q5)** : 301 sans `Location` → `INVALID_RESPONSE`. Une redirection vers
  un réseau bloqué, un schéma ou un port non autorisés → `POLICY_REFUSED`, sans
  contacter la cible.
- **Textes** : WEB-READER.md et le rapport de correctifs ne promettent ni
  échéance dure (« n'ajoute pas d'interruption dure »), ni TLS entièrement figé
  (minimum de version, suites et `verify_flags` déclarés non couverts), ni cache
  exclu après toute annulation (C1 déclaré ouvert).

## Limites annoncées, mesurées

- **Parseur avant statut (Q2)** : ligne d'en-tête de plus de 65 536 octets,
  101 en-têtes pour `http.client`, ou ligne de statut invalide. Le statut n'est
  jamais observé (`status=None`), la source devient `INVALID_RESPONSE`, et
  **l'URL suivante du même domaine est contactée**. C'est documenté
  (WEB-READER.md l. 43 ; rapport de correctifs, ligne D1). Je ne prétends pas
  qu'un 429 a été vu : le serveur l'a envoyé, mais le client ne l'a pas lu.
- **L1** : le serveur qui attend 1,5 s pour 0,5 s restante occupe bien 1,5 s.
  Le délai de lecture reste `read_seconds` et n'est pas borné au temps restant.
  La réponse complète arrivée pendant ce délai est perdue (`DEADLINE_EXCEEDED`
  avant le corps), alors qu'un corps lent garde son reçu en retard (divergence
  déjà notée en G008).

## Propositions (non demandées comme correctifs)

1. Pour D3 : `min(deadline − clock(), total_seconds)`, plus un test avec
   horloge figée à `237.965`.
2. Après un échec du parseur sur un domaine, une courte pause conservatrice de
   ce domaine dans la session. La réponse ne prouve pas un 429, mais un serveur
   qui envoie du HTTP invalide ne mérite pas d'être relancé aussitôt. À trancher
   par Codex : coût sur les sites simplement cassés.
3. Borner le délai de socket par le temps restant
   (`min(read_seconds, restant)`), ce qui réduit L1 sans le supprimer.

## Limites de cette revue

Pas de TLS négocié, pas de réseau réel, Python 3.11 (Codex : 3.12). Les durées
de Q4 dépendent de la machine. Fréquences de D3 calculées hors réseau.
