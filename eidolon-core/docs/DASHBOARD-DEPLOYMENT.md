# Déploiement du dashboard (page connectée + voix et caméra) — essai PC du week-end

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande de toytoy : « travaille sur le déploiement du
dashboard » ; essai sur le PC **le week-end prochain**. Échanges : C147.

Le dashboard est la **page connectée servie par Core** (`desktop/connected`), ouverte sur le PC :
- dans un navigateur ;
- ou dans la coquille Tauri `eidolon-consultation`.

Le PC y accède par un tunnel SSH. **Rien n'est installé sur le PC** à part
OpenSSH, déjà présent sur Windows.

## 1. Ce qui change avec ce lot

- **Bloc « Voix et caméra »** dans la conversation, **éteint par défaut** :
  - micro, voix d'Eidolon et caméra, chacun avec son interrupteur, son choix
    d'appareil et son voyant ;
  - « Parler » / « Terminer » : la transcription est **placée dans le champ**,
    jamais envoyée toute seule ;
  - lecture à voix haute des **nouvelles** réponses quand la voix est
    allumée ;
  - « Quelqu'un est-il là ? » et « Décrire la scène » : **une** image, caméra
    relâchée aussitôt, aucune identification.
- **Relais de même origine** : Core transmet `/v1/comm/*` au service voix
  (`--comm-port 8766`). La règle de sécurité de la page (`connect-src
  'self'`) ne change pas, et il n'y a **qu'un port dans le tunnel**.
- Recette navigateur :
  [recipe_dashboard.json](validation/2026-10-12/claude-dashboard/recipe_dashboard.json),
  **19/19** à 1280 et 360 px. Elle utilise Chromium avec **faux** micro et
  **fausse** caméra, Core et le service voix lancés comme sur la VM, et des
  moteurs simulés. Capture : [bloc à 360 px](validation/2026-10-12/claude-dashboard/captures/dashboard-comm-360.png).

## 2. Sur la VM Core (à faire par GPT ou toytoy, avant le week-end)

1. Mettre à jour le code dans `/opt/eidolon-core/bootstrap` jusqu'au commit de
   ce lot.
2. Installer les moteurs et la configuration privée : [COMMUNICATION.md §4](COMMUNICATION.md).
   Sans moteur, la page affiche « indisponible » et le texte reste utilisable.
3. Installer l'unité
   [`eidolon-comm.service`](../deployment/vm-profile/eidolon-comm.service) :
   - même compte que Core, en lecture seule sur l'état Core ;
   - boucle locale seulement ;
   - limites de mémoire et de processeur **à ajuster après mesure**.
4. Appliquer la nouvelle version de
   [`eidolon-core-api.service`](../deployment/vm-profile/eidolon-core-api.service) :
   seul ajout, `--comm-port 8766`.
5. Vérifier :
   ```sh
   python -m eidolon_core.comm_service --state … --config ~/eidolon-comm/comm.json --check
   systemctl daemon-reload && systemctl restart eidolon-comm eidolon-core-api
   ```
   Retour arrière : retirer `--comm-port 8766`, puis arrêter et désactiver
   `eidolon-comm`. La page affiche alors les moteurs comme indisponibles.

## 3. Sur le PC Windows (week-end)

**Port réel : 8767** (unité `eidolon-core-api.service`). Il faut le **même
numéro des deux côtés** du tunnel (constat G082).

```powershell
.\eidolon-tunnel.ps1 -Server <VM Core> -User toytoy -Port 8767 -Connect -OpenBrowser
# ou, avec la coquille : eidolon-consultation --port 8767
```

**Ordre conseillé** :
1. d'abord dans **Edge ou Chrome**, où la gestion des permissions de micro
   et de caméra est connue ;
2. ensuite dans la **coquille Tauri** : WebView2 demande aussi la permission,
   mais son comportement exact avec Tauri **n'a pas été essayé**.

**Liste d'essai** (à cocher et à rapporter) :

| # | Essai | Attendu |
| --- | --- | --- |
| 1 | Ouvrir la conversation avec ta clé | bloc « Voix et caméra » visible, **tout décoché**, aucun voyant rouge |
| 2 | Cocher Micro | Windows ou le navigateur demande la permission ; « prêt » si accordée, « refusé — à autoriser dans Windows… » sinon |
| 3 | « Parler », dire une phrase, « Terminer » | voyant rouge **seulement** pendant la parole ; texte dans le champ, **non envoyé** ; durée de transcription à noter |
| 4 | Corriger le texte, puis Envoyer | réponse normale de Core |
| 5 | Cocher « Voix d'Eidolon », envoyer un message | la réponse est lue ; noter le délai du premier son, la clarté et les nombres |
| 6 | Pendant la lecture, appuyer sur « Parler » | la voix s'arrête **aussitôt** |
| 7 | Cocher Caméra, puis « Quelqu'un est-il là ? » | voyant de la webcam allumé un instant puis éteint ; texte « … (observation non vérifiée) » |
| 8 | Webcam déjà utilisée (Teams, Zoom…) | « occupé par une autre application », sans plantage |
| 9 | Débrancher ou rebrancher une webcam USB | la liste se met à jour |
| 10 | Refuser la permission | état « refusé », le texte reste utilisable |
| 11 | Couper le service voix sur la VM | « indisponible » ou erreur affichée, conversation texte intacte |
| 12 | Échelle Windows 125 % et 150 %, fenêtre étroite | rien ne déborde |

**À ne pas faire** : brancher une caméra réseau, ou laisser la capture
allumée sans surveillance. Rien n'est enregistré, mais l'image et le son sont
traités sur la VM.

## 4. Ce qui n'est pas prêt ou pas vérifié

- **Badge DARME** dans la page : à coordonner avec Codex (relais et socket,
  G153). Pas dans ce lot.
- **WebView2 et Tauri** : permissions micro et caméra non essayées.
- **Vrais moteurs** (Whisper, Piper, vision) : dépendent de l'installation
  par GPT (C147). Les durées réelles sont inconnues.
- **Port 8765** encore utilisé par défaut dans la coquille Tauri et dans
  d'anciens guides : passer `--port 8767` explicitement.
