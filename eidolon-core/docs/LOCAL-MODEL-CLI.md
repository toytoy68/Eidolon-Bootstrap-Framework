# Planificateurs locaux explicites dans la CLI — C-032/C-036

Le profil text peut appeler les adaptateurs Ollama ou llama-server existants avec
--model-config. Le champ provider choisit explicitement le candidat à essayer.
Sans cette option, la démonstration reste déterministe et n'appelle aucun modèle.
Ce raccordement prépare la qualification sur serveur ; les essais livrés utilisent
des faux serveurs en HTTP loopback, pas un modèle, un GPU ou un moteur réel.

## Configuration opérateur

Créer localement un fichier JSON privé (permissions 0600), en choisissant le modèle
**déjà installé** sur le serveur. Exemple de forme ; remplacer le nom proposé :

```json
{
  "version": 1,
  "provider": "ollama",
  "endpoint": "http://127.0.0.1:11434",
  "model": "MODELE_INSTALLE:ETIQUETTE",
  "options": {"temperature": 0, "seed": 7, "num_predict": 512},
  "timeout_seconds": 60
}
```

Seuls 127.0.0.1 et ::1 littéraux sont acceptés par la CLI. Aucun hôte DNS,
adresse LAN, allow_non_loopback, identifiant ou clé dans l'URL/fichier, ni paramètre d'URL. Le
transport ignore les proxies et refuse les redirections. Cela ne prouve pas
l'identité d'un service local ; l'opérateur doit vérifier ce qui écoute au port.
Un tunnel local configuré séparément peut mener ailleurs : le choisir signifie
choisir le destinataire des données. Aucun tunnel n'est créé par Core.

La requête de mission et le contexte mémoire rappelé sont transmis au modèle.
La configuration vient du fichier opérateur, jamais du modèle, de la mémoire ou
d'une requête. Un fichier manquant, public, lien symbolique, FIFO, JSON ambigu,
clé inconnue ou fichier de plus de 16 Kio est refusé avant création d'état.
Les messages d'erreur du chargeur sont constants, sans contenu ni chemin privé.

Pour Ollama, num_predict est obligatoire, entier de 1 à 8192. Options autorisées : celles de
l'adaptateur, avec valeurs finies ; num_ctx 256–262144, temperature 0–2,
top_p dans ]0,1], seed/top_k entiers non négatifs bornés. Ces bornes ne garantissent
pas que le modèle ou la machine puissent supporter la configuration demandée.
Les budgets max_prompt_bytes, max_response_bytes et max_output_bytes sont
facultatifs et reprennent les bornes de l'adaptateur.

## Essai restreint

Avant tout essai réseau, contrôler le fichier privé sans lancer de mission :

```sh
PYTHONPATH=src python -m eidolon_core model-config-check --config /chemin/modele-prive.json
PYTHONPATH=src python -m eidolon_core --format human model-config-check --config /chemin/modele-prive.json
```

C-038 : `VALID_CONFIG` signifie seulement que le fichier respecte le schéma et
la politique locale de la CLI. Le manifeste et l'identifiant du planificateur
sont affichés pour comparer deux configurations ; la valeur de clé n'est pas
lue. `server_contacted`, `secret_value_read` et `authorizes_execution` restent
false ; `model_available` reste null. Cela ne prouve ni présence du modèle,
ni validité de la clé, ni disponibilité ou qualité du serveur. Code retour 0 si
configuration valide, 2 avec diagnostic constant sur stderr sinon. Aucun état
créé, même si --state désigne un dossier absent. Les options de mission sont
refusées ; la commande prend --config, pas l'option globale --model-config.

Puis, lorsque l'opérateur veut effectivement essayer le serveur choisi :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat-neuf \
  --timeout 90 --model-config /chemin/ollama-prive.json demo
```

L'option --timeout borne chaque appel du worker, démarrage inclus ; elle doit être
choisie avec le timeout_seconds HTTP du fichier (60 secondes dans cet exemple).
Aucun modèle n'est téléchargé ou choisi par Core. Pour reprendre une mission,
utiliser les mêmes options et le même fichier puis run m-ID. Changer l'endpoint,
le modèle, ses paramètres/budgets ou le timeout de mission modifie la configuration
et bloque la reprise. Conserver la configuration avec l'état privé.

create enregistre une mission sans appel modèle. --model-config est accepté
uniquement pour demo/create/run et --profile text ; les commandes de consultation
s'utilisent sans cette option. Les profils de recherche/service/action synthétiques
conservent leurs modèles fixes. Aucun choix de modèle n'est exposé dans le client HTTP.

## Ce qui peut réussir

Ce n'est pas du chat généraliste. Seule la mission textuelle restreinte déjà
supportée par Core est exécutable : rappel puis calcul text.stats sur les références.
Une autre demande conserve son résultat de clarification/mission non supportée.
Un plan produit par l'un des adaptateurs passe par les mêmes parseur, contrôles de permissions,
budget d'invocations et vérificateurs indépendants. Une réponse hors contrat échoue ;
une commande de service proposée ne peut pas être exécutée par ce profil.

Échec réseau/modèle : BLOCKED / MODEL_UNAVAILABLE ; plan mal formé : FAILED /
MODEL_INVALID ; plan non autorisé : BLOCKED / PREFLIGHT_REFUSED. Aucun plan de
secours n'est fabriqué. Une mission terminée ne rappelle pas le modèle à la reprise.

La qualité du modèle, sa stabilité sous charge, son contexte utile et ses performances
V100 restent à mesurer sur la VM. Ce raccordement ne constitue pas une qualification.
Voir [adaptateur](OLLAMA-ADAPTER.md) et [rapports de qualification](QUALIFICATION-REPORTS.md).

Depuis C-034 (08/10), le manifeste Ollama est versionné `ollama-chat/2` : les
missions créées avec l'ancien contrat ne reprennent pas automatiquement sous le
nouveau. Les bornes des options sont partagées par l'API Python et le fichier
CLI ; num_predict reste obligatoire dans ce dernier. Les erreurs reçues du
serveur sont résumées par un code local sans copier leur contenu privé.

## Candidat llama-server — C-036, 08/10/2026

L'adaptateur Python candidat existant peut désormais être choisi dans le même
fichier privé. Cela ne choisit pas le moteur du projet. Le contrat visé demeure
celui documenté dans [OPENAI-CHAT-ADAPTER](OPENAI-CHAT-ADAPTER.md), pas une
compatibilité générale avec n'importe quelle API chat.

```json
{
  "version": 1,
  "provider": "llama-server",
  "endpoint": "http://127.0.0.1:8080",
  "model": "ALIAS_DU_MODELE_DEJA_SERVI",
  "options": {"temperature": 0, "seed": 7, "max_tokens": 512},
  "context_tokens": 8192,
  "api_key_env": "EIDOLON_LLAMA_KEY",
  "timeout_seconds": 60
}
```

`max_tokens` est obligatoire et borné à 1–8192 dans cette CLI restreinte. Les
autres options sont celles de l'adaptateur : `temperature`, `seed`, `top_p`,
`top_k`. `num_predict` et `num_ctx` ne sont pas traduits implicitement. Les champs
facultatifs `context_tokens` et `api_key_env` appartiennent seulement au fournisseur
llama-server ; ils sont refusés dans un fichier Ollama. Le contexte déclaré est
une borne de vérification, pas une modification de la configuration du serveur.

`api_key_env` peut être omis si le serveur n'exige pas de clé. Sinon il contient
uniquement le **nom** d'une variable définie dans l'environnement du processus
Core et héritée par son worker. La valeur se configure localement ; elle n'est
pas placée dans le JSON, la ligne de commande, le manifeste ou le dépôt. Charger
la configuration et `create` ne lisent pas cette valeur et n'envoient rien.
Au moment de l'appel, valeur absente/invalide → `BLOCKED/MODEL_UNAVAILABLE`,
sans requête ni repli vers un modèle factice. Le nom de la variable fait partie
de l'empreinte de configuration ; sa valeur n'y figure jamais. Remplacer la
valeur d'une même variable ne change donc pas l'identité du planificateur.

Même commande d'essai que ci-dessus, avec le fichier llama-server choisi. Un
changement de fournisseur ou d'option exige une nouvelle mission ; une reprise
sous une configuration différente est refusée. Les erreurs 401, limites de
contexte et sortie interrompue conservent les codes propres à l'adaptateur.
Une clé reflétée dans le contenu de sortie est retenue avant persistance selon
le contrôle existant de l'adaptateur ; cela n'est pas une garantie contre toute
transformation imaginable d'un secret par un serveur malveillant.

Validation C-036 : 11 nouveaux tests, dont six parcours CLI réels avec faux
serveur. Reprise sans réémission, configuration changée, clé absente/invalide,
erreurs serveur et plans interdits vérifiés. Aucun llama.cpp ni GPU exécuté.

C-037 : les manifestes courants sont `ollama-chat/3` et
`openai-chat-llamacpp/3` après contrôle du cadrage HTTP. Les missions créées
avec /1 ou /2 ne sont pas migrées automatiquement : leur reprise sous le
nouveau contrat est bloquée. Une coupure de corps HTTP conserve l'échec, même
si les octets déjà reçus forment un objet JSON lisible.
