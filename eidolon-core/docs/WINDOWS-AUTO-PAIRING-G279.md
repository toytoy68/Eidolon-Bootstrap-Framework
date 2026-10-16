# G279 — ouvrir la conversation sans saisir la clé

Demande toytoy du 16 octobre 2026 à 23 h 01. L'authentification serveur reste active ; le PC conserve l'appairage pour éviter la saisie répétitive.

## Utilisation

1. Décompresser le nouveau paquet dans un dossier du Bureau et remplacer l'ancien EXE par celui fourni. Ne pas mélanger l'ancien EXE G270 avec ce lanceur.
2. Garder `Eidolon-tunnel.cmd` ouvert comme auparavant.
3. Lancer `Lancer-Eidolon.cmd`. La première fois uniquement, SSH demande le mot de passe du serveur afin de récupérer la clé existante. La confiance dans l'empreinte SSH doit déjà avoir été établie avec le tunnel ; le lanceur ne l'accepte pas à l'aveugle.
4. La conversation s'ouvre automatiquement. Aux lancements suivants, la clé est relue depuis son stockage chiffré Windows ; aucune copie dans le presse-papiers ni saisie dans l'application.

Les anciens scripts résident/démarrage qui lancent directement l’EXE ne passent pas par ce nouveau lanceur et restent en ouverture manuelle.

Le mot de passe SSH du tunnel reste distinct. Ce lot ne crée pas de clé SSH ni d'ouverture automatique du tunnel.

Si Windows bloque le script téléchargé, vérifier la provenance du ZIP et utiliser Propriétés → Débloquer sur ce ZIP avant extraction. Le lanceur utilise `RemoteSigned` seulement pour son processus PowerShell ; aucune politique Windows permanente n'est modifiée et les stratégies d'organisation restent prioritaires.

## Fonctionnement et limites

- Le lanceur conserve un fichier `.dpapi` sous `%LOCALAPPDATA%\Eidolon\pairing`. DPAPI le lie au compte Windows et à la machine ; le contenu inclut aussi la destination SSH, le port local et le chemin de clé. Un changement de destination nécessite un appairage distinct.
- La clé est transmise au nouveau client dans l'environnement de son seul processus, retirée par le client avant le démarrage de WebView2. Elle n'apparaît pas dans les arguments, URL, journaux ou téléchargements.
- Le client utilise le formulaire existant une fois la page chargée, uniquement à la racine de `http://127.0.0.1:<port>/`, dans la fenêtre principale. Le champ est effacé immédiatement ; la page garde sa clé en mémoire, comme après saisie manuelle. Pas de plugin, commande IPC ou accès disque accordé à la page.
- Le serveur valide toujours la clé. Une clé révoquée n'est pas réactivée par le lanceur. Le code n'écrit ni ne crée un compte sur le serveur.
- Cette protection ne protège pas contre un programme malveillant exécuté sous le même compte Windows. L'appairage fait confiance au tunnel SSH habituel et à son port local.
- Fermer la conversation ne supprime pas l'appairage du PC. L'ouverture automatique se produit une fois par chargement de la page ; elle ne se répète pas après un clic de fermeture au sein de la page.

Pour oublier uniquement l'appairage local, depuis le dossier :

```powershell
.\eidolon-open.ps1 -ForgetPairing
```

Cela ne révoque pas la clé serveur. Relancer ensuite demande un nouvel appairage SSH. Un fichier chiffré illisible est refusé, jamais utilisé comme clé en clair.

## Qualification

Trois tests JavaScript exécutés localement : origine/port/page/fenêtre principale, attente de fin de chargement, ouverture unique et effacement du champ même en cas d'erreur. La CI Windows exécute les tests Rust, le chiffrement/déchiffrement DPAPI avec une clé synthétique, le refus d'une autre destination et des entrées invalides, puis la compilation verrouillée du client. Les résultats du candidat et son empreinte sont à conserver avec le paquet. La validation du clic réel sur le PC de toytoy reste à effectuer après téléchargement.

### Candidat vérifié et livré

Workflow Windows `38967030522`, job `117195927758`, code `fd973a16176a0b5435becc33cc512dc5f597db5f` : succès. Sept tests Rust, trois tests JS d’ouverture automatique et tests DPAPI réussis ; compilation release verrouillée, vérifications résident/démarrage existantes réussies. Aucun test n'a utilisé la clé personnelle de toytoy.

EXE SHA-256 : `bf99f0c75f9e6bedd28fd6db279de9e1f10b9c120dfa6d5db307b7136af0a372`. ZIP utilisateur `eidolon-pc-g279.zip` : `163bd508b9b8f149e78f69860270425fefbdaf03c211e189d1078f9fe930e85a`. Archive CI téléchargée et empreinte contrôlée ; EXE comparé au manifeste produit sur Windows ; intégrité ZIP vérifiée. Les scripts PS de la CI conservent leurs fins de ligne Windows, avec contenu normalisé identique au dépôt.

Le serveur Core a été synchronisé sans redémarrage : aucune modification de son authentification. Reste à valider sur le PC réel : premier appairage SSH, ouverture automatique et relance depuis l'appairage chiffré.
