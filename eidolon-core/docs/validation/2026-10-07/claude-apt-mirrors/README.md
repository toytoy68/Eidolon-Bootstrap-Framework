# Miroirs APT supplémentaires — décision C-D11

Auteur : Claude, 07/10/2026. Décision de toytoy : « Liste miroir a ajouter si
il y en a. » ([C-D11](../../../CADRAGE-DECISIONS-2026-10-05.md)).
Rectification autorisée des trois scripts (C040). **Aucun installateur
exécuté ni sourcé** : la fonction est extraite et testée sur des fichiers
fictifs.

## Changement dans `02-nvidia.sh` (`add_debian_components` seulement)

- Nouvelle variable `EIDOLON_APT_EXTRA_MIRRORS` : liste **explicite**
  d'hôtes exacts, sous la forme `nom` ou `nom:port`, séparés par des espaces.
  Elle est **vide par défaut**, car aucun miroir n'a été donné.
- Un hôte listé est traité comme un miroir officiel. Le chemin doit rester
  `/debian` ou `/debian-security`. La comparaison porte sur l'hôte entier :
  pas de sous-chaîne, et un autre port n'est pas le même hôte.
- Une entrée invalide (majuscules, `*`, chemin, option, `;`, port trop long)
  arrête la fonction : **aucun fichier modifié**, message d'erreur, et
  l'installateur s'arrête par `error`.
- Le diagnostic d'une source non reconnue indique maintenant la variable à
  remplir.

Utilisation sur la VM, si elle passe par un miroir non officiel :

```sh
sudo EIDOLON_APT_EXTRA_MIRRORS="miroir.exemple.org" ./02-nvidia.sh
```

Pour savoir quel miroir la VM utilise, regarder la colonne de l'adresse dans
`/etc/apt/sources.list` et `/etc/apt/sources.list.d/*.sources`. Si
l'hôte n'est ni `deb.debian.org`, ni `security.debian.org`, ni
`ftp.<pays>.debian.org`, il faut le lister.

## Preuves

- [Nouveaux cas, avant le changement : 11 échecs](test-before-ba800da.txt)
- [Après : 15/15](test-after.txt) : miroir listé, `nom:port`, autre port,
  sous-domaine piège, autre chemin, deb822 avec deux miroirs, source tierce
  voisine intacte, 6 entrées invalides refusées, liste vide.
- [Les 23 cas G033 rejoués : 0 échec](g033-cases-rerun.txt)
- [bash -n des trois scripts, shellcheck](scripts-check.txt)

Limites : testé avec mawk 1.3.4 sous Linux, sans VM ni `apt update`.
