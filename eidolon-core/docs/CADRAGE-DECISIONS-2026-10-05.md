# Cadrage consolidé — assistant résident et accès réseau

Date : 05/10/2026. Ce document confronte le brainstorming au code présent et
consigne les décisions de cadrage ; il ne décrit pas des capacités toutes livrées.

## Sources et bases examinées

- [Cadrage fourni par toytoy](cadrage/EIDOLON-CORE-CADRAGE-WORK-2026-10-05.md),
  conservé sans modification. Son origine est le brainstorming avec GPT Chat,
  pas un audit du dépôt ni une qualification des modèles mentionnés.
- Ajout explicite de toytoy à 10 h 40 (Europe/Paris) : « besoin absolu d'un accès
  à Internet et aux autres machines comme memory-engine ou mon NAS ».
- Ajout explicite de toytoy à 10 h 44 (Europe/Paris) : accès aux documents,
  images, vidéos et autres fichiers de sa session Windows.
- Core : `feat/eidolon-core-v0.1`, `f34391687f14cd1b1734c25eef6f47dad5fd91f5`.
  AGENTS.md, standard de présentation, runtime, outils et TODO relus.
- Mémoire : tête distante `d34a36544b2c0740c74b88b043de4c947b2482c0`,
  `refactor/architecture-v1`, consultée sans modification dans ce lot.
  Depuis `7d99ded`, deux lots harmonisent la présentation ; `d34a365` refuse
  les `content.parts` qui ne sont pas des listes avant publication de l'import.
  Diff du correctif lu ; ses tests n'ont pas été réexécutés ici.

## Décisions de cadrage

**C-D01 — Assistant résident.** La cible est un assistant/chatbot/superviseur,
hébergé sur le serveur. Le client Windows disposera de l'icône E bleue, du chat,
de l'état des missions et de notifications ; autostart configurable. Conversation,
présence utilisateur, connexion du client et mission restent des notions séparées.
L'interface Desktop finale n'est pas un prérequis pour construire les contrats.

**C-D02 — Internet et réseau local sont des exigences du socle.** Core devra
pouvoir consulter le Web et accéder aux services/machines autorisés. « Local AI »
signifie ici exécution et maîtrise locales, pas obligation de rester hors ligne.
La perte d'Internet ne devra pas empêcher une mission locale qui n'en dépend pas.
La lecture mémoire distante et l'accès au NAS doivent être prévus dès les
premiers contrats de connecteurs, pas ajoutés après coup à un shell générique.
L'accès aux fichiers de la session Windows fait partie de ce même socle : Core
sur le serveur doit pouvoir travailler avec les contenus du PC utilisateur.

**C-D03 — Connectivité et droits d'action sont séparés.** Chaque accès associe
une identité de cible, une capacité, des paramètres validés, une identité cliente
et un périmètre autorisé. L'exigence réseau ne crée pas une permission globale
de modifier les machines, publier des données ou exécuter du code téléchargé.
Les tests préparatoires restent synthétiques/isolés ; aucune connexion au NAS,
à une VM ou capture de périphérique n'est déclenchée par ce document.

**C-D04 — Présence et identité ne valent pas authentification.** Webcam et voix
personnalisent l'accueil ; une action sensible doit dépendre d'une identité et
d'une autorisation vérifiées. Événements de présence locaux avant toute Vision
distante ; multi-utilisateur, invité et mode silencieux explicitement prévus.

**C-D05 — Développement progressif.** Un agent et une exécution séquentielle
restent suffisants pour les prochains cas A–D. Ollama est l'adaptateur de modèle
envisagé en premier, pas un choix définitif des poids. Les tags/mesures rapportés
dans le brainstorming ne sont pas qualifiés. Desktop, voix, Vision, Scheduler
complet et robot réel restent des tranches ultérieures.

**C-D06 — Connecteur de fichiers Windows indépendant du Desktop final.** Prévoir
un agent léger dans le contexte de la session utilisateur, avec ses droits,
qui expose des capacités de fichiers autorisées à Core. Pas de privilège
administrateur implicite ni de partage global du disque. L'interface Desktop
pourra utiliser ce même connecteur ; sa réalisation finale ne doit pas retarder
les premières missions sur documents. L'implémentation/protocole restent à faire.

**C-D07 — `SUCCEEDED` signifie « mission atteinte ».** Décision de toytoy,
05/10/2026 vers 14 h 10 (Europe/Paris), en réponse à la question Q1 de
[C-BRAIN-C007](../collaboration/BRAINSTORMING.md#c-brain-c007--forme-minimale-du-contrat-de-mission-c-001)
transmise par Claude : « Oui pour Q1, garde SUCCEEDED pour mission atteinte ».
Une mission dont l'exécution s'est terminée sans atteindre son objectif (issue
non atteinte, partielle ou sans preuve) ne finit jamais en `SUCCEEDED` ; elle
finit dans un état distinct qui porte son issue. Restent à fixer dans C-001 :
le nom de cet état (`CONCLUDED` proposé), son code de retour CLI (5 proposé)
et le traitement d'une demande de clarification. Cette décision ne tranche pas
Q2 (refus au précontrôle) ni Q3 (missions sans type déjà en base).

## Capacités réseau à livrer

| Capacité | Premier usage attendu | Contrat et vérification |
| --- | --- | --- |
| Internet : recherche et lecture Web | Documentation, recherche technique, informations actualisées | URL finale et source, date de consultation, contenu borné, refus/erreurs explicites ; aucune vérité déduite du seul HTTP 200 |
| Memory Engine distant | Rappel avec références et réserves | Transport vers une API réellement disponible/à construire explicitement ; préserver readiness, révisions, provenance et statuts |
| NAS : fichiers | Lister, lire et rechercher dans des emplacements autorisés | Périmètre de partage/répertoire, droits de lecture, taille et empreinte/version du fichier ; écriture/suppression séparées |
| Session Windows : fichiers personnels | Rechercher, lire et analyser documents, images, vidéos et audio | Connecteur local lié à la session, dossiers autorisés, version du fichier et provenance ; restitution de données bornée à la mission |
| NAS / serveurs : diagnostic | État de services, stockage, alertes et métriques | Cible enregistrée, origine, horodatage, fraîcheur et limites des observations |
| Administration distante | Redémarrer un service ou lancer une action déléguée | Autorisation liée à cible/action/paramètres, reçu observable, vérification après action et réconciliation si effet inconnu |

Les protocoles (HTTP(S), API spécifique, SSH, SMB/NFS selon usage) ne sont pas
interchangeables et restent à choisir après inspection des services effectivement
exposés. Ne pas inventer d'endpoint API, de port ou de droit d'accès. Le serveur
MCP de collaboration n'est pas présumé fournir le rappel mémoire ou l'administration
du NAS. Aucun secret, token ou mot de passe ne doit entrer dans Git ou un prompt.

Exigences communes à ces connecteurs :

- Catalogue de cibles stables, capacités autorisées et références de secrets
  fournies à l'exécution ; configuration conservée hors contrôle du modèle.
- Séparation du périmètre Internet public et du LAN. Une URL issue d'une page
  ou d'un modèle ne doit pas donner accès à un service interne arbitraire.
- Validation des redirections et des destinations DNS, vérification TLS,
  authentification selon le service ; aucun contournement silencieux de certificat.
- Paramètres/chemins bornés, délais, limites de volume et concurrence ; pas de
  commande shell libre ni d'accès universel à tout un partage NAS.
- Provenance et fraîcheur des réponses, état indisponible/dégradé distinct d'un
  succès. Une ancienne métrique du NAS n'est pas son état actuel.
- Données minimales dans les requêtes sortantes : une recherche Web peut déjà
  transmettre du contenu privé. Lecture seule ne signifie pas absence de tout
  effet externe (requête, journal serveur, coût). Permissions d'egress explicites.
- Contenus Web/NAS traités comme données non fiables, jamais comme instructions
  pour étendre les permissions. Téléchargement, analyse et exécution sont séparés.

## Écarts avec le jalon déjà livré

| Besoin | État constaté dans Core | Suite |
| --- | --- | --- |
| Missions, journal, reprise prudente | Livré et testé sur données synthétiques | Conserver ces garanties lors des extensions |
| Rappel mémoire | Adaptateur Python local réel, pas un client réseau | Choisir/exposer le transport distant sans copier le moteur |
| Internet / NAS / autres machines | Aucun connecteur réseau général | Priorité dans la prochaine tranche ; critères de refus et preuve dès le contrat |
| Fichiers de la session Windows | Aucun connecteur PC ni accès à ses documents/médias | Contrat commun avec les ressources NAS, agent local sans élévation implicite |
| Modèle Ollama | Interface interchangeable, simulateur uniquement | Adaptateur configurable après critères de mission et contrats de transport |
| A : synthèse mémoire | Rappel avec références ; pas de synthèse générale | Restitution sourcée bornée et absence de contexte explicite |
| B : diagnostic de service | Outil démonstrateur de statistiques textuelles | Premier connecteur de diagnostic, cible synthétique puis cible réelle désignée |
| C : redémarrage approuvé | Ni outil de redémarrage ni file d'approbation métier | Simuler attente/accord/refus ; action réelle après contrat et cible autorisée |
| D : échec partiel et reprise | Preuves/étapes conservées, reprise des appels incertains ; FAILED terminal | Retry explicite de l'étape admissible, conservation des étapes vérifiées |
| Clients distants / reconnexion | CLI et événements SQLite locaux | Contrat API, authentification et curseur de reprise d'événements |
| Desktop / présence / voix / endpoints | Vision produit uniquement | Extensions progressives, pas de serveur/interface déjà prétendus disponibles |

Le terme « première tranche v0.1 » du brainstorming est donc plus large que
la démonstration v0.1 déjà livrée. Il fixe la cible suivante ; il ne requalifie
pas les 40 tests existants en validation de A–D ou d'un accès réseau réel.

## Fichiers Windows et médias : périmètre attendu

Les dossiers Documents, Images, Vidéos, Bureau ou d'autres emplacements choisis
par l'utilisateur sont des exemples de périmètres à configurer, pas des chemins
codés en dur. Respecter les droits effectifs de la session, les dossiers déplacés
et le cas des fichiers uniquement disponibles via un fournisseur de stockage.

| Ressource | Capacités cibles | Preuves et limites |
| --- | --- | --- |
| Documents | Recherche par nom/métadonnées puis contenu, lecture/extraction et synthèse | Fichier identifié/versionné, pages ou passages référencés ; formats non pris en charge signalés |
| Images | Métadonnées, aperçu, OCR ou analyse visuelle selon capacité disponible | Référence à l'image, transformation éventuelle tracée, incertitude de l'interprétation conservée |
| Vidéos | Métadonnées, segments/images sélectionnés, transcription/analyse progressive | Références temporelles, limites de durée/volume, pas de vidéo entière envoyée systématiquement au modèle |
| Audio | Métadonnées, lecture/extraction et transcription autorisées | Références temporelles, modèle/capacité identifié, distinction contenu du fichier et capture micro |

Le premier contrat de ressources doit séparer `list`, `stat`, `search` et `read`
des transformations (`extract_text`, OCR, transcodage) et des mutations
(`write`, `rename`, `move`, `delete`). Accéder à une image ne signifie pas que
le modèle courant sait l'analyser ; le routeur doit reconnaître ses capacités
et signaler l'absence de Vision/OCR/transcription si nécessaire.

Points de conception et scénarios à couvrir :

- Identité du PC, de la session et de la ressource, emplacements autorisés et
  références stables ; aucun nom de profil Windows supposé dans le code.
- Pas de sortie de périmètre par traversée de chemin, lien/jonction ou changement
  de fichier entre autorisation et lecture. Fichier modifié, verrouillé ou supprimé
  pendant l'opération : résultat explicite, jamais analyse silencieuse d'une autre version.
- Recherche/index local possible, ingestion mémoire distincte. La disponibilité
  des fichiers ne demande pas d'importer automatiquement l'intégralité du PC
  ou du NAS dans Memory Engine, ni de transmettre son contenu vers Internet.
- Extraction et sélection locales lorsque possible ; transférer vers Core
  les données nécessaires, avec quotas, délais et annulation. Conserver la
  distinction entre original, aperçu, transcription et résumé généré.
- PC éteint/hors ligne, session indisponible/verrouillée ou connecteur arrêté :
  appliquer la politique de session, afficher le dernier état daté et le blocage
  éventuel. Ne pas exposer les documents d'un utilisateur à un contexte invité.
- Pour une future modification : permission spécifique, version attendue,
  vérification de l'artefact produit et stratégie de reprise ; aucune permission
  d'écriture/suppression déduite du seul besoin de lecture.

Premiers exemples de missions : retrouver un document de projet et le résumer
avec ses références ; lire les métadonnées d'une image puis l'analyser si un
modèle Vision est disponible ; retrouver un passage d'une vidéo à partir de
sa transcription. Commencer avec fichiers synthétiques et erreurs simulées,
puis une recette Windows sur des dossiers explicitement sélectionnés.

## Deux arbitrages nécessaires avant implémentation

1. **Expiration d'une autorisation ≠ expiration d'une proposition.** Une
   proposition sans décision reste en attente conformément à J-02. Un justificatif
   d'autorisation peut devenir inutilisable si sa durée, sa cible, ses paramètres
   ou la politique changent ; il faut redemander une décision sur l'action
   concrète, sans inventer un abandon ou une acceptation par silence.
2. **FAILED ne signifie pas oubli.** Le code actuel interdit la relance d'une
   mission FAILED. Le besoin de retry de D implique un nouveau parcours explicite,
   testé et journalisé. Ne pas retirer simplement FAILED des états terminaux :
   les étapes déjà vérifiées et les effets incertains doivent rester protégés.

## Ordre de réalisation proposé et critères de sortie

La [TODO Core](../TODO.md) porte les lots C-001 à C-008 : contrat de mission et
cible, connecteurs de lecture Internet/LAN/Windows, rappel distant, diagnostic, approbation
et reprise partielle, puis contrôleur réel et clients distants. La définition
des contrats réseau commence dès C-001 ; elle ne dépend pas du Desktop final.

Première démonstration cible sans VM : répondre avec références à A, diagnostiquer
une cible simulée pour B, attendre un accord précis pour C puis vérifier l'état
simulé, provoquer l'échec de Y dans D et reprendre sans rejouer X. Ajouter cible
ambiguë, réseau absent, authentification refusée, réponse périmée/mal formée et
interruption après envoi avant reçu. Aucun succès annoncé sans preuve adaptée.

Avant l'activation réelle : désigner la machine et son service, vérifier le
protocole et l'identité, configurer les permissions et secrets hors Git, puis
exécuter une recette limitée. La VM, le NAS et Internet réel restent des niveaux
de validation distincts des doubles de test et serveurs locaux de laboratoire.

## Portée du présent lot

Cadrage source archivé, besoin réseau ajouté, écarts/contradictions explicités,
feuille de route actualisée. Aucun code d'accès réseau, API distante, modèle réel,
nouvelle autorisation d'exécution ou outil de redémarrage livré dans ce lot.
Contrôles : source copiée à l'identique, liens et diff documentaire vérifiés.
Les précédentes preuves logicielles restent datées de leurs propres exécutions.

## Complément matériel — instruction toytoy du 05/10 à 14 h 23, Europe/Paris

Matériel prévu : **2 × NVIDIA V100 32 Go avec NVLink**. Réviser le recours à
Ollama en fonction de cette cible. Ceci fixe un objectif de qualification, pas
une machine déjà installée ou testée, ni un modèle contrôleur retenu. Les références
exactes des cartes, l'interconnexion et la répartition hôte/VM restent à relever.
[Note d'inférence et tâche Claude révisée](INFERENCE-2XV100-2026-10-05.md).

Précision toytoy du même jour à 14 h 28 : **deux modules SXM2 montés sur une carte
adaptatrice PCIe, lien NVLink sur le PCB**. Le format est donc renseigné ; restent
la référence/révision de l'adaptateur et la topologie constatée lors de la recette.
