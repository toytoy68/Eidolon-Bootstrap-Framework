# Recette locale autonome — C-010f/g

La commande teste des états synthétiques qu'elle crée dans un dossier temporaire.
Elle ne prend pas de dossier d'état existant et ne contacte que 127.0.0.1.
Les serveurs sont ses propres processus enfants, arrêtés par PID à la fin,
y compris sur erreur. Aucun installateur, GPU, SSH ou modèle n'est appelé.

Depuis `eidolon-core/`, Linux/Python 3.11+ :

```sh
PYTHONPATH=src python -m eidolon_core.beta_check --web-root desktop/connected
```

Sortie JSON `eidolon-beta-check/1`, code 0 pour PASS et 2 pour FAIL ;
`--format human` affiche la présentation ECT. Ne pas confondre cette commande
avec `http_api --check` : cette dernière n'ouvre aucun port, alors que
`beta_check` prépare et lance des serveurs temporaires sur des ports loopback
attribués par le système. Le dossier temporaire et les jetons sont retirés.

## Vérifications et preuves

24 contrôles : préparation, diagnostic, trois assets, authentification,
six états de mission, trois reçus historiques, absence d'écriture par la
consultation, création/annulation par la CLI visibles, redémarrage,
changement explicite de jeton et conservation de l'identité/curseur.

Le rapport donne les contrôles réussis et les SHA-256 des assets servis.
En cas d'échec, seuls les contrôles déjà réussis sont listés ; pas de sortie
brute des processus ou de secrets. `LOCAL_RECIPE_FAILED` n'identifie pas à lui
seul la cause ; reproduire les tests ciblés dans un environnement de développement.

## Installation isolée

Le wheel contient les modules Python, **pas le client Web**. Fournir le
chemin absolu du `desktop/connected` de la même version :

```sh
python -m eidolon_core.beta_check --web-root /chemin/du/depot/eidolon-core/desktop/connected
```

Aucun Git ou répertoire courant particulier n'est requis par la commande.
Le script de preuve `docs/validation/2026-10-07/codex-beta/package-smoke.py`
construit sans réseau, installe dans un venv temporaire, vérifie les modules
installés octet pour octet, le point d'entrée CLI puis rejoue les 24 contrôles.
La construction nécessite setuptools et wheel déjà installés ; elle ne les
télécharge pas. Elle ne constitue pas l'archive de sources G044.

Limites : pas de navigateur, Windows, tunnel SSH, serveur utilisateur, modèle
ou intégration distante Memory Engine validés par ce résultat. Un PASS local
ne qualifie pas l'assistant complet ni des actions distantes.

## Interruption et construction — suivi G047

SIGINT et SIGTERM déclenchent désormais le nettoyage des enfants possédés,
puis un rapport FAIL / INTERRUPTED avec le numéro de signal et un code de
retour 2. Les commandes CLI et serveurs temporaires ont chacun leur groupe
de processus ; la recette termine ce groupe, avec SIGKILL de secours, puis
retire son dossier temporaire. Aucun processus n'est sélectionné par son nom.
Les gestionnaires de signaux précédents sont restaurés à la sortie.
Un SIGKILL sur la recette elle-même ne peut pas déclencher ce nettoyage.

Claude a observé un échec `install_layout` avec un setuptools fourni par sa
distribution, et un succès en sélectionnant `SETUPTOOLS_USE_DISTUTILS=stdlib`
dans cet environnement. Ce n'est pas une correction universelle : certaines
versions Python ne fournissent plus distutils dans la bibliothèque standard.
La preuve de paquet distingue donc le backend effectivement testé ; ne pas
modifier globalement l'environnement Debian sur la base de ce seul résultat.
