> **Actualisation G272 :** ce guide reste la base profils/Internet/maintenance. L’import PDF/Office et les copies privées sont désormais raccordés ; voir DOCUMENTS-G272, PROFILS-ENROLEMENT-G272 et ETAT-PRIVE-G272. La synchronisation automatique des bibliothèques reste distincte.

# Recette des raccordements G270

Les chemins et comptes ci-dessous sont des exemples à remplacer après inventaire.
Ne pas les appliquer sur le corpus courant. Aucune commande n'a été exécutée sur
les VM ou le PC. Le choix du compte C187 reste ouvert.

## 1. Sources et installation de recette

Vérifier les SHA du manifeste, les dépendances épinglées et les empreintes du ZIP.
Créer un état Core de recette, un client appairé et une racine Memory privée par
personne. Les identifiants de client proviennent de l'appairage réel, pas d'une
identification biométrique. Ne pas donner la même clé à deux personnes.

Préparer explicitement la liaison de chaque racine existante :

```sh
python -m services.profile_binding --root /CHEMIN/PROFIL --profile toytoy
python -m services.profile_binding --root /CHEMIN/PROFIL --profile toytoy --apply
```

Le premier appel retourne NOT_PREPARED/code 2 s'il n'y a pas de liaison. Le second
crée seulement la liaison technique. Il ne répartit pas un ancien corpus partagé.
Une racine liée à un autre profil est refusée. Pour une copie de test, ne copier
que les informations que cette personne est autorisée à lire.

## 2. Memory et index

Copier et adapter `index.example.json` (modèle/digest exacts, alias propre
au profil, ports locaux). Créer le nouvel alias sur une copie arrêtée avec la
commande rebuild de G269. Le prochain `sync` ne ré-encode que les documents qui
changent ; il copie néanmoins les anciens vecteurs et inventorie tout le corpus.
Ne pas prévoir une complexité O(1). Ne pas lancer deux écrivains sur le même alias.

Le pont de profil exige `--profile-id`. L'écriture exige aussi `--remember-profile`
et un **second** secret `EIDOLON_MEMORY_WRITE_TOKEN`, différent de
`EIDOLON_MEMORY_BRIDGE_TOKEN`. Préparer ces secrets hors dépôt, dans un fichier
privé fourni à systemd. Le mode lecture seule historique reste disponible, sans
écriture : ne pas lui ajouter l'option d'écriture par automatisme.
`memory-profile.service.in` montre le mode avec écriture, à examiner sur copie.

## 3. Core et profils

Avant lancement, exécuter le [diagnostic G271](DIAGNOSTIC-G271.md) sur la
configuration préparée, puis son mode `--local-files` sous le compte cible.
Un résultat valide ne remplace pas les essais de service et d'isolation ci-dessous.

Copier `beta-runtime.example.json` en fichier 0600, dans un répertoire privé.
Créer son `state_directory` en 0700. Chaque profil utilise un port Memory et des
fichiers de jetons distincts, puis le pont confirme son identité à chaque réponse.
Les chemins de jetons et racines NAS ne sont jamais choisis par le navigateur.
Les clients non liés sont refusés. Le rappel partagé historique est exclu lorsque
`--beta-runtime` est utilisé. Ne pas modifier une liaison en place : une autre
configuration est refusée sur le même état. Prévoir une migration explicite ou
un nouvel état ; conserver les anciens reçus privés.

Lancer Core avec `--conversations MODEL.json --beta-runtime CONFIG.json` et les
options habituelles état/token/web-root. Exemple d'unité : `core-profile.service.in`.
La sélection d'un modèle de dialogue est différente de l'identité de personne.

Dans le chat, ouvrir « Retenir ceci · Internet · Fichiers ». Préparer le texte,
relire, confirmer. Vérifier le reçu, fermer/recharger et le retrouver. Simuler une
réponse perdue : reprendre **la même** mémorisation avec le même reçu. Vérifier
qu'une seule Information a été créée et reste UNVERIFIED. Tester une deuxième
clé/profil et son absence d'accès à la première mémoire.

## 4. Internet et NAS/PC

SearXNG doit déjà être installé/configuré en boucle locale, avec le format JSON
activé. La configuration ne l'installe pas et ne choisit pas ses moteurs.
Confirmer une recherche exacte ; vérifier ses sources et les erreurs de moteur.
Le bouton « Interroger Eidolon sur ce résultat » transmet le reçu sélectionné
au modèle comme observation non vérifiée, avec sa date ; aucun nouvel appel Web
ou lecture de fichier n'est déclenché. Un extrait de 3 600 caractères est utilisé,
avec marque explicite s'il est tronqué. La source est figée avec le tour et
conservée lors d'une reprise.
Tester la lecture d'une URL HTTPS publique, le refus des adresses privées et une
page indisponible. Recherche et lecture consomment un quota durable commun par
profil/jour UTC. Redémarrer Core puis vérifier que le quota n'a pas été remis à
zéro. Une tentative ambiguë n'est jamais renvoyée automatiquement.

Monter le dossier NAS de recette avec les droits minimums avant de le déclarer
sous `file_roots`. Tester liste et lecture UTF-8 (64 000 octets maximum), chemins
parents, liens et fichier modifié entre aperçu/confirmation. Aucun fichier NAS
n'est écrit. Le sélecteur du navigateur ouvre un texte PC (16 000 octets maximum)
sans envoi avant préparation/confirmation. G272 ajoute un sélecteur documentaire
binaire et l’extraction bureautique : voir DOCUMENTS-G272. La synchronisation
automatique de bibliothèques reste hors de ce raccordement.

## 5. Activité et maintenance entre VM

Core exporte `activity.json` dans l'état privé toutes les dix secondes. Les
interactions appairées et demandes en cours rafraîchissent l'activité ; le simple
passage du temps ne le fait pas. L'arrêt de Core rend la preuve périmée et bloque
la maintenance. Cela mesure l'usage **d'Eidolon**, pas toutes les applications PC.

Sur Memory, utiliser un tunnel local vers l'API Core, le jeton Core de lecture,
`maintenance-profile.example.json` et `maintenance-remote.service.in`. Le point
GET `/v1/activity` est en lecture seule et ses consultations ne comptent pas comme
activité utilisateur. Vérifier l'heure des deux VM. Mode de contrôle :

```sh
python -m eidolon_core.maintenance_host --policy /CHEMIN/policy.json \
  --activity-core-port PORT_LOCAL --activity-token-file /CHEMIN/core-read-token \
  --check-only
```

Pour l'exécution, remplacer `--check-only` par `--runtime /CHEMIN/runtime.json
--execute`. La portée `isolated_profile_root` autorise explicitement les nouvelles
informations de cette racine liée au profil ; elle évite une modification manuelle
de la liste d'identifiants à chaque mémorisation. Vérifier 04–08 h Europe/Paris,
30 minutes d'inactivité et de démarrage, charge basse. Une reprise d'activité
interrompt la synchronisation entre opérations ; un appel d'embedding déjà en
cours termine ou expire avant l'interruption. L'ancien alias reste visible.
L'expiration systemd de 120 s peut empêcher de terminer un gros index : mesurer
avant de modifier cette limite. Pas de suppression automatique des générations.

## 6. Windows résident

Le workflow « Core Windows candidate » construit l'exécutable Tauri et fournit
l'artefact `eidolon-windows-candidate`. Contrôler son SHA et le SHA source du run.
Placer le binaire et `desktop/windows/*.ps1` dans un dossier privé stable, hors
répertoire partagé modifiable par un autre utilisateur. Les scripts respectent
la politique d'exécution PowerShell du poste ; aucun contournement n'est ajouté.

`eidolon-resident.ps1 -ClientExe ... -ExpectedSha256 ...` est un aperçu sans effet.
Avec `-Run` sous PowerShell `-STA`, il affiche l'icône native « e », ouvre le client
et reste présent lorsque la fenêtre est fermée. Menu : ouvrir, fermer la
conversation, quitter. Si Core/tunnel est indisponible, l'icône reste disponible
pour un nouvel essai. Le lanceur SSH existant conserve la responsabilité du tunnel.
Aucun token n'est conservé par le résident ; fermeture réelle de la fenêtre =
fin de sa session, nouvelle saisie de la clé à la réouverture.

`eidolon-startup.ps1` prépare la commande de démarrage à la connexion Windows.
Fournir les chemins et empreintes du script et du binaire ; vérifier l'aperçu.
`-Apply` inscrit seulement HKCU/Run/EidolonCore pour l'utilisateur courant.
`-Remove -Apply` enlève uniquement la valeur exacte attendue. Un conflit est
refusé. Ne pas lancer ces modes pendant une simple inspection du paquet.

Recette physique indispensable : WebView2, icône 16/32 px, double-clic, fermeture,
réouverture, tunnel absent/revenu, démarrage après connexion Windows, microphone
et caméra explicitement autorisés, arrêt de la capture et sortie du résident.
