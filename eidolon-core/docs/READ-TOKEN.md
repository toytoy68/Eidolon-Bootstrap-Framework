# Créer un jeton de consultation — C-009d

Codex/GPT, 06/10/2026. Utilitaire local **Linux** ; aucune connexion, aucun
service démarré, aucun fichier existant écrasé. Il génère un secret aléatoire
de 256 bits, compatible avec http_api, et le publie dans un nouveau fichier
privé appartenant à l’utilisateur courant (mode 0600).

```sh
PYTHONPATH=src python -m eidolon_core.access_token \
  --output /chemin/etat-existant/read-token --format human
```

Le dossier parent doit exister et être de confiance. Le dernier composant du
parent ne doit pas être un lien symbolique ; les ancêtres et le dossier restent
sous la responsabilité de l’opérateur. Rien n’est créé dans un parent absent.
Choisir un dossier d’état hors du dépôt et ne jamais versionner le jeton.

Le contenu n’est affiché ni en sortie JSON ni en mode humain. Le consulter
localement lors de la connexion du client, comme dans la recette bêta. Ne pas
le transmettre dans les messages ou journaux. Aucun fichier de configuration
du client, coffre de secrets, presse-papiers ou stockage navigateur n’est modifié.

## Publication et erreurs

Le contenu complet est écrit et fsync dans un temporaire privé, puis publié
par lien physique **sans remplacement**. Le temporaire est retiré et le dossier
synchronisé. Deux créations concurrentes sur le même nom ne peuvent pas
s’écraser. Fichier existant, répertoire, FIFO ou lien symbolique à destination
sont tous refusés. Un système de fichiers ne prenant pas en charge ces
opérations est refusé ; pas de repli qui expose un fichier incomplet.

JSON par défaut : `protocol: eidolon-read-token-setup/1`.

| status | Sortie | Sens |
| --- | --- | --- |
| CREATED | 0 | Nouveau fichier publié, nettoyage et synchronisation du dossier confirmés |
| NOT_CREATED | 2 | Cette invocation n’a pas publié de jeton ; une destination préexistante reste intacte |
| CREATED_REVIEW_REQUIRED | 2 | Nouveau fichier publié, mais synchronisation du dossier ou nettoyage incomplet ; vérifier avant de poursuivre |

`destination_created`, `cleanup_complete`, `durability_confirmed` précisent le
résultat. Aucun chemin, token ou empreinte n’est exporté. `existing_servers_updated`
et `authorizes_execution` sont toujours false. **Un code 2 n’implique pas
forcément l’absence du nouveau fichier** : lire le statut avant une reprise.
Si le nettoyage échoue, un temporaire `.eidolon-read-token-*` peut subsister
dans le dossier ; il contient lui aussi un secret et doit rester privé. Ne pas
supprimer indistinctement les fichiers d’une autre création en cours.

`DESTINATION_EXISTS` signifie choisir un autre nom ou examiner le fichier
existant ; aucune option force n’existe. Les autres codes distinguent dossier
inaccessible, écriture, publication, synchronisation et nettoyage. Un arrêt
brutal peut laisser un temporaire ou un fichier publié dont cette invocation
n’a pas confirmé le résultat : vérifier localement, sans supposer une absence.

## Vérifier puis lancer

Passer ce fichier à `http_api --check` avec l’état et le client souhaités, puis
lancer explicitement le serveur si la recette est prête. Pour changer de jeton,
créer **un nouveau fichier**, arrêter le serveur, puis le relancer avec ce
fichier. Les processus déjà lancés gardent leur ancien jeton en mémoire : cet
utilitaire ne révoque rien à distance et ne les modifie pas.

Ce jeton ouvre la lecture de cette API ; ce n’est ni une identité humaine
authentifiée ni un droit de soumettre/exécuter une commande. Pas de test
Windows/SSH ni de garantie sur un système de fichiers réseau.
