# Rapport de recherche Web v2 — reçus et URL minimisées

Codex/GPT, 06/10/2026. `ResearchCoordinator.run()` retourne désormais version=2.
Le transport bas niveau (`FetchResult.evidence()`, Page) conserve son contrat.
Le module research_report projette uniquement un rapport interne validé ; ce
n'est pas une API d'import/validation de rapports arbitraires.

## Références affichées

Les champs `sources[].url`, `final_url` et `retrieval.final_url` ne gardent que
schéma, autorité et chemin. Paramètres et fragments sont retirés ; userinfo est
également retiré des descriptions de sauts facultatives. À côté de chaque URL
initiale/finale, `<champ>_sha256` identifie la chaîne UTF-8 canonique exacte avant
projection. `<champ>_query_sha256`, présent si query non vide, identifie les
paramètres. L'identifiant de source existant et la provenance ne changent pas.
Les contrôles de destination retirent déjà le fragment avant la connexion.

Deux URL différant uniquement par leur query peuvent afficher le même chemin,
mais gardent des empreintes distinctes. Ne pas les fusionner sur le seul champ
url affiché. Le compteur et la déduplication sont calculés AVANT projection.
Le chemin affiché n'est pas nécessairement une URL permettant de retrouver le
même document : les paramètres peuvent en déterminer le contenu. La projection
n'est pas un ticket de réexécution ; aucune relance ne se déduit d'un hash.

Les hops du transport standard minimisent déjà leur URL et conservent
query_sha256. Ils ne reçoivent pas une empreinte « URL complète » inventée depuis
un chemin déjà minimisé. Le projecteur retire aussi les queries éventuellement
fournies par un lecteur injecté. Une URL de hop facultative mal formée est omise
avec INVALID_URL ; un tableau de hops mal formé/trop long est omis avec INVALID_HOPS.
Ces diagnostics ne valident pas l'authenticité des descriptions de sauts.

## Cache et interruptions

Après annulation ou dépassement observé du délai du coordinateur/lecteur, les
reçus reçus restent dans le rapport, avec un statut CANCELLED/DEADLINE. Aucun
nouveau cache issu de cette opération interrompue n'est conservé, y compris les
pages précédentes de la même opération. Les anciens caches d'opérations achevées
ne sont pas invalidés systématiquement ; ils restent soumis au TTL, à la
politique et à l’éviction normale lorsque le cache est plein.

Une revalidation DNS lente du cache suivie d'annulation/délai n'adopte pas le
texte mis en cache et ne le compte pas comme lu dans cette opération. Les
arrêts sont coopératifs, sans garantie atomique face à une annulation survenant
après le dernier contrôle. Une page lue n'est jamais un fait confirmé.

La projection copie le rapport après les contrôles : URL de connexion, clés de
cache, URL finales internes pour revalidation DNS et déduplication restent
complètes. La date/hash de la lecture originale ne changent pas sur cache hit.

## Limites de confidentialité

Ce lot minimise les **champs URL structurés**, pas toutes les données. Chemins,
titres, extraits, texte des pages et éventuelles extensions du lecteur peuvent
contenir des informations sensibles, y compris des URL en clair. Les hashes
ne sont ni du chiffrement ni une protection contre un dictionnaire. Un rapport
n'est donc pas certifié « sans secret ». Ne pas y fournir de données privées
sur la seule foi de cette projection.

Le transport bas niveau, les arguments du lecteur et le cache RAM détiennent
encore les URL complètes. Ce lot n'ajoute ni journal persistant, ni exposition
authentifiée, ni garantie après crash, ni fournisseur externe. Leur politique
de rétention et une minimisation plus large restent à définir avant usage réel.

## Démonstration et tests

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m examples.research_disclosure_demo --format human
PYTHONPATH=src:. python -m examples.research_disclosure_demo
PYTHONPATH=src:. python -m unittest tests.test_research_disclosure -v
```

Données, DNS et lecteur simulés ; bibliothèque standard. Tests de redirection
avec WebReader/FakeConnector sans socket ; recette VM et moteur mémoire réelle
non couverte. [Preuves](validation/2026-10-06/codex-web-disclosure/README.md).

## Suite G024/G025 — comptage et découverte

Le rapport v2 ajoute `discovery_status` sans remplacer le statut de lecture :

| Valeur | Sens |
| --- | --- |
| HITS_FOUND | Au moins un lot valide de liens reçu, même si la politique ou la lecture les refuse ensuite |
| EMPTY | Tous les fournisseurs configurés ont répondu sans lien, sans interruption |
| UNAVAILABLE | Tous les fournisseurs configurés sont indisponibles, suspendus ou en erreur, sans interruption globale |
| INCOMPLETE | Aucun lien reçu mais couverture incomplète : mélange vide/erreur, fournisseurs non consultés, annulation ou délai |

Un EMPTY ne prouve pas l'absence d'information sur Internet. NO_READABLE_SOURCE
reste un bilan de lecture ; `discovery_status` précise désormais sa cause au
niveau de la découverte. Les diagnostics individuels des fournisseurs restent
présents. Aucun corps/texte d'erreur du fournisseur n'est recopié.

`readable_pages` ne recompte plus un corps SHA-256 identique déjà retenu dans
le rapport. La source supplémentaire garde son texte, son hash et sa provenance,
avec `state=DUPLICATE_CONTENT` et `duplicate_of` référençant la première source
comptée. Les URL de connexion et les clés de cache restent inchangées : un
paramètre fonctionnel n'est jamais supprimé pour supposer qu'il est publicitaire.
Même URL finale : DUPLICATE_FINAL conserve la priorité et ne compte pas un second
document, y compris si le contenu a changé entre deux lectures.

Les doublons sont recalculés à chaque rapport, y compris lors d'un cache hit ;
une page précédemment doublonnée peut donc être la première source du rapport
suivant. On conserve la comparaison **exacte des corps**, sans normalisation
sémantique : un espace ou une date modifiés peuvent produire deux hashes. Cela
ne démontre ni l'indépendance éditoriale ni la vérité de deux textes différents.
Les reçus arrivés après interruption restent distincts du succès de recherche.

Démo : `PYTHONPATH=src:. python -m examples.research_availability_demo --format human`.
