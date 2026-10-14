# Déploiement du dashboard (page connectée + voix et caméra) — essai PC du week-end

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande de toytoy : « travaille sur le déploiement du
dashboard » ; essai sur le PC **le week-end prochain**. Échanges : C147, G154 (lots G155–G160), G161 (contrat machine), C148.

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
- **Panneau « État des machines »** (G156), visible quand la conversation est
  ouverte. **Rien n'est lu avant le clic** sur « Afficher l'état des machines ».
  Il montre :
  - le badge DARME avec son mot (Or, Gris, Rouge, Bleu, Statut périmé,
    Indisponible), son **périmètre** et sa **fraîcheur** ;
  - les sources ;
  - les mesures machine du contrat `eidolon-machine/1` de Codex (G161) :
    CPU, charge, mémoire, swap et disque du journal, datés. Une mesure
    absente est écrite « indisponible », jamais 0 ; le GPU est « non sondé ».
  Le gris est écrit « ce n'est PAS un état sécurisé ». Le GPU de VM101 est
  affiché « Non surveillé », sans aucune mesure.
- **Adaptateur `eidolon-monitor`** (G157), port 8768 en boucle locale. Core
  le relaie avec `--monitor-port 8768` : contrat au §5.
- Recette navigateur :
  [recipe_dashboard.json](validation/2026-10-12/claude-dashboard/recipe_dashboard.json),
  **31/31** à 1280 et 360 px. Elle utilise :
  - Chromium avec **faux** micro et **fausse** caméra ;
  - Core, le service voix et l'adaptateur lancés comme sur la VM ;
  - des moteurs simulés ;
  - le **vrai** `Collector` DARME, avec ses vraies mesures machine
    (`eidolon-machine/1`) et des sondes de services injectées.
  Captures : [voix à 360 px](validation/2026-10-12/claude-dashboard/captures/dashboard-comm-360.png),
  [machines à 360 px](validation/2026-10-12/claude-dashboard/captures/dashboard-monitor-360.png).

## 2. Sur la VM Core (à faire par Codex, avant le week-end)

Claude n'a pas accès à la VM. Les scripts sont prêts ; **Codex les exécute et
publie la recette**.

1. Mettre à jour le code dans `/opt/eidolon-core/bootstrap` jusqu'au commit de
   ce lot.
2. **Plan, sans rien modifier** :
   ```sh
   python3 deployment/dashboard_install.py install --source deployment/vm-profile
   ```
3. **Installer** :
   ```sh
   sudo python3 deployment/dashboard_install.py install --source deployment/vm-profile --apply
   ```
   Ce que fait l'installation :
   - elle **sauvegarde d'abord** tout fichier visé qui existe (archive 0600
     dans `/var/backups/eidolon/dashboard-preinstall-*.tar.gz`) ;
   - elle copie [`eidolon-comm.service`](../deployment/vm-profile/eidolon-comm.service)
     et [`eidolon-monitor.service`](../deployment/vm-profile/eidolon-monitor.service) ;
   - elle **ajoute seulement** `--comm-port 8766 --monitor-port 8768` à
     l'unité Core **active**. La copie du dépôt ne la remplace jamais, et
     une valeur différente déjà présente est refusée ;
   - elle crée `~/eidolon-monitor/monitor.json` depuis
     [l'exemple](../deployment/vm-profile/monitor.json.example), **seulement
     s'il est absent** (0600).
   Elle **n'écrase aucune configuration**, ne copie aucune clé et n'appelle
   pas `systemctl` : elle affiche les commandes suivantes.
4. Moteurs voix et `comm.json` : voir [COMMUNICATION.md §4](COMMUNICATION.md).
   Sans eux, n'activer **que** `eidolon-monitor`. La page affiche alors la
   voix comme « indisponible » et le texte reste utilisable.
5. Commandes affichées par l'installateur :
   ```sh
   systemctl daemon-reload
   systemctl enable --now eidolon-monitor.service
   systemctl restart eidolon-core-api.service
   ```
6. **Prévol** (lecture seule ; `--probe` ouvre seulement les ports locaux et
   envoie `STATUS` au socket DARME) :
   ```sh
   python3 deployment/dashboard_install.py preflight --probe
   ```
   Il vérifie :
   - les unités, et que Core relaie vers les bons ports ;
   - que les trois ports sont distincts ;
   - que les trois services utilisent le même état ;
   - la boucle locale ;
   - que les configurations sont privées et que l'origine vaut
     `http://127.0.0.1:8767` ;
   - le socket DARME.

**Retour arrière** :
1. `tar -xzf <archive> -C /` ;
2. `systemctl daemon-reload` ;
3. `systemctl disable --now eidolon-monitor eidolon-comm` ;
4. `systemctl restart eidolon-core-api`.

Sans les relais, la page affiche « Surveillance non activée » ; la
conversation n'est pas touchée.

## 3. Sur le PC Windows (week-end)

**Guide complet, à suivre pas à pas** : [WINDOWS-WEEKEND.md](WINDOWS-WEEKEND.md)
(G165). Il contient 21 essais (W1 à W21), les réglages de confidentialité
Windows, l'application facultative et le
[modèle de résultats](validation/windows-weekend/RESULTS-template.md).
Le résumé ci-dessous reste valable.

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
| 13 | « Afficher l'état des machines » | Core **Gris** « ce n'est PAS un état sécurisé », périmètre et fraîcheur visibles ; Memory et VM101 GPU « Non surveillé » |
| 14 | Cocher « Actualisation automatique », attendre 30 s, puis fermer la conversation | l'heure de lecture avance ; à la fermeture, le panneau disparaît et les données sont effacées |

**À ne pas faire** : brancher une caméra réseau, ou laisser la capture
allumée sans surveillance. Rien n'est enregistré, mais l'image et le son sont
traités sur la VM.

## 4. Ce qui n'est pas prêt ou pas vérifié

- **Mesures machine** : le contrat de Codex (G161) est suivi champ par champ.
  Elles ne sont vérifiées qu'en conteneur ; la lecture du vrai socket sur la
  VM revient à Codex.
- **Memory** : aucune sonde depuis Core. Une lecture du DARME de Memory
  demanderait un relais à part (tunnel de socket), **non fait**.
- **WebView2 et Tauri** : permissions micro et caméra non essayées.
- **Vrais moteurs** (Whisper, Piper, vision) : dépendent de l'installation
  par GPT (C147). Les durées réelles sont inconnues.
- **Port 8765** encore utilisé par défaut dans la coquille Tauri et dans
  d'anciens guides : passer `--port 8767` explicitement.

## 5. Contrat `eidolon-monitor/1` (G157)

**Route unique** : `GET /v1/monitor/status`, sur la page (relais Core) ou
directement sur `127.0.0.1:8768`.

**Accès accepté** : seulement la **clé de conversation appairée**. Sont
refusés :
- le jeton de lecture (`READ_TOKEN_NOT_ALLOWED`) ;
- un client inconnu ou révoqué (`UNAUTHORIZED`) ;
- toute requête avec un paramètre ou un corps ;
- toute méthode autre que GET ;
- un `Host` ou un `Origin` inexacts.

**Réponse** (bornée, aucune donnée brute) :
```json
{"protocol": "eidolon-monitor/1", "generated_at": "…", "poll_seconds": 10,
 "machines": [{"id": "core", "label": "Core", "state": "ok|stale|unavailable|invalid", "error": "…",
   "darme": {"badge": "gold|grey|red|blue", "secure_claim": false, "visibility": "complete|partial",
     "sources": {"unité": true}, "scope": "…", "security_telemetry_installed": false,
     "unacknowledged_alerts": 0, "intervention": false, "ingestion_paused": false,
     "generated_at": "…", "age_seconds": 4, "health_ttl_seconds": 60},
   "machine": {"sampled_at": "…", "age_seconds": 3, "stale": false, "cpu_count": 8, "cpu_percent": 12.5,
     "load_1_5_15": [0.4, 0.3, 0.2], "memory": {"total_bytes": 0, "available_bytes": 0, "used_bytes": 0},
     "swap": {"total_bytes": 0, "free_bytes": 0, "used_bytes": 0},
     "disk": {"scope": "journal_filesystem", "total_bytes": 0, "free_bytes": 0, "used_bytes": 0},
     "gpu": null, "errors": []}}],
 "not_covered": ["Memory", "VM101 GPU"], "gpu_metrics": null, "authorizes_execution": false}
```

**Lecture du socket DARME** :
- l'adaptateur envoie seulement les octets fixes `STATUS\n` ;
- il lit au plus 64 Kio, en 3 s au maximum ;
- il garde le résultat 2 s en cache commun, pour que plusieurs onglets ne
  multiplient pas les lectures.

**Réponse invalide** (`state` = `invalid`) quand :
- le schéma n'est pas `eidolon-darme-service/1` ;
- `authorizes_execution` n'est pas `false` ;
- le badge est inconnu ;
- la date n'a pas de fuseau ;
- la date est en avance de plus de 5 s (`CLOCK_SKEW`).

**Statut périmé** : au-delà de `health_ttl_seconds`, `state` vaut `stale`
et la page retire la couleur du badge.

**Champ `machine`** (contrat `eidolon-machine/1`, G161) :
- seuls les champs du contrat sont recopiés ;
- un bloc incohérent (par exemple utilisé + libre > total, ou un disque
  d'un autre `scope`) **annule toute la vue** : `machine: null`, et
  `darme.machine_error` vaut `MACHINE_INVALID` ;
- une date de mesure en avance donne `MACHINE_CLOCK_SKEW` ;
- au-delà de 60 s, `stale: true`, et la page écrit « Mesures PÉRIMÉES ».

**Compte du socket** : avec `"peer_user": "eidolon-darme"` dans
`monitor.json`, l'adaptateur vérifie par `SO_PEERCRED` que le socket est
bien servi par ce compte (`PEER_REFUSED` sinon), comme `read_status()` de
`monitor_tools.py`.

**Jamais relayés** :
- `events` et les sujets d'événements ;
- les champs inconnus ;
- les chemins et les jetons.

**Accès au socket** : Codex a ajouté `toytoy` au groupe `eidolon-darme`
(G161). L'unité garde en plus `SupplementaryGroups=eidolon-darme`, pour que
l'accès ne dépende pas de l'appartenance du compte au groupe. Ni sudo ni le socket ne
sont exposés au navigateur.

## 6. Revue de sécurité et nature des preuves (G160)

| Point | Constat |
| --- | --- |
| Surface réseau | Un seul port tunnelé (8767). Les ports 8766 et 8768 sont en boucle locale, avec `IPAddressDeny=any`. CSP `connect-src 'self'` inchangée. |
| Authentification | Les services vérifient eux-mêmes la clé appairée. Core ne fait que transmettre `Authorization`. Jeton de lecture et clé révoquée refusés (tests). |
| Entrées navigateur | Monitor : aucune donnée du navigateur ne va à DARME. Voix : corps borné, formats vérifiés (lot G146–G151). |
| Sorties | Liste blanche champ par champ côté adaptateur ; compte du socket vérifié (`SO_PEERCRED`). La page affiche tout en `textContent`, jamais en HTML. |
| Capture | Rien au chargement, ni micro ni caméra ni lecture machine (tests 156/156 et recette 31/31). |
| Suivi | Une requête à la fois, toutes les 10 s au plus. Pause quand l'onglet est caché. Arrêt après 3 échecs, sur refus 401/403, et à la fermeture ou au départ de la page. |
| ResourceWarning (G154) | Socket non fermé quand Ollama répond par une erreur HTTP (`HTTPError`, module vision). Corrigé : 64 tests `test_comm*.py` sans avertissement sous `-X dev`. |
| Installation | Simulation par défaut, sauvegarde avant écriture, unité Core seulement complétée, configurations jamais écrasées, liens refusés (7 tests). |

**Nature des preuves** :
- **Simulé (conteneur)** : moteurs voix et vision, faux périphériques
  Chromium, sondes de services injectées dans le vrai `Collector`. Les
  mesures machine, elles, sont réelles mais prises dans le conteneur.
- **Pas encore fait** :
  - appels réels sur la VM (installation, prévol `--probe`, socket DARME
    réel avec le groupe) ;
  - Edge, Chrome et WebView2 sous Windows ;
  - vrais micro, caméra et haut-parleurs.
- Ces essais reviennent à **Codex** pour la VM, et à **toytoy** pour le PC le
  week-end.
