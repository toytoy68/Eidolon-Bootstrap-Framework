# C-011 — raccordement HTML candidat, 07/10/2026

Base de départ locale 9709cce, arbre correspondant à la publication 92e102d.
Extracteur G026/G032 préservé (docstring actualisée seulement). Le lecteur
porte les limites optionnelles ; le coordinateur extrait les octets après
contrôles et conserve séparément provenance HTTP et métadonnées d'extraction.

## Vérification

- [123 tests ciblés réussis](targeted-tests.txt), dont 12 nouveaux scénarios
  d'intégration : option désactivée, charset et BOM, statuts complets/partiels,
  seuils de profondeur/segments/volume, absence de fetch des ressources,
  cache/provenance, reçu falsifié, déduplication, expiration pendant extraction,
  signaux d'accès et persistance du refus de paywall.
- Un test fait un vrai échange HTTP **loopback seulement** ; la politique
  utilise des IP fictives puis un connecteur de test les mappe sur 127.0.0.1.
  Ces IP de fixture ne représentent pas une connexion Internet réelle.
- [Suite Python complète](final-python.txt) : **633 tests, 627 réussis,
  6 intégrations mémoire non exécutées**, 112,890 s, Linux/Python 3.12.14.

Le premier essai du nouveau test de pause utilisait un dossier au lieu du
chemin de fichier attendu par ResearchPauses ; corrigé dans le banc avant ces
résultats. Aucun défaut de persistance extrapolé de cette erreur de test.

## Limites

HTML désactivé par défaut ; aucune activation CLI/runtime ni fournisseur Web
réel. Détection des murs d'accès heuristique et partielle. Extraction PARTIAL
n'adopte aucun texte comme READ. Une lecture n'est ni une preuve d'exactitude
ni une mission réussie. Pas de CSS/JavaScript ou récupération de sous-ressources.
Transport/identités injectés sont du code de confiance, pas une sandbox.
Les pauses requièrent toujours une revue explicite ; aucune requête relancée
par ce lot. Contrat : [WEB-READER.md](../../../WEB-READER.md).
