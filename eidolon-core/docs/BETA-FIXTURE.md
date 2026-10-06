# Jeu synthétique pour la recette bêta

C-009g, Codex/GPT, 06/10/2026. Outil local Linux, depuis `eidolon-core/`.
Il prépare six missions via les runtimes synthétiques existants, un jeton privé
et un manifeste de consultation. Aucun modèle externe, service mémoire réel,
service système ou serveur HTTP n’est appelé ou démarré. Le calcul de texte
local est réellement exécuté dans les workers habituels.

```sh
FIXTURE_PARENT=$(mktemp -d "${TMPDIR:-/tmp}/eidolon-fixture-XXXXXX")
FIXTURE="$FIXTURE_PARENT/demo"
PYTHONPATH=src python -m eidolon_core.beta_fixture --output "$FIXTURE" --format human
PYTHONPATH=src python -m eidolon_core.http_api \
  --state "$FIXTURE/state" --token-file "$FIXTURE/read-token" \
  --web-root desktop/connected --check --format human
```

Le parent doit déjà exister et être de confiance, ainsi que ses ancêtres.
La destination doit être absente : dossier, fichier ou lien existant sont
refusés sans modification. Une seconde préparation emploie une autre destination.
Le dossier racine est privé `0700`, le jeton `0600`, jamais affiché. Le JSON
est le format par défaut ; `READY` donne le code 0, tout autre résultat le code 2.

Après `READY` et le diagnostic `PASS`, le lancement reste explicite :

```sh
PYTHONPATH=src python -m eidolon_core.http_api \
  --state "$FIXTURE/state" --token-file "$FIXTURE/read-token" \
  --web-root desktop/connected --port 8765
```

L’API écoute seulement sur loopback. Pour le PC, suivre la
[recette Debian/Windows](BETA-ACCEPTANCE.md) et son tunnel SSH. Le diagnostic
ne valide pas le port libre, le navigateur ou le tunnel. Le jeton se consulte
localement dans son fichier pour le saisir dans le client ; ne pas le publier.

## Scénarios et observations attendues

| Rôle dans `manifest.json` | État | Observation utile |
| --- | --- | --- |
| `text_completed` | SUCCEEDED | Calcul synthétique terminé et vérifié |
| `not_started` | NEW | Mission créée, pas encore exécutée |
| `approval_pending` | BLOCKED | Proposition PENDING ; aucune autorisation donnée |
| `cancel_requested` | NEW | Annulation demandée, distincte d’une mission arrêtée |
| `cancelled` | CANCELLED | Mission annulée avant exécution |
| `approval_revoked` | BLOCKED | Proposition actuellement REVOKED, reçu ancien d’approbation conservé |

Le manifeste donne les identifiants et trois `receipt_queries`, directement
utilisables comme corps JSON sur `POST /v1/command-receipt`. Il ne contient ni
jeton ni chemin absolu. Les identifiants, horodatages et jetons varient entre
préparations ; les scénarios sont reproductibles, pas les octets SQLite.

Le compteur de redémarrages du service simulé est vérifié à zéro. Un reçu
historique d’approbation ne rend pas une proposition révoquée applicable et
n’atteste aucune exécution. Le client G036 doit encore intégrer la recherche
de reçus ; l’API permet déjà leur consultation.

## Échec et limites

Un marqueur `state/BETA-PREPARATION-INCOMPLETE` est créé avant le peuplement.
L’API et le diagnostic refusent cet état tant qu’il existe, y compris pour un
lecteur déjà construit. Il n’est retiré qu’après les vérifications de scénarios,
la création réussie du jeton et l’écriture synchronisée du manifeste. Les
chemins restent stables, sans déplacer une configuration déjà enregistrée.

En cas d’échec, le résultat est `INCOMPLETE` ; le dossier neuf reste disponible
pour inspection. Aucun nettoyage récursif ni reprise automatique n’est tenté.
Ne pas retirer manuellement le marqueur pour contourner le refus : choisir une
autre destination. Si l’interruption survient avant la base, le diagnostic peut
simplement signaler son absence. Ce garde protège la consultation ; ce n’est
pas un verrou de sécurité contre un opérateur modifiant volontairement les fichiers.

`READY` ne garantit pas la durabilité après coupure électrique. Ce jeu n’est
ni une sauvegarde, ni une installation, ni une qualification du serveur de
toytoy. Il est destiné à la lecture ; le modifier ou exécuter ses missions rend
les attentes du manifeste historiques. Aucun essai Windows/SSH réel n’est
revendiqué par cette génération.

Preuves : [séance du soir](validation/2026-10-06/codex-evening/README.md).
