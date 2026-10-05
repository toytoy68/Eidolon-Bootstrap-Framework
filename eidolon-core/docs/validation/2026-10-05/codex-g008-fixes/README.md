# Correctifs après contre-revue Claude G008 — Codex/GPT

Date : 05/10/2026, Europe/Paris. Base exacte :
`534099d34a1b5555eb3da465bb623006247ce154`, rapport Claude `e55dc5d`.
Python 3.12.14/Linux, bibliothèque standard ; openssl pour les tests TLS locaux.
Code cible : commit introduisant ce rapport, empreintes [source-hashes.json](source-hashes.json).

## Changements vérifiés

- D1 : statut entier 429/503 conservé après rejet des en-têtes par notre
  validateur ; suspension sans échéance dans la session, aucune valeur ambiguë
  adoptée. Deux URL du même domaine n'entraînent qu'une connexion. Corps absent.
  La réponse mal formée ne devient jamais une lecture réussie.
- D2 : durée remaining_seconds à la frontière du connecteur ; échéance locale
  monotone. Horloges lecteur à 0 et 1e9 testées sur serveur local ; contrôle
  du temps propre au connecteur sondé avec connexion simulée et horloge locale
  pilotée. Budget partagé entre redirections, garde before_hop décompté.
- C5 : redirection sans Location classée INVALID_RESPONSE, pas UNAVAILABLE.
- L3 : promesse TLS documentaire réduite au contrôle réellement implémenté
  (certificat requis et vérification du nom). Aucun nouveau durcissement TLS.

Changement volontaire du protocole candidat exchange : remaining_seconds
remplace deadline. Identités par défaut stdlib-http/3 et web-reader/2.
Le FakeConnector des tests et l'attente du test 302 sans Location sont adaptés.
Les sondes/rapports Claude d'origine sont conservés intacts ; leur ancienne
signature exige une adaptation dans une copie pour les rejouer sur cette base.

## Tests exécutés

- [regressions-before.txt](regressions-before.txt) : neuf premières méthodes
  du nouveau fichier sur le code de base, avant correctif. Échecs attendus,
  dont les assertions du nouveau protocole alors absent ; 12 échecs et 5
  erreurs de sous-cas. Ce journal rouge ne décrit pas l'état livré. Le dixième
  test (budget invalide refusé avant socket) a été ajouté ensuite.
- [core-tests.txt](core-tests.txt) : 309 tests découverts, **303 réussis**, six
  intégrations Memory Engine opt-in sautées ; durée 101,348 s. Les dix nouveaux
  tests de régression sont inclus, avec sous-cas 429/503 et horloges décalées.
- [demo-human.txt](demo-human.txt) : démonstration HTTP locale rejouée ; cinq
  requêtes, une lecture exploitable sur deux demandées, résultat PARTIAL.

Depuis eidolon-core/ :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_web_review_regressions -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m examples.research_http_demo --format human
```

Les connecteurs des tests locaux remplacent l'adresse publique de fixture par
127.0.0.1 après la politique. Pas d'exception loopback dans la politique réelle.
Les faux corps/URL sont synthétiques. Aucun site Internet, modèle, GPU, appareil
personnel, VM ou accès mémoire réel dans ces essais. Tests simulés et HTTP/TLS
loopback ne qualifient pas le réseau du foyer.

## Tri de tous les points G008

| Point | État après ce lot |
| --- | --- |
| D1 | Corrigé et testé pour un statut rendu par le parseur ; échec du parseur avant réponse reste sans observation HTTP |
| D2 | Corrigé et testé ; pas de promesse de délai global dur |
| L1 | Ouvert : DNS/recv en cours non interrompus ; goutte-à-goutte peut dépasser largement le budget ; pas de borne total + read garantie |
| L2 | Ouvert : suspensions RAM, perdues au redémarrage ; à persister avant intégration mission |
| L3 | Texte rectifié ; minimum TLS, suites et verify_flags restent à durcir séparément |
| C1 | Ouvert : cache encore possible après annulation ou retard du seul coordinateur ; date originale conservée |
| C2 | Compteur de reçus, pas verdict ; contrat précisé, aucun changement de code |
| C3 | HTTP_ERROR peut porter une attente ; champs documentés, éventuelle meilleure projection à traiter |
| C4 | Ouvert : URL finales et sources peuvent conserver la requête en clair ; minimisation nécessaire avant données personnelles |
| C5 | Corrigé et testé |

D1/D2 sont vérifiés par Codex ; la contre-revue indépendante est demandée dans
C-TASK-G011, pas présumée reçue. [Contrat actuel](../../../WEB-READER.md).
