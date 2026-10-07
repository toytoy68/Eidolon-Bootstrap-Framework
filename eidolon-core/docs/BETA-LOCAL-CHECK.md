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
