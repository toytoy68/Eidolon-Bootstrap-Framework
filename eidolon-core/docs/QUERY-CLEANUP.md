# Nettoyage local des requêtes — C-013

07/10/2026. Implémentation de la direction C-D10 rapportée par Claude dans
C061 : retirer les données personnelles repérées avant l'envoi. Aucun
fournisseur réel, abonnement, accès Internet ou appel de modèle ajouté.

`clean_query(text)` est une fonction pure, bornée à 1 000 caractères avant et
après normalisation. Elle produit le texte nettoyé pour **prévisualisation
locale**, deux empreintes SHA-256 et les comptes par catégorie. Son reçu ne
contient ni les valeurs retirées ni le texte nettoyé. Les empreintes ne sont
pas une protection contre les recherches par dictionnaire.

Le coordinateur candidat appelle cette fonction **avant tous ses fournisseurs**,
y compris les replis. Aucune option ne désactive ce nettoyage dans `run`.
Le nettoyage ne modifie pas les permissions et n'active aucun fournisseur.
Les fournisseurs injectés restent du code de confiance ; ils ne sont pas
isolés par cette fonction. Une requête vide après retrait retourne
`QUERY_EMPTY_AFTER_CLEANUP`, `discovery_status=NOT_REQUESTED`, sans fournisseur,
lecteur, DNS ni écriture de pause.

## Ce qui est retiré

- Courriels de forme reconnue, y compris après normalisation NFKC et retrait
  des caractères Unicode de format (notamment invisibles).
- Téléphones français à dix chiffres commençant par 01–09 et numéros
  internationaux avec `+` de 10 à 15 chiffres ; séparateurs usuels. Une
  référence produit de même forme est également retirée.
- Formes d'IBAN en majuscules, sans validation bancaire de la clé.
- URL `http`, `https`, `ftp`, `file` **entières**, même publiques : garder le
  domaine seul laisserait des informations dans les chemins/paramètres.
- Chemins Windows/UNC et préfixes locaux Unix reconnus : `/home`, `/Users`,
  `/root`, `/etc`, `/var`, `/mnt`, `/media`, `/tmp`, `~/`. Les chemins entre
  guillemets doubles peuvent contenir des espaces ; un chemin non cité s'arrête
  au premier espace. Les autres variantes ne sont pas garanties.
- Adresses IPv4/IPv6 valides reconnues, même publiques.

Le texte est normalisé avant détection ; les espaces sont ensuite consolidés.
Des caractères de contrôle non textuels et des chaînes non UTF-8 sont refusés
par un diagnostic constant, sans réafficher la requête.

## Limites explicites

Ce n'est **pas une anonymisation** : noms, adresses postales, courriels épelés,
citations privées et secrets de format libre peuvent rester. Les titres,
extraits et corps des résultats ne sont pas nettoyés par cette fonction.
Les faux positifs réduisent parfois la pertinence. Le reçu indique toujours
`anonymity_guaranteed=false` et `authorizes_transmission=false`.

L'affichage/confirmation avant émission externe, les catégories sensibles,
la durée des décisions et leur conservation restent à définir pour le futur
produit. Aucun envoi automatique réel n'est décidé ici. Le corpus G029 est
conservé à l'identique ; [ses 27 résultats synthétiques et les tests](validation/2026-10-07/codex-query-cleanup/)
documentent ce que cette version retire **et ce qu'elle laisse**.
