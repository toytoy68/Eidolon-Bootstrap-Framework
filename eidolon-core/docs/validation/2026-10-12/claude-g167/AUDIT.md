# Audit disponibilité et reprise des trois services (G167)

Auteur : Claude. Date : 12/10/2026, Europe/Paris.

Périmètre : Core API (8767), eidolon-comm (8766), eidolon-monitor (8768), tels que Codex les a déployés (G162).

## Constats et suites

| # | Constat | Gravité | Suite |
| --- | --- | --- | --- |
| A1 | `Type=simple` : systemd déclare le service démarré **avant** que le port n'écoute. Codex l'a observé : un refus de connexion juste après le redémarrage. | moyenne | **Corrigé pour comm et monitor** : `sd_notify.py` (bibliothèque standard), `READY=1` envoyé après l'ouverture du port ; unités en `Type=notify`, `NotifyAccess=main`, `TimeoutStartSec=30`. Test : `READY` reçu, puis connexion immédiate acceptée. **Core API** : proposition A1-bis ci-dessous, à appliquer par Codex (`http_api.py` est partagé). |
| A2 | Clé **révoquée pendant** une transcription, une synthèse ou une image : le résultat était quand même rendu. | moyenne | **Corrigé** : après le traitement, `CommAPI` revérifie la clé ; si elle est révoquée, 401 et résultat jeté. Test avec la vue `ReadOnlyClientCredentials` réellement déployée ; un autre client n'est pas touché. Le monitor relit la clé à chaque appel ; ses lectures sont instantanées. |
| A3 | Service média absent : Core répond `503 MEDIA_WORKER_NOT_CONFIGURED`, mais la page classait la validation « incertaine », comme une panne réseau. | basse | **Corrigé** : refus définitif avec un message en français. Les autres 5xx restent incertains (test). |
| A4 | Service voix ou monitor arrêté pendant l'usage | — | Déjà couvert : le relais renvoie `COMM_UNAVAILABLE` / `MONITOR_UNAVAILABLE` ; la page affiche l'erreur, le texte reste utilisable ; le suivi machines s'arrête après 3 échecs (tests G157 et G158). |
| A5 | Annulation | — | Déjà couvert : `DELETE /v1/comm/stt` et `/tts` ; une réponse tardive est ignorée par la page (tests G149). |
| A6 | Concurrence des moteurs (« file ») | info | Pas de file d'attente : **un** appel moteur à la fois par service, le suivant reçoit `DEVICE_BUSY` aussitôt. C'est voulu : pas d'attente invisible, et la page l'affiche. |
| A7 | Priorité CPU face au dialogue et à la page | basse | **Ajouté** dans l'unité comm : `Nice=10`, `CPUWeight=50`, E/S en priorité basse. Whisper cède le processeur quand Core travaille. Effet sur la durée de dictée **à mesurer** sur la VM. |
| A8 | `ProtectHome=read-only` | — | Respecté. Aucune écriture ; la vue `ReadOnlyClientCredentials` est obligatoire et non assouplie. |

## A1-bis — proposition pour Core API (non poussée)

Dans `http_api.main`, juste avant `server.serve_forever()` :

```python
from .sd_notify import notify
notify()           # G167: ready once the port listens
```

Dans `eidolon-core-api.service` :

```ini
Type=notify
NotifyAccess=main
TimeoutStartSec=60
```

**Risque** : l'unité et le code doivent changer **ensemble**. Une unité
`notify` avec un ancien code ferait échouer le démarrage au bout de 60 s.
L'installateur G159 ne modifie que les options de relais de l'unité Core :
ce changement reste donc manuel.

## Preuves

- `tests/test_service_readiness.py` : 3 tests (signal `READY`, port
  ouvert, révocation pendant une requête).
- `desktop/connected/tests/conversation.test.js` : test du service média
  absent.
- **Non fait** : redémarrages réels sous systemd sur la VM, et mesure de
  `Nice` sur la durée de dictée.
