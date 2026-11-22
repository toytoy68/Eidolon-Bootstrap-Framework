# Suivi Eidolon — 22 novembre 2026

**Eidolon Core Technologies (ECT)**  
Local AI • Modular • Reliable • Reproducible

Cette campagne reprend quatre travaux : séparation de l'exécuteur Darme, maintenance Memory admissible, robustesse des petits LLM et nouvel essai Eva après le rejet d'E5. Les modifications Core partent du commit `860a33e2ccbc63197424b8b21876d1027c565440`, dans une branche dédiée. Les services et modèles de production ne sont pas remplacés par ces prototypes.

## Darme : une frontière entre deux comptes Linux

Le nouveau registre opt-in `remote_registry(socket_path, service_uid)` raccorde le Runtime existant à un service Unix distinct. Il couvre **l'unique outil pur actuellement enregistré, `text.stats`**. Aucun shell, URL, chemin fourni par le modèle, accès GPU ou commande moteur n'est accepté.

- Core et le service vérifient mutuellement le compte du pair avec `SO_PEERCRED`. Les identités déclarées dans le JSON n'accordent aucun droit.
- Le service revalide les champs, le type d'outil et le budget UTF-8, puis appelle le worker bubblewrap existant. Le client recalcule le résultat attendu.
- Les trames sont bornées et les champs JSON dupliqués sont refusés. Une échéance totale empêche une requête au compte-gouttes de prolonger indéfiniment la lecture.
- Aucun repli local ni nouvelle tentative automatique. Le Runtime conserve ses reçus et classe une interruption incertaine `REVIEW_REQUIRED / UNKNOWN_EFFECT`.
- Dans `Memory-engine-tests`, Core utilise l'UID 999 et le service l'UID 995. Le code appartient à root ; Core ne peut modifier le répertoire de socket ni lire l'état privé du service.
- Le service testé a zéro capacité, `NoNewPrivileges`, un réseau privé, un système de fichiers protégé, 256 Mio de limite mémoire, 32 tâches et 64 descripteurs. `AF_NETLINK` est nécessaire à bubblewrap pour initialiser son réseau isolé ; les sockets IP ne sont pas autorisées par la restriction des familles d'adresses.

L'exemple d'unité est un modèle de déploiement à configurer avec des comptes et UID locaux explicites. Le compte Core doit appartenir au groupe autorisé à joindre le socket, sans droit d'écriture sur son répertoire. L'installation, les configurations et les parents de chemin doivent rester contrôlés par l'opérateur. Le Runtime sélectionne explicitement ce registre ; son registre par défaut reste inchangé.

La qualification réelle vérifie le résultat et le reçu, le redémarrage du Runtime, l'interruption après retour, les demandes interdites, les droits des fichiers et l'absence de repli après arrêt du service. Un autre UID joignant le socket est également refusé. Cela ne qualifie pas encore des outils avec effets externes, un contrôle universel de tous les processus, ni un déploiement Darme en production.

## Maintenance Memory

Le timer de production est actif et son dernier passage a terminé avec succès en état `DEFERRED / OUTSIDE_WINDOW`. La VM de production a démarré à 08:04, après la plage 04:00–08:00 Europe/Paris : il ne s'agit pas d'un échec de maintenance. Aucun passage nocturne effectif n'est revendiqué.

L'exercice isolé utilise le vrai Qdrant et le vrai modèle `qwen3-embedding:0.6b`, avec une heure admissible injectée dans l'API de test, sans modifier l'horloge système. Douze fixtures de 1 200 caractères, explicitement extraites de documents synthétiques, produisent douze points. Le second passage est `UNCHANGED`, sans réembedding. Les cas hors plage, activité récente et charge élevée sont différés. La reprise d'activité interrompt la synchronisation et conserve le même état d'index. Les fichiers canoniques des fixtures restent identiques.

Deux limites ont été constatées et conservées dans les traces : les documents synthétiques complets d'environ 16 000 caractères dépassent le contexte de 2 048 tokens ; un essai de contexte à 8 192 tokens dépasse le délai d'inférence de 30 secondes. Leur traitement intégral n'est donc pas qualifié. Le résultat positif concerne les passages bornés, pas une validation de documents longs ou de qualité de recherche.

La VM de test possédait encore un tunnel vers l'ancien Core `192.168.1.101`. Son adresse a été corrigée vers X399 avec sa clé publique hôte vérifiée, mais l'accès SSH direct depuis cette VM reste bloqué. L'exercice a utilisé un tunnel inverse temporaire, limité au loopback et arrêté ensuite. Ce point de connectivité reste à résoudre pour une autonomie complète de la VM de test. Memory de production n'a pas été modifié.

## LLM : robustesse des intentions et du diagnostic

Quatre modèles, 36 cas chacun, soit **144 réponses**. Les cas connus ont été transformés en ajoutant des journaux plus longs et, en alternance, une instruction malveillante dans les données. Le schéma JSON contraint la forme, pas le choix correct de la réponse. Trente étiquettes ont été revérifiées par règles déterministes ; six étiquettes Darme inchangées proviennent du banc antérieur. Ce test de robustesse n'est pas une nouvelle validation aveugle générale.

| Modèle | Intention robot | Triage Darme | Diagnostic système |
|---|---:|---:|---:|
| LFM3 1.7B Q4_K_M | 9/12 | 9/12 | 7/12 |
| LFM2.5 1.2B Q4_K_M | 4/12 | 9/12 | 2/12 |
| Phi-4-mini Q4_K_M | 6/12 | 3/12 | 7/12 |
| Eva-source 4B Q4_K_M | 8/12 | 6/12 | 7/12 |

Aucun des quatre ne passe tous les cas critiques. Exemple conservé : Eva-source propose `AVANCER` alors que le cas exige `ATTENDRE`. Ils peuvent produire des suggestions, mais les décisions exécutables doivent rester vérifiées par les règles déterministes et la politique indépendante.

La classification d'usage reste donc : Eva-source comme référence de dialogue ; petits modèles comme candidats pour intentions ou assistance système sous contrôle ; modèles de raisonnement plus grands comme planificateurs à budget distinct ; Darme comme autorité déterministe indépendante, avec LLM auxiliaire seulement. Ce banc ne requalifie ni les modèles de vision, ni les embeddings, ni le STT/TTS. Eva-source Q4_K_M est distinct du parent cycle 5 NF4 + LoRA utilisé pour l'entraînement.

Les poids et le binaire llama.cpp sont identifiés par SHA-256 dans `roles-identities.json`. Les réponses brutes sont conservées. Les relevés secteur de ce court banc incluent les autres travaux CPU de la session ; ils ne permettent pas un classement énergétique isolé des modèles. WALL-E est resté injoignable après une tentative de réveil : aucun résultat N6000 n'est déduit des mesures V100.

## Eva E6 : protocole rééquilibré

Le parent reste le cycle 5, adapter SHA-256 `c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30`. E5 avait amélioré X1 et X2 tout en régressant sur X3. E6 remplace la pondération 1:3:1 par 1:1:1, à budget total constant : 60 109 tokens supervisés par passage, dont 28 487 horaires et 31 622 autres. Le replay, le taux d'apprentissage `1e-6`, le parent et les critères de rejet restent identiques.

Les exemples étant indivisibles, le premier passage contient effectivement 7 635 tokens X1, 7 230 X2 et 7 186 X3 : un rééquilibrage proche de l'objectif, pas une égalité exacte. Les valeurs d'entraînement sont disjointes des sondes réservées du protocole. Les évaluations historiques restent des outils de développement ; le lot final réservé n'est pas ouvert.

Le banc contrôle l'intégrité des poids, les copies mémoire, le boot courant, les températures GPU/HBM/CPU, les ECC, les erreurs noyau et la fraîcheur du compteur secteur. Les deux V100 sont limitées à 200 W. Une régression au checkpoint 102 arrête le passage 204. Aucune promotion de modèle n'est automatique.

Deux lancements préparatoires ont été archivés : choix initial d'un interpréteur sans télémétrie, puis absence d'un fichier de consignes et chemins de références historiques à adapter au nouveau dossier. Ces corrections précèdent l'entraînement du candidat ; les références historiques sont désormais incluses dans le manifeste d'intégrité. Les tests matériels du même boot restent valides et les contrôles d'intégrité sont répétés à chaque phase.

**Résultat : E6 rejeté au checkpoint 102 ; le passage 204 n’a pas été lancé.**

| Évaluation | Parent cycle 5 | E6, 102 mises à jour |
|---|---:|---:|
| X1 : HH:MM vers minutes | 47/96 | 67/96 |
| X2 : jours et reste en minutes | 80/96 | 82/96 |
| X3 : minutes vers HH:MM | 47/96 | 44/96 |
| Questions horaires complètes | 86/320 | 84/320 |
| Jour 0 | 55/64 | 54/64 |
| Acquis de référence | 26/32 | 25/32 |

La stabilité X3 échoue : la tolérance était au maximum une perte, contre trois observées. Le rééquilibrage seul ne corrige donc pas la régression dans cet essai. Le parent cycle 5 reste la référence d’entraînement ; aucun candidat n’est promu.

Sur les 52 anciens cas de rôles, le diagnostic NF4 conserve les mêmes scores stricts : robot 10/12, Darme 8/12, système 5/12, raisonnement 1/12. Ce jeu et sa recette diffèrent du banc GGUF de robustesse décrit plus haut. La relecture des huit sondes qualitatives relève une nouvelle erreur : le candidat parle de 16 processeurs logiques pour un CPU de 16 cœurs / 32 threads. Cette relecture est réalisée par Codex, pas par un évaluateur humain ; elle ne vaut pas certification générale du dialogue.

Le prochain protocole devra examiner l’interférence entre les familles et la composition des calculs, plutôt que répéter uniquement le rééquilibrage. La sonde sur les processeurs logiques doit rejoindre les contrôles de développement, avec un nouveau lot indépendant pour toute future validation. Aucun nouvel essai n’est lancé automatiquement.

Campagne principale : 18 min 16 s, dont 150 s pour les 102 mises à jour. Les intervalles mesurés consomment **118,31 Wh au secteur pour la X399 entière**, hors précontrôles CPU, lancements échoués et intervalles non échantillonnés. Maxima observés : GPU 40 °C, HBM 46 °C, CPU 43,75 °C ; aucune nouvelle erreur ECC. Les deux GPU ont retrouvé 1 Mio de VRAM utilisée chacun en fin de campagne. Adapter candidat conservé : `a1df6beadbc385af56d79a9ee7c3052078d134dce55b16b69cd4c85dc77e3604`.


## Vérifications et état final

La suite complète du code final passe : **2 501 tests et 1 349 sous-tests**, avec 30 tests conditionnels ignorés dans cet environnement. Parmi ces 30, les six tests de comptes distincts passent dans la VM et les deux tests de propriétaires passent séparément sous root. Il reste donc 22 tests optionnels non exécutés (dépendances ou modèles audio/vision/médias absents). Les 31 tests ciblés du transport et du sandbox passent aussi ; ils recoupent la suite complète et ne sont pas additionnés au total. Deux fixtures existantes ont été corrigées pour créer explicitement leurs configurations privées en mode 0600, indépendamment du umask du shell.

Les données brutes, journaux, modèles et checkpoints restent sous `/srv/eidolon/ssd/work/followup-20261122`. Le dépôt contient les conclusions, résultats structurés, protocoles et empreintes nécessaires pour les retrouver et les contrôler. Les erreurs intermédiaires sont conservées, sans être comptées comme réussites.

La VM `Memory-engine-tests`, initialement arrêtée, est de nouveau arrêtée. Les services temporaires et le tunnel inverse sont arrêtés. X399 et la VM Memory de production restent en ligne, sans unité systemd en échec lors du contrôle final. Le pont Git MCP retourne `ready=true`, au commit `a6a882bb4c0b1b1730a37d15cdc80dffae35e994`. Les 205 points de production ont été revérifiés ; aucun modèle ou service de production n’a été remplacé par le prototype.

Restent ouverts : déploiement et extension de Darme aux outils avec effets, connectivité autonome du tunnel de la VM de test, qualification des documents longs, mesures sur N6000/WALL-E accessible, et toute amélioration d'Eva qui ne satisferait pas ses critères. Ces dépendances ne sont pas marquées terminées par la clôture de cette campagne.
