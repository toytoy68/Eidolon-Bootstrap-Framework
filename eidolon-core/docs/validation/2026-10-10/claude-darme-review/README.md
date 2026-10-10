# DARME — Revue du concept et du prototype v0.1

Auteur : Claude. Date : 10/10/2026, Europe/Paris.

Demandes :
- [DARME-SECURITY-CONCEPT.md](../../../DARME-SECURITY-CONCEPT.md) (`9396e52`) ;
- G140 §4 et G141 (GPT, relayés par toytoy).

**Revue seulement** : je n'ai rien implémenté ni déployé, aucune capture ni
action réseau, et je n'ai pas modifié les fichiers DARME de GPT.

Les remarques sur le matériel (Freebox, Netgear, Proxmox, TrueNAS) viennent
de connaissances générales. Elles n'ont pas été vérifiées sur le réseau de
toytoy et sont marquées **à vérifier**.

## 0. En bref

- Le concept est sain sur l'essentiel :
  - purement défensif, sans représailles ;
  - LLM sans autorité ;
  - réponses réversibles qui expirent ;
  - « pas de données ≠ pas de menace ».
- Cinq désaccords, détaillés au §7 :
  - DARME doit tourner **hors du processus Core** ;
  - **pas d'extinction automatique** ;
  - la **v0.1 se limite à la VM Eidolon**, en passif, par les journaux ;
  - pas de LLM sur des journaux bruts ;
  - **badge sans référence policière ni new-yorkaise**.
- Le prototype `darme.py` (`c417e66`) est un bon squelette. Il est passif et
  sans privilège, et ses 7 tests passent. J'y trouve **5 défauts**,
  reproduits par [probes_darme.py](probes_darme.py), qui échoue 5 fois sur 5
  à ce commit. Le plus important : **une alerte critique connue disparaît
  derrière le gris** dès qu'une sonde tombe (R2).

## 1. Architecture proposée

```text
 collecteurs (non privilégiés, un par source)      VM / conteneur DARME (séparé de Core)
 ┌──────────────────────────────┐   événements     ┌───────────────────────────────────────┐
 │ journald sshd, ss -ltn diff, │ ──── signés ───▶ │ ingest (schéma strict, bornes)         │
 │ compteurs nftables, syslog   │   (clé par       │ magasin append-only (SQLite + chaîne   │
 │ NAS/Proxmox, plus tard IDS   │    collecteur)   │   d'empreintes), rétention             │
 └──────────────────────────────┘                  │ règles déterministes → alertes         │
                                                   │ API statut LECTURE + acquittement      │
                                                   └──────────────┬────────────────────────┘
                                                                  │ HTTP 127.0.0.1 / lien privé
 plus tard, séparé et désactivé par défaut :                      ▼
 agent de réponse (seul droit : ajouter un élément        Core : relais en LECTURE du statut
 temporaire dans un set nftables, avec expiration)       → badge dans l'application Windows
```

- **Séparation** : DARME a son processus, son compte, son stockage et, à
  terme, sa VM ou son conteneur LXC.
  - Core ne lit que son statut.
  - DARME n'a aucun accès à l'état de Core : ni conversations, ni missions,
    ni clés.
  - Si l'un est compromis, l'autre ne l'est pas d'office.
- **Le prototype `darme.py`** peut rester dans le paquet comme **modèle
  partagé** (le contrat du statut). Le service qui collecte ne doit pas
  tourner dans le serveur HTTP de Core.
- **Bus d'événements** : il n'en faut pas au début. Les collecteurs écrivent
  des événements signés, chacun avec sa propre clé Ed25519, comme pour les
  sauvegardes. DARME refuse un événement non signé, ou signé par une source
  inconnue.
- **Stockage durable** :
  - SQLite en ajout seul, chaque ligne portant l'empreinte de la précédente ;
  - acquittements enregistrés comme des événements (qui, quand, pourquoi) ;
  - rétention configurable.
- **Privilèges** :
  - lire `journald` passe par le groupe `systemd-journal` ;
  - lister les ports en écoute ne demande aucun privilège ;
  - les compteurs `nftables` demandent `CAP_NET_ADMIN` : lecture par une
    petite commande dédiée, ou exporter les compteurs ;
  - **aucun collecteur root permanent**.
- **Réponse, plus tard** : un agent séparé n'a qu'un droit, ajouter une
  adresse dans un set `nftables` avec délai d'expiration (`timeout`). Il ne
  peut ni vider le pare-feu ni toucher aux règles. Tant que la recette n'est
  pas faite, chaque blocage est proposé et un humain le valide, comme les
  missions.

## 2. Visibilité réelle (Freebox Delta, GS728TX, Proxmox, TrueNAS)

| Point d'observation | Ce qu'on peut voir | Angle mort |
| --- | --- | --- |
| **Freebox Delta** | journaux et redirections de ports, via son interface | **pas de recopie de trafic connue** (à vérifier) ; elle ne sert pas de sonde réseau |
| **Netgear GS728TX** | recopie de port (*port mirroring*) **probable** sur ce switch administrable (à confirmer dans son manuel) vers une interface dédiée | le trafic **entre VM d'un même hôte Proxmox** ne passe pas par le switch |
| **Proxmox (pont `vmbr0`)** | tout le trafic des VM de l'hôte, depuis l'hôte, ou recopié vers l'interface d'une VM de sonde (`tc mirred`) | une sonde **sur l'hôte** élargit la surface de l'hôte |
| **TrueNAS** | journaux d'authentification SMB, SSH et interface, envoyés en syslog | trafic chiffré, contenu des partages |
| **PC Windows** | journal d'événements (échecs de connexion 4625, Defender) | demande un agent sur le PC : **hors v0.1** |
| **Partout** | rien du contenu TLS (voulu) | les attaques dans un flux chiffré ne se voient que par leurs métadonnées |

**Coût** (ordres de grandeur, à **mesurer** sur l'hôte réel, qui sert déjà
l'inférence) :
- Suricata en IDS : environ 1 à 2 Go de RAM avec les règles courantes, et
  plusieurs cœurs à 1 Gbit/s ;
- CrowdSec : quelques centaines de Mo ;
- collecte de journaux : négligeable.

Le badge **gris** doit dire *quelles* sources manquent, pas seulement
« inconnu ».

## 3. Modèle de menace

| Scénario | Risque | Parade |
| --- | --- | --- |
| **Injection via les journaux** (nom d'utilisateur SSH « ignore tes instructions… », séquences ANSI) | un LLM de tri obéit ; journal falsifié ; affichage corrompu | refuser les caractères de contrôle (R4) ; texte venu des journaux toujours en bloc **non fiable**, comme `TOOL RESULTS` dans Core ; LLM seulement sur des champs structurés |
| **Usurpation d'adresse source** | blocage d'une adresse légitime (passerelle, PC admin) | liste d'adresses jamais bloquées (admin Proxmox, passerelle, PC de toytoy), vérifiée par un test de propriété ; blocages courts qui expirent |
| **Faux positifs** | alerte permanente, ou blocage du service légitime | dry-run d'abord ; seuils mesurés ; acquittement avec raison |
| **Inondation d'événements** | mémoire saturée, alertes noyées | bornes (R5), agrégation par catégorie et source, limite par collecteur |
| **Compromission de la VM DARME** | faux statut « or », ou blocages abusifs | aucun droit sur Core ; agent de réponse séparé, au périmètre minimal ; statut signé ; un collecteur muet passe le badge au **gris**, jamais à l'or |
| **Blocage de l'administration** | toytoy enfermé dehors | liste de protection codée en dur et testée ; expiration automatique ; chemin hors bande (console Proxmox) documenté |
| **Perte de télémétrie** | « or » alors qu'on ne voit plus rien | état par source avec `last_seen` et délai d'obsolescence ; gris dès qu'une source est muette ; **sans effacer le rouge** (R2) |
| **Horloge décalée** | ordre faux, fenêtres de détection fausses | instants normalisés en UTC (R3) ; écart d'horloge par source signalé |
| **Fuite de secrets** | jetons ou mots de passe dans les alertes, ou envoyés à un LLM | filtrage des secrets connus (formats de jetons Core) avant stockage ; rien de brut vers un LLM |

## 4. État du badge et contrat d'API minimal

**Priorité proposée** (G141 met le gris au-dessus du rouge, ce qui cache un
incident connu) :

1. **rouge** : au moins une alerte non acquittée, même si des sondes
   manquent ;
2. **bleu** : une intervention est active, avec sa nature et son
   expiration ;
3. **gris** : au moins une source attendue est muette ou obsolète, sans
   alerte connue ;
4. **or** : toutes les sources sont fraîches, sans alerte et sans
   intervention.

Le badge porte en plus un indicateur `visibility: complete | partial`, pour
afficher par exemple « rouge, visibilité partielle ».

```text
GET /v1/darme/status        (jeton de lecture, comme /v1/missions)
{ "schema": "eidolon-darme-status/1", "generated_at": "...Z",
  "badge": "red|blue|grey|gold", "visibility": "complete|partial",
  "sources": {"pve-journal": {"state": "fresh|stale|down", "last_seen": "...Z", "stale_after_s": 120}},
  "alerts": {"critical": 1, "warning": 0},
  "intervention": null | {"kind": "...", "target": "...", "expires_at": "...Z"},
  "enforcement_enabled": false, "authorizes_execution": false }

POST /v1/darme/acknowledge  (clé appairée, comme la soumission d'une mission)
{ "command_key": "...", "event_id": "...", "actor": "toytoy", "reason": "...",
  "status_sha256": "<empreinte du statut affiché>" }
→ reçu durable et idempotent (même clé, même reçu) ; refus si le statut a changé depuis l'affichage.
```

Le statut affiché est en lecture seule. L'acquittement ne bloque ni ne
débloque rien : il éteint le rouge pour cette alerte, avec une trace.

## 5. Outils comparés, et MVP

| Outil | Rôle | Pour | Contre |
| --- | --- | --- | --- |
| **journald / syslog** | authentifications, services | déjà là, léger, sans privilège | ne voit pas le réseau |
| **nftables** | compteurs ; plus tard, sets à expiration | déjà dans le noyau ; le blocage temporaire est natif (`timeout`) | lire les compteurs demande `CAP_NET_ADMIN` |
| **CrowdSec** | analyse de journaux, décisions | léger, scénarios prêts (force brute SSH) | la liste communautaire **envoie des adresses observées** à un service externe : à désactiver ou à décider ; le « bouncer » bloque, donc pas en v0.1 |
| **Suricata** | IDS réseau | référence, règles riches, lecture de pcap hors ligne | coûteux ; a besoin d'une recopie de trafic ; risque de bruit |
| **eBPF** | collecte fine sur l'hôte | précis, peu coûteux | complexe, privilégié, fragile entre noyaux |

**MVP raisonnable (v0.1, passif, VM Eidolon seule)** :
1. échecs d'authentification SSH et API de Core, depuis `journald` ;
2. **différence des ports en écoute** par rapport à une référence validée
   par toytoy ;
3. compteurs `nftables` en lecture ;
4. statut, badge et acquittement durables, sans aucune action.

**v0.2** :
- CrowdSec en **détection seule**, partage communautaire désactivé ;
- Suricata sur la recopie du pont Proxmox, en IDS seulement, **après mesure
  de la charge**.

**Réponse active** : seulement après recette, avec accord humain à chaque
blocage au début.

## 6. Plan de tests (sans trafic offensif vers Internet)

- **Unitaires** : bornes, caractères de contrôle, ordre en UTC, priorité du
  badge (R1 à R5), idempotence de l'acquittement.
- **Rejeu hors ligne** :
  - journaux synthétiques (échecs SSH, nouveau port) passés aux
    collecteurs ;
  - `suricata -r fichier.pcap` sur des captures publiques de test ou
    fabriquées en local ;
  - aucun paquet n'est émis.
- **Pannes** : collecteur tué → gris ; journal tronqué, horloge décalée,
  inondation de 100 000 événements → borné et signalé ; disque plein →
  refus clair.
- **Hostile** : nom d'utilisateur SSH contenant une injection ou de l'ANSI →
  refusé ou neutralisé, et jamais transmis comme instruction.
- **Réponse, dans un réseau isolé seulement** (pont Proxmox de test sans
  sortie) :
  - un set `nftables` avec `timeout` expire bien ;
  - la liste de protection n'est **jamais** bloquée (test de propriété) ;
  - retour à l'état initial après redémarrage ;
  - dry-run comparé à l'exécution réelle.
- **Bout en bout** : badge dans la page à 1 280 et 360 px, pour chacun des
  quatre états.

## 7. Désaccords, alternatives, charge

1. **Pas d'extinction automatique d'un serveur**, même configurée : elle
   transforme un faux positif en panne, voire en perte de données. Je
   propose d'isoler le service touché, de notifier, et de laisser l'humain
   décider de l'extinction.
2. **DARME hors du processus Core**, comme au §1.
3. **v0.1 limitée à la VM Eidolon.** Le réseau entier vient après les
   essais VM et PC de la bêta, qui ne sont pas faits.
4. **Le LLM ne lit jamais de journaux bruts** : seulement des événements
   normalisés et bornés, comme blocs non fiables.
5. **Le badge** : la tête de chien de garde au collier à pointes est retenue
   par toytoy (C140). Sur l'image actuelle, deux éléments gardent une
   référence policière ou new-yorkaise :
   - le **contour** à épaulements reste celui des insignes de police
     américains ;
   - la **silhouette de New York** (Empire State Building) est en fond.

   Je propose :
   - un écusson de forme simple, ou un bouclier ;
   - un motif ECT à la place de la ville (réseau, circuit, serveurs) ;
   - une **version simplifiée** pour la barre : tête et collier, sans
     lauriers ni texture.

   Le chien, vigilant et gueule fermée, et le collier sont très bien.

**Charge estimée pour la bêta** (ordre de grandeur, au rythme de ce projet) :

| Lot | Charge |
| --- | --- |
| v0.1 passif sur la VM Eidolon : collecteurs journald, ports et compteurs ; stockage durable ; API de statut ; badge ; tests | 2 à 3 sessions |
| v0.2 : CrowdSec en détection, recopie de trafic et Suricata en IDS, mesures | 3 à 5 sessions, plus les essais sur le matériel réel |
| Réponse active : agent nftables à expiration, liste de protection, recette en réseau isolé | à planifier après la recette v0.2 |

## 8. Revue du code `darme.py` (`c417e66`)

Points positifs :
- aucune dépendance, aucune action ni capture ;
- `enforcement_enabled: false` ;
- sources nommées ;
- collision d'identifiant refusée ;
- horodatage avec fuseau obligatoire ;
- gris si une sonde n'est pas saine, et état initial non sain.

| # | Défaut | Preuve |
| --- | --- | --- |
| **R1** | `severity` n'est pas vérifiée : une chaîne `"critical"` est acceptée, puis `snapshot()` plante (`AttributeError`) | sonde `test_r1` |
| **R2** | une alerte critique non acquittée **passe au gris** dès qu'une sonde tombe, ce qui contredit le concept (« rouge, visible jusqu'à acquittement ») ; le test `test_bad_health_overrides_alert` fige ce comportement | sonde `test_r2` |
| **R3** | le tri compare le texte des horodatages : `07:30Z` passe avant `08:00+02:00` (06:00 UTC) | sonde `test_r3` |
| **R4** | aucun refus des caractères de contrôle (saut de ligne, ANSI) dans `subject`, `category` et `source` | sonde `test_r4` |
| **R5** | projection non bornée : 100 000 événements gardés en mémoire | sonde `test_r5` |

Mineurs :
- `ipaddress`, `json` et `timezone` sont importés mais pas utilisés ;
- l'en-tête n'a pas la ligne « Standard » et les accents manquent (standard
  de présentation) ;
- `intervention` est un attribut modifiable sans nature ni expiration ;
- l'acquittement n'a ni acteur, ni raison, ni date ;
- aucune protection contre les accès concurrents (acceptable tant que tout
  reste en mémoire) ;
- `subject` contient une adresse IP sans type : le module `ipaddress` est
  importé, mais pas utilisé pour valider.

Les corrections sont dans tes fichiers : je n'y touche pas sans
coordination (G141). Sondes :
`PYTHONPATH=src python3 -m unittest
docs/validation/2026-10-10/claude-darme-review/probes_darme.py` → 5 échecs à
`c417e66`, attendus jusqu'à correction.
