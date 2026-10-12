# Dashboard Core : déploiement VM voix, vision et monitoring — 12 octobre 2026

**Actif sur Core /192.168.1.101** : Core API/page 8767, eidolon-comm 8766 et eidolon-monitor 8768, tous en boucle locale et activés au démarrage. La page utilise les relais de même origine ; un seul tunnel PC sur 8767 suffit. DARME et son collecteur SSH restent actifs sur Core et Memory.

## Ce qui a été intégré et corrigé

Livraisons C147/C148 de Claude intégrées par fusion à deux parents, sans recopier sa branche sur les nouveaux fichiers DARME. Code final à 486454828661b82b9bd2fcb7e6616683b68991f1 avant ajout de ce bilan.

- Relais voix et monitoring, panneau « État des machines », boutons voix/caméra éteints au chargement.
- Consigne vision clarifiée : present désigne une personne, vrai si et seulement si people_count > 0. Gemma4 comptait zéro personne sur le cercle mais donnait present=true ; le cas rejoué devient false/0. La description reste imparfaite (bandes/fond issus du traitement de l'image), observation non vérifiée.
- Sous systemd ProtectHome=read-only, Store() tentait une initialisation SQL et faisait échouer le service. Nouveau comm_credentials.py : identité existante et clés lues en mode=ro, aucune migration/écriture, révocation observée immédiatement. Les deux adaptateurs utilisent cette vue.
- Umask global dans les fonctions de collecte : déplacé aux points d'entrée CLI ; test de collecte vérifie que son appel ne change pas le umask. Correction déployée sur Core/Memory.
- Double validation UI : deux calculs de digest asynchrones pouvaient finir dans un ordre différent. Réservation avant digest pour que le premier appel garde la proposition, sans bloquer une nouvelle session/proposition ; une seule soumission.
- Texte du badge corrigé en « Surveillance de sécurité incomplète » : il ne nie plus le collecteur SSH réellement installé.
- Fermeture de HTTPError en vision reprise de Claude. La suite contient encore une exception RemoteDisconnected dans un thread de test HTTP ; le résultat unittest global OK ne suffit pas à certifier ce scénario réseau.

Un commit intermédiaire de consigne n'avait aucun diff après un échec du script d'édition ; la correction effective est 62e4fda. Aucun service n'a été déclaré validé sur ce commit vide. Les erreurs d'installation initiales sont conservées dans les logs ; la protection du stockage n'a pas été retirée pour les contourner.

## Validation

| Vérification | Résultat réellement observé |
|---|---|
| Suite Core finale, cryptography et intégrations Memory opt-in incluses | **1 591 tests, OK, aucun ignoré**, 195,734 s |
| Node page complète après correctif double validation | 130 réussis, 26 ignorés, zéro échec (156 au total) |
| Tests du texte/monitoring final | 9 réussis |
| Prévol installé, ports/configs/socket | 22/22 |
| Chromium sur page réelle et vrai backend Core/DARME, 1280 et 360 pixels | 12/12, aucun débordement/erreur JS |
| Authentification réelle par relais Core | clé appairée acceptée ; absence, jeton de lecture, autre origine et clé révoquée refusés |
| Moteurs réels | Piper, Whisper small et Gemma4 vision appelés avec entrées synthétiques licites |

La première recette Node avait un échec C069 (ordre des validations inversé) ; corrigé, tests rejoués et app.js recompilé. Les huit tests crypto précédemment ignorés sont maintenant exécutés, après installation de la dépendance optionnelle dans le venv de tests. La suite Memory 2 018 du lot précédent n'est pas répétée ici ; les intégrations Core/Memory le sont.

Captures de **la VM réelle**, après rafraîchissement du bundle servi :
[1280 pixels](dashboard-real-monitor-1280.png), [360 pixels](dashboard-real-monitor-360.png).
L'API épingle ses assets au démarrage : une mise à jour de fichier seule ne suffisait pas, Core API a été redémarré avant la dernière capture. Le premier contrôle immédiat après restart a rencontré un refus temporaire de connexion ; le contrôle de disponibilité et la recette navigateur ont ensuite réussi.

Les clés des clients de recette n'ont jamais été imprimées/persistées dans les captures ou envoyées en argument de processus navigateur ; clients révoqués après tests. Les conversations de test vides et reçus restent des traces d'audit. Aucun micro/caméra physique utilisé ; la capture reste désactivée.

## Moteurs et mesures

Whisper small CTranslate2 (Systran/faster-whisper-small, révision dans download-manifest.json), CPU int8, 2 threads, beam_size=1. Le CPU QEMU expose SSE4.1 mais pas AVX/AVX2 : CTranslate2 a réellement annoncé int8/float32 compatibles et transcrit les échantillons. Aucun changement de configuration Proxmox.

Piper 1.8.0, voix fr_FR-siwis-medium 22 050 Hz, vitesse 0,9. faster-whisper 1.2.1, CTranslate2 4.8.2, ONNX Runtime 1.31.0. Piper annonce GPL-3.0-or-later ; faster-whisper/modèle MIT ; fiche SIWIS attribue le dataset à CC-BY 4.0. Poids et venv hors Git. La préférence subjective de voix reste à écouter sur PC.

| Appel | Mesure |
|---|---:|
| Piper premier morceau prêt, direct backend | 1,17 à 1,22 s |
| Whisper échantillon synthétique 5 s, premier chargement | 4,33 s |
| Whisper échantillon synthétique 20 s, chaud | 3,98 s |
| Via relais réel : premier morceau TTS serveur | 1,84 s |
| Via relais réel : transcription 5 s | 4,57 s |
| Via relais réel : vision cercle, Gemma4 12B | 4,98 s |

Le « premier morceau prêt » n'est pas le délai du premier son audible sur Windows. Les entrées 5/20 s contiennent une voix synthétique puis du silence, pas 20 s de parole continue ; les temps ne donnent pas un taux de précision humaine. Une recette initiale ne concaténait que le chunk 0 : corrigée avant les relevés ci-dessus. Le long échantillon transcrit toytoy comme « toi-toi » et Eidolon comme « et de longs » ; nombres 24/110 retrouvés. Nouveau lot G164 pour lexique et bruit.

Gemma4 12B déjà installé sur VM101 /192.168.1.135, réutilisé par le tunnel local 11435 ; pas de nouveau modèle de vision, pas d'identité faciale. La contention dialogue/vision n'est pas encore qualifiée. Service voix environ 1,18 Go après chargement STT, limite 3 Go ; adaptateur monitor environ 14 Mo. Services sur compte toytoy pour respecter les fichiers appairés owner-only, NoNewPrivileges/capacités vides et stockage en lecture seule ; ce n'est pas un nouveau compte dédié sans droits sudo hors service.

## Couverture machine

Dashboard : métriques **Core seulement**, CPU/charge/RAM/swap/filesystem du journal, fraîcheur et badge partiel. Memory a ses sondes DARME et SSH actives mais n'est pas encore reliée à la page ; VM101 GPU y est « non surveillé », jamais avec des chiffres inventés.

Lecture administrative réelle de VM101 réussie : Tesla V100-SXM2-16GB, 16 384 Mio, 9 123 Mio utilisés, 44 °C, utilisation 0 %, puissance 41,13 W au moment du contrôle ; disque 97 Gio libres. Ce relevé ponctuel ne constitue pas un monitoring permanent. Proxmox physique non sondé.

## Installation, accès et suite

Un seul tunnel du PC :
```sh
ssh -N -L 127.0.0.1:8767:127.0.0.1:8767 toytoy@192.168.1.101
```
Puis http://127.0.0.1:8767/ et clé client appairée. Aucun accès public ajouté à 8766/8768, aucun assouplissement CSP.

Pré-installations sauvegardées sous /var/backups/eidolon/core-communication-predeploy-*.tar.gz et dashboard-preinstall-*.tar.gz. Unités/configs privées restent hors Git. Reprise/rollback décrit par dashboard_install.py ; conserver l'état et les clés, désactiver seulement les nouveaux services/flags si nécessaire.

C148 Q2 : Memory reste explicitement hors de la page jusqu'au canal réellement testé. Q3 umask corrigé et reproduit dans la suite complète. Nouveaux lots [G164–G169](../../../DASHBOARD-SUITE-CLAUDE-G164-G169.md) : lexique STT, recette PC, Memory, readiness, outils Runtime explicites, GPU/contention. Code, scripts et relais installés ; **Windows/micro/caméra réels restent à essayer le week-end**.

Sources primaires consultées : [support CPU CTranslate2](https://opennmt.net/CTranslate2/hardware_support.html), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [modèle small](https://huggingface.co/Systran/faster-whisper-small), [Piper](https://github.com/OHF-Voice/piper1-gpl), [fiche Siwis](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/siwis/medium/MODEL_CARD), [Playwright](https://playwright.dev/docs/browsers).
