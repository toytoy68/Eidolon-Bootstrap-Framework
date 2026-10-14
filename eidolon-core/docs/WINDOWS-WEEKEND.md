# Essai du dashboard sur le PC Windows — guide du week-end

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Lot G165.

À faire par toytoy. La VM Core est prête : déploiement et preuves de Codex
dans [dashboard-vm/REPORT.md](validation/2026-10-12/dashboard-vm/REPORT.md).

Cet essai qualifie ce qui **n'a jamais été testé** :
- Windows ;
- Edge ou Chrome sur le PC ;
- WebView2 ;
- les vrais micro, caméra et haut-parleurs.

Les tests Chromium sur la VM ne remplacent pas cet essai.

Durée prévue : environ une heure. Rien n'est installé sur le PC pour l'essai
dans le navigateur.

## 0. Avant de commencer

| Il faut | Comment vérifier |
| --- | --- |
| Windows 10 ou 11, client OpenSSH | `ssh -V` dans PowerShell |
| Edge ou Chrome à jour | menu ⋯ › Aide › À propos |
| Un micro, une webcam, des haut-parleurs **et** si possible un casque | |
| Une **clé de conversation** pour le PC | la demander à Codex ou GPT (appairage d'un client « pc ») |

**La clé** : ne pas l'écrire dans un fichier partagé, ni la photographier,
ni la coller dans un message. Elle se tape dans la page et n'est pas gardée.

**Réglages de confidentialité Windows** (Windows 11 : Paramètres ›
Confidentialité et sécurité ; Windows 10 : Paramètres › Confidentialité) :
1. **Microphone** : « Accès au microphone » activé, et « Autoriser les
   applications de bureau à accéder au microphone » activé. Edge, Chrome et
   WebView2 sont des applications de bureau.
2. **Caméra** : mêmes deux réglages.

Si un réglage est coupé, la page doit afficher « refusé — à autoriser dans
Windows et le navigateur ». Cela fait partie de l'essai (W7).

## 1. Ouvrir le tunnel

**Port réel : 8767.** Un seul tunnel suffit : la voix et l'état des machines
passent par le même port.

```powershell
cd <dossier>\eidolon-core\desktop\connected\launchers
.\eidolon-tunnel.ps1 -Server <VM Core> -User toytoy -Port 8767 -Connect -OpenBrowser
```

Le navigateur s'ouvre sur `http://127.0.0.1:8767/`. Sinon, saisir cette adresse
à la main : exactement `127.0.0.1`, pas `localhost`.

## 2. Essais dans Edge ou Chrome

Disposition (G176) :
- en haut à gauche, l'**œil** : activité d'Eidolon et état réel de la caméra ; un clic ouvre la voix et la caméra ;
- au centre, la **zone de discussion** ;
- en haut à droite, **DARME** : un clic ouvre l'état des machines ;
- à gauche, le menu des sections ; le jeton de lecture est dans **Réglages**.

Pour chaque essai, noter **OK** ou **KO** et la mesure demandée dans
[le modèle de résultats](validation/windows-weekend/RESULTS-template.md).

### Ouverture

| # | Essai | Attendu |
| --- | --- | --- |
| W1 | Saisir la clé dans la **barre du haut** | la barre devient le champ « Écrire à Eidolon… » ; l'œil (en haut à gauche) affiche « Eidolon disponible · caméra éteinte » ; aucune demande de permission |
| W2 | Bouton **DARME** (en haut à droite), puis « Afficher l'état des machines » | Core **Gris**, « Surveillance de sécurité incomplète », périmètre et fraîcheur visibles, mesures CPU, mémoire et disque ; Memory et VM101 GPU « Non surveillé » |

### Micro et dictée

| # | Essai | Attendu |
| --- | --- | --- |
| W3 | Cliquer l'**œil** (en haut à gauche) pour ouvrir « Voix et caméra », puis cocher **Micro** | le navigateur demande la permission ; accorder ; état « prêt » ; liste des micros avec leurs noms |
| W4 | « Parler », dire « Bonjour Eidolon, ici toytoy. Il est quinze heures trente. », puis « Terminer » | voyant rouge **seulement** pendant la parole ; texte dans le champ, **non envoyé**. Noter : la durée entre « Terminer » et le texte, le texte obtenu, et la ligne « Corrigé : … » si elle apparaît |
| W5 | Dire une phrase de 20 s environ | noter la durée et les erreurs (noms, nombres) |
| W6 | « Parler » puis « Terminer » sans rien dire, pièce calme puis ventilateur ou bruit de fond | « Rien n'a été entendu. » ; **aucun texte inventé** (par exemple « Sous-titres… ») |
| W7 | Refuser la permission : icône de cadenas › Autorisations du site › Microphone : Bloquer, puis recharger | état « refusé — à autoriser… » ; le texte tapé fonctionne toujours. Remettre ensuite sur « Demander » |
| W8 | Débrancher le micro USB **pendant** « Parler » | capture arrêtée, voyant éteint, aucun plantage ; la liste se met à jour |
| W9 | Rebrancher le micro | il réapparaît dans la liste sans recharger la page |

### Voix d'Eidolon

| # | Essai | Attendu |
| --- | --- | --- |
| W10 | Cocher « Voix d'Eidolon », envoyer un message | la réponse est lue. Noter : délai du premier son (chronomètre), clarté, lecture des nombres, préférence pour la voix |
| W11 | **Haut-parleurs** (sans casque) : pendant la lecture, appuyer sur « Parler » | la voix s'arrête **aussitôt** ; la transcription ne contient pas la voix d'Eidolon (anti-écho) |
| W12 | Même essai **avec casque** | même résultat |
| W13 | « Arrêter la voix » pendant une longue réponse | silence immédiat |

### Caméra

| # | Essai | Attendu |
| --- | --- | --- |
| W14 | Cocher Caméra, puis « Quelqu'un est-il là ? » face caméra, puis hors champ | voyant de la webcam allumé un instant puis **éteint** ; « Une personne visible… (observation non vérifiée) » puis « Personne… ». Noter la durée |
| W15 | « Décrire la scène » | description courte, **sans nom ni identité** |
| W16 | Webcam déjà utilisée (application Caméra, Teams…) | « occupé par une autre application », sans plantage |
| W17 | Débrancher puis rebrancher une webcam USB | la liste se met à jour |

### Clavier, affichage, fin

| # | Essai | Attendu |
| --- | --- | --- |
| W18 | **Clavier seul** : depuis le champ du haut, Maj+Tab jusqu'à l'œil, Entrée, Tab jusqu'à « Micro », Espace, Tab jusqu'à « Parler », Entrée, parler, Entrée ; Échap ferme le panneau | tout fonctionne, focus toujours visible (contour) |
| W19 | Échelle Windows **125 %** puis **150 %** (Paramètres › Système › Écran › Échelle), fenêtre étroite, puis Ctrl + et Ctrl − dans le navigateur | rien ne déborde ni ne se chevauche ; boutons lisibles |
| W20 | Cocher « Actualisation automatique », attendre 30 s, puis « Fermer la conversation » | l'heure de lecture avance ; à la fermeture, le panneau des machines disparaît et la caméra et le micro sont relâchés |
| W21 | Couper le Wi-Fi ou le tunnel 30 s, puis le rétablir | messages d'erreur clairs, pas de plantage ; la page refonctionne après réouverture |

## 3. Application Windows (facultatif, si le temps le permet)

L'application `eidolon-consultation` (Tauri, WebView2) **n'est pas fournie
compilée**. La construire sur le PC demande Rust et les outils de
compilation de Visual Studio. Le runtime WebView2 est inclus dans
Windows 11.

```powershell
cd <dossier>\eidolon-core\desktop\tauri
cargo build --release
.\target\release\eidolon-consultation.exe --port 8767
```

- **`--port 8767` est obligatoire** : le port par défaut de l'application
  est 8765.
- **Permissions (G165)** :
  - micro et caméra : l'application ne les accorde **jamais** d'elle-même,
    WebView2 affiche sa propre demande ;
  - localisation, notifications, presse-papiers, fichiers et autres :
    **refusés** d'office.
- Refaire W1, W3, W4, W7, W10, W14 et W19 dans l'application.
- WebView2 garde le choix « Autoriser » ou « Bloquer ». Pour revenir à la
  demande, fermer l'application et supprimer le dossier de profil WebView2
  (`%LOCALAPPDATA%\local.eidolon.consultation\EBWebView`). Cet emplacement
  est **à confirmer** pendant l'essai.

## 4. Fin de l'essai

1. Décocher micro, voix et caméra, puis « Fermer la conversation ».
2. Arrêter le tunnel :
   `.\eidolon-tunnel.ps1 -Stop -Port 8767`.
3. Remplir le [modèle de résultats](validation/windows-weekend/RESULTS-template.md)
   et le donner à Claude ou GPT.

Ce qu'il **ne faut pas** mettre dans les résultats :
- la clé ;
- une adresse IP ;
- une capture montrant la clé ;
- une photo de personne.

## 5. Ce que l'essai ne vérifie pas

- La précision de la dictée sur d'autres voix que la tienne.
- La reconnaissance des personnes : elle **n'existe pas**, la vision dit
  seulement si quelqu'un est visible.
- Une caméra réseau : ne pas en brancher.
