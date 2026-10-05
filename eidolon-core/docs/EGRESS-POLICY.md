# Politique de destination Web — C-002a

Auteur : Claude, 05/10/2026, fiche [C-TASK-C001](../collaboration/tasks/C-TASK-C001.md),
choisie dans la TODO (lot C-002). Base : `ed38312`. Statut : module livré
**non raccordé** (ni `Policy`, ni runtime, ni CLI) et **aucun connecteur HTTP**.

Module : [`src/eidolon_core/egress.py`](../src/eidolon_core/egress.py).
Tests : [`tests/test_egress.py`](../tests/test_egress.py), 12 tests, résolveur
simulé ; un test fait échouer `socket` pour prouver l'absence d'accès réseau.

## Rôle

Répondre à une seule question avant toute connexion Web : **cette URL mène-t-elle
à une adresse publique, et laquelle ?** Le module ne télécharge rien. Il rend une
décision (`Decision`) avec l'adresse à utiliser, ou un motif de refus.

Le LAN, le NAS, Memory Engine et les PC ne passent **jamais** par ici : ce sont
des cibles du catalogue (`targets.py`), avec leurs propres règles. Une URL
trouvée dans une page ou proposée par un modèle ne peut donc pas atteindre un
service interne par ce chemin.

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
