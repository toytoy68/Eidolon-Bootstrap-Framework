# Politique de destination Web — C-002a

Auteur : Claude, 05/10/2026, fiche [C-TASK-C001](../collaboration/tasks/C-TASK-C001.md),
choisie dans la TODO (lot C-002). Base : `ed38312`. Statut initial : module livré
**non raccordé** (ni `Policy`, ni runtime, ni CLI) et **aucun connecteur HTTP**.

Module : [`src/eidolon_core/egress.py`](../src/eidolon_core/egress.py).
Tests : [`tests/test_egress.py`](../tests/test_egress.py), 12 tests, résolveur
simulé ; un test fait échouer `socket` pour prouver l'absence d'accès réseau.

## Rôle

Répondre à une seule question avant toute connexion Web : **cette URL mène-t-elle
à une adresse publique, et laquelle ?** Le module ne télécharge rien. Il rend une
décision (`Decision`) avec l'adresse à utiliser, ou un motif de refus.

Le LAN, le NAS, Memory Engine et les PC ne passent **jamais** par ici : ce sont
des cibles du catalogue (`targets.py`), avec leurs propres règles. Le refus des adresses privées couvre un premier cas ; il ne suffit pas pour
les adresses publiques du foyer, les routes particulières ou une traduction
IPv6 locale. Voir les exclusions et limites de la révision `/2` ci-dessous.

## Règles

| Étape | Règle | Refus |
| --- | --- | --- |
| Forme | Au plus 2 048 caractères ; ni espace ni caractère de contrôle (jamais « réparé ») | `BAD_URL` |
| Schéma | `https` seul par défaut ; `http` seulement par une `WebPolicy` explicite | `SCHEME_REFUSED` |
| Identifiants | Aucun `user:pass@` (ni `@` qui masquerait l'hôte réel) | `CREDENTIALS_IN_URL` |
| Port | 443 par défaut ; autres ports seulement par politique | `PORT_REFUSED`, `BAD_PORT` |
| Hôte | Nom IDNA en minuscules, au moins deux labels ; un nom à un seul label passerait par les domaines de recherche locaux | `BAD_HOST` |
| Noms locaux | `.local`, `.lan`, `.home`, `.internal`, `.localhost`, `.localdomain`, `.arpa` | `LOCAL_NAME` |
| Formes numériques ambiguës | `2130706433`, `0x7f000001`, `017700000001`, `127.1`… que certains résolveurs lisent comme IPv4 | `AMBIGUOUS_NUMERIC_HOST` |
| Résolution | Résolveur injecté ; erreur, réponse vide, invalide ou de plus de 32 adresses | `RESOLUTION_*` |
| Adresses | **Toutes** les adresses doivent être publiques ; une seule non publique refuse le nom | `DESTINATION_<motif>` |
| Épinglage | L'adresse retenue (`Decision.address`) est la seule à laquelle le connecteur pourra se connecter | — |
| Redirections | Chaque saut est revérifié ; 5 au plus par défaut ; jamais de https vers http | `TOO_MANY_REDIRECTS`, `DOWNGRADE_REFUSED` |

Motifs d'adresse : `LOOPBACK`, `LINK_LOCAL` (dont `169.254.169.254`, l'adresse
des métadonnées cloud), `UNSPECIFIED`, `MULTICAST`, `TEREDO`, `IPV4_COMPATIBLE`,
`NOT_GLOBAL` (privées, CGNAT `100.64/10`, documentation, bancs d'essai, réservées).

## Ce que la bibliothèque standard ne suffit pas à couvrir

`ipaddress.is_global` de Python 3.11 déclare **globales** trois familles
d'adresses qui mènent pourtant à un réseau local. Le module les traite
explicitement (constaté ici, Python 3.11.15) :

| Adresse | `is_global` | Réalité | Traitement |
| --- | --- | --- | --- |
| `224.0.0.1` | vrai | multicast | refus `MULTICAST` |
| `64:ff9b::7f00:1` | vrai | 127.0.0.1 traduit par NAT64 | IPv4 extraite puis classée : `LOOPBACK` |
| `::127.0.0.1` | vrai | forme IPv6 « compatible IPv4 », obsolète | refus `IPV4_COMPATIBLE` |

Sont aussi déballées : les adresses IPv4 encapsulées (`::ffff:a.b.c.d`), 6to4
(`2002::/16`) et NAT64 local (`64:ff9b:1::/48`). Teredo est refusé en bloc.

## Responsabilités qui restent au futur connecteur

Le module ne protège que si le connecteur respecte sa décision :
1. Se connecter à `Decision.address`, jamais refaire une résolution du nom.
   Le test « rebinding » montre qu'une seconde résolution aurait rendu `127.0.0.1`.
2. Envoyer le nom d'origine (`Decision.host`) en SNI TLS et en en-tête `Host`,
   et vérifier le certificat pour ce nom. Aucun contournement de certificat.
3. Ne suivre aucune redirection lui-même : appeler `follow()` à chaque saut.
4. Ignorer tout proxy système non approuvé : un proxy changerait la destination réelle.
5. Borner taille, durée et type de contenu, et traiter le contenu comme donnée
   non fiable, jamais comme instruction.
6. N'envoyer que les données minimales : une requête Web peut déjà divulguer un
   contenu privé (C-D02, cadrage).

## Raccordement proposé (non fait, fichiers du lot Codex)

- Une capacité `web.read` de classe `egress_read` dans le catalogue de cibles
  (`kind = web_public`) ; `Policy` l'autorise par liste explicite.
- Le précontrôle d'une étape Web appelle `decide()` ; l'exécutant reçoit la
  décision (adresse épinglée) et non l'URL brute.
- La politique (`WebPolicy`) entre dans `configuration()` par empreinte, comme
  le catalogue.

## Limites

Aucune requête réelle, aucun résolveur réel exercé. La qualité de l'IDNA est
celle du codec `idna` de Python (IDNA 2003). Les noms locaux sont une liste
finie, pas une preuve qu'un nom public ne résout pas vers un service local :
c'est le rôle de la vérification des adresses. Un DNS public qui renvoie une
adresse publique appartenant à l'utilisateur (son IP Internet) reste autorisé
par ce module : la distinguer demandera une liste d'adresses propres à
l'opérateur, à décider.

## Révision Codex/GPT C-002a.1 — contrat `/2`, 05/10/2026

Base Claude reçue `4283db9`, code initial `b869eef`. Les 12 tests initiaux sont
reproduits sous Python 3.12.14 ; les correctifs et 18 nouveaux tests portent le
total ciblé à 30. [Sondes, commandes et résultats](validation/2026-10-05/codex-c002a/README.md).
Les sections précédentes décrivent la livraison initiale ; les changements
suivants définissent désormais le comportement actif.

### Exclusions configurables

`WebPolicy(blocked_networks=(...))` accepte jusqu'à 256 adresses IP ou réseaux
CIDR, IPv4/IPv6. Les CIDR doivent désigner exactement un réseau : `8.8.8.8/24`
est refusé, pas élargi silencieusement en `8.8.8.0/24`. Une IP seule devient un
/32 ou /128. La liste est copiée, normalisée, dédupliquée, figée et incluse dans
`manifest()` et `policy_id` ; les listes de schémas/ports sont également figées.
Les valeurs réelles appartiendront à la configuration locale, hors Git.

```python
from eidolon_core.egress import WebPolicy, decide

# Adresses de classification fictives pour ce scénario, jamais contactées.
policy = WebPolicy(blocked_networks=("8.8.8.8", "2001:4860::/32"))
decision = decide("https://household.example/", lambda host, port: ["8.8.8.8"], policy)
assert decision.code == "DESTINATION_BLOCKED_NETWORK"
```

Le contrôle s'applique à l'IP littérale, à **chaque** réponse DNS et à chaque
redirection. Une réponse mixte contenant une IP exclue suffit à refuser le nom.
Il couvre aussi l'IPv4 extraite des formes IPv4-mapped, NAT64 connu /96 et 6to4,
et le préfixe IPv6 extérieur avant cette extraction. Un nom DNS différent ne
contourne donc pas une exclusion de son adresse dans ces cas testés.

`follow()` exige de conserver le `policy_id` de la décision précédente ; oublier
la politique ou la remplacer pendant la chaîne est une erreur de contrat.
Ce hash n'est **pas** un jeton signé d'autorisation ; les objets Decision et les
fournisseurs Python sont internes et de confiance. Une future API ne doit pas
accepter une décision construite par le modèle ou par un client externe.

### Refus stricts et URL canonique

- Erreur de parsing, Unicode non persistable, espaces/contrôles, antislash,
  échappement `%` mal formé et autorité IPv6 ambiguë : refus nommé.
- Port zéro et port vide refusés ; ils ne deviennent plus implicitement 443.
- Une redirection est contrôlée **avant** `urljoin` : aucun retrait silencieux
  d'un retour à la ligne ou d'une tabulation.
- URL autorisée reconstruite avec le nom IDNA contrôlé, port contrôlé,
  chemin/requête encodés, fragment retiré. Taille maximale après normalisation :
  2 048 caractères. Le futur transport utilisera les champs de cette décision.
- URL refusée non renvoyée dans Decision, pour ne pas recopier identifiants,
  requête privée ou caractères invalides ; le code du refus reste disponible.
- DNS : chaînes IP sans identifiant de zone (`%interface`), ni entier implicite.
  L'itération s'arrête après 33 éléments pour vérifier la limite de 32, même
  avec un générateur infini. Une erreur au milieu de la réponse refuse tout.

La bibliothèque Python avertit que le parsing URL ne valide pas les entrées et
retire certains contrôles : [documentation officielle Python 3.12](https://docs.python.org/3.12/library/urllib.parse.html#url-parsing-security),
consultée le 05/10/2026. Les sondes locales reproduisent ce comportement.

### Correction NAT64 local

Toute adresse `64:ff9b:1::/48` est maintenant refusée (`DESTINATION_NAT64_LOCAL`).
La version initiale extrayait toujours les 32 derniers bits. Ce n'est pas une
règle valable pour toute la plage /48 : les sous-préfixes de traduction peuvent
varier, et l'emplacement de l'IPv4 dépend de leur longueur. Choix conservateur :
refuser cette famille plutôt que deviner le traducteur présent.
Sources officielles consultées : [RFC 8215 §3](https://www.rfc-editor.org/rfc/rfc8215.html#section-3)
et [RFC 6052 §2.2](https://www.rfc-editor.org/rfc/rfc6052.html#section-2.2).
Le préfixe connu `64:ff9b::/96` garde son extraction définie.

Deux attentes des tests initiaux ont changé explicitement : refus global de
NAT64 local ; budget de redirections conservé dès la première décision.

### Démonstration et limites de déploiement

```sh
PYTHONPATH=src:. python -m examples.web_policy_demo
PYTHONPATH=src:. python -m examples.web_policy_demo --format human
```

Huit scénarios vérifient les décisions attendues sans aucun DNS ni HTTP réel.
Le mode humain réutilise la présentation Eidolon. `ALLOWED` signifie uniquement
que cette destination satisfait cette politique, pas qu'une connexion ou une
mission a réussi. Le modèle n'intervient pas dans ces décisions.

Le module reste **hors runtime et hors CLI principale**, sans connecteur HTTP.
La future intégration devra appliquer permissions, minimisation des données
sortantes, délais DNS/connexion/lecture, TLS, épinglage et preuves de réponse.
`system_resolver` existe mais n'est pas appelé par ces tests ou la démo ; le
budget de 33 réponses ne borne pas la durée d'un résolveur bloquant.

Aucune découverte du réseau du foyer, aucune mise à jour automatique d'IP ou
préfixe, aucune règle pare-feu/VPN générée ou appliquée. Une liste vide ne protège
pas une adresse publique personnelle. Les préfixes NAT64 propres à un opérateur,
routes et tunnels particuliers ne se devinent pas à partir d'une IP globale :
leur inventaire et leurs exclusions restent nécessaires. La classification de
la bibliothèque `ipaddress` dépend de Python ; recette de la version cible requise.
C-D08 impose une barrière système indépendante avant les accès réels. Ce module
ne la remplace pas et ne qualifie aucune API du robot ou machine personnelle.
