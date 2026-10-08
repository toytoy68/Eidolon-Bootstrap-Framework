# Séance Core du 08/10/2026 — matin

Codex/GPT, reprise vers 09 h 24 Europe/Paris. Base `6f46219bfe578902f892d48c7437b042b2616a10`.
Travail sur `feat/eidolon-core-v0.1`, contributions Claude jusqu'à
`e403fd220f2b714b1c28e9f61b350f521c5ed2c1` intégrées avec leur historique.
Python 3.12.14, Linux. Corpus synthétiques, HTTP loopback et dossiers jetables.
Aucun modèle réel, GPU, Windows, NAS ou VM qualifié ; aucun changement Memory Engine.

## Résultat livré

- C-039 : contrat text.stats explicite dans les deux adaptateurs, version /4,
  sélection par demande exacte, empreinte des instructions ; permissions et
  vérification restent exécutoires dans Core.
- C-040 : `model-probe` prépare hors ligne ou exécute quatre cas synthétiques
  sur un endpoint configuré explicitement. Dossier privé neuf, empreintes,
  preuves par cas, arrêt au premier incident technique et marqueur d'incomplétude.
- C-041 : `model-probe-inspect` consulte les documents sans modèle, clé, Store,
  écriture ou reprise. Cohérence des documents seulement, pas authenticité du
  matériel ni nouvelle vérification des preuves SQLite.
- G065 intégré : blocage budgétaire expliqué avec reste disponible, mission
  historique inconnue normalisée. G064 reçu et trié ; G064-3 reproduit.
- Six nouvelles tâches G072–G077 publiées en `b81a9de`, anciennes tâches ouvertes
  préservées. Les fichiers ne démarrent aucune session Claude.
- Propositions [dashboard/contexte](../../../proposals/2026-10-08-dashboard-context.md)
  et [comparaison outillage](../../../proposals/2026-10-08-agent-toolbox.md)
  avec l'avis signé Claude. Préférences discutées, aucun choix utilisateur inventé.

[Guide des commandes](../../../MODEL-PROBE.md).

## Validation finale

**925 tests réussis, aucun échec ni saut, en 346,699 s**, avec les six intégrations
Memory Engine activées : [journal final](python-integrated-final.log).
Le paquet installé passe pour les deux candidats : [résultat](installed-integrated.json).
Empreinte du wheel contrôlé :
`90bbace39e2769297dbb81c4094f9e2751f6c2fb95131789ee4a6c94495bfdfb`.

Commande complète depuis eidolon-core, avec une copie en lecture seule des
sources Memory Engine b33c3a0 et données synthétiques :

```sh
PYTHONPATH=src:/chemin/memory-reference EIDOLON_MEMORY_INTEGRATION=1 \
  python -m unittest discover -s tests -t . -q
python docs/validation/2026-10-08/codex-hour-0924/installed-probe.py
PYTHONPATH=src python docs/validation/2026-10-08/codex-hour-0924/reproduce-g064-3.py
```

`installed-probe.py` construit sans réseau, installe dans un venv, compare les
52 modules octet pour octet puis invoque la CLI hors du répertoire source et
sans PYTHONPATH. Quatre cas passent par candidat ; trois requêtes HTTP pour une
suite complète (cas vide sans modèle), une seule pour une suite interrompue.
Préparation et inspection ne font aucun appel. Les secrets sont synthétiques et
ne figurent pas dans les preuves. Les serveurs simulés connaissent le contrat :
ce résultat ne mesure pas la capacité d'un vrai modèle à le suivre.

Le corpus lie sources/configuration/critères ; le nombre de tentatives dans les
rapports est une réservation Core, pas une mesure réseau. Les nombres de requêtes
ci-dessus viennent du serveur instrumenté du script d'installation.

## Échec intermédiaire conservé

`python-final-with-memory.log` contient 920 tests dont un échec dans le test HTTP
concurrent (503 reçu au lieu de 401). La réception d'une réponse ne signifie pas
que son worker a déjà libéré sa place : le test limitait les clients simultanés,
mais enchaînait avant cette libération. Le serveur est inchangé. Le test procède
par groupes concurrents avec fin effective des workers ; un nouveau cas bloque
leur fermeture et confirme 4 réponses reçues, puis 503, puis retour à 200 après
libération. Les assertions d'authentification restent exactes.
`g065-http-tests.log` : 50 tests ciblés réussis après intégration/correction.

Les autres journaux de ce dossier sont des étapes intermédiaires ; ils ne
remplacent pas la validation finale. `installed-probe*.json` documentent des
paquets antérieurs au dernier arbre intégré ; `installed-integrated.json` est
la vérification finale du paquet.

## G064 : réception, reproduction et suivi

Rapport/sondes Claude conservés dans ../../2026-10-07/claude-g064. Ses 45 refus
hostiles et sondes complètes sont rapportés, pas réexécutés ici. Lecture du diff
G065 et tests correspondants effectués sur l'arbre intégré.

`g064-3.json` provient de `reproduce-g064-3.py` : pause ACCESS_DENIED active,
remplacement par base vide valide, construction du runtime acceptée, aucune
pause restante. Aucune recherche relancée après remplacement. C-042 prioritaire
reste **à faire** : identité liée, migration explicite, coupures/restauration,
concurrence et conservation de l'audit. Ne pas qualifier ce point pour Web réel.
G064-1, limite du verrou coopératif, documenté. G064-2, libellé de cohérence
à la génération, et G064-4, exceptions Python SQLite, restent dans ce suivi.

## Publication

Le commit de livraison est celui contenant ce bilan sur la branche autorisée ;
son arbre doit être comparé au local testé et la référence distante relue après
publication. Ni fusion main, ni déploiement, ni lancement d'un modèle réel.
