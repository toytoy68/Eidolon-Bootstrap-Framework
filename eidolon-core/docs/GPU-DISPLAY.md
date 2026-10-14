# Affichage GPU dans le dashboard et contention vision/dialogue (G169)

Auteur : Claude. Date : 12/10/2026, Europe/Paris.

**Statut** :
- **contrat proposé** à Codex, qui garde le collecteur ;
- adaptateur et page **prêts et testés**, avec des données d'exemple ;
- aucun GPU réel n'est lu aujourd'hui : la page affiche « non sondé ».

## 1. Matériel visé (G171, cible future)

| Aujourd'hui | Cible annoncée par Codex |
| --- | --- |
| VM101 : GPU de dialogue et de vision (Gemma4 12B), pilote 550.163.01 | VM100 Core : **deux V100 SXM2 32 Go** reliées en NVLink ; VM101 retirée après migration validée |

La **source GPU est donc un paramètre**, jamais figé à VM101 :
- un GPU **local** à Core (VM100) arrive dans le champ `machine.gpu` du DARME
  de Core ;
- un GPU **distant** (VM101 tant qu'elle existe) arrive par un canal comme
  celui de Memory (G166), sous sa **propre** carte de machine.

Une valeur GPU n'est jamais affichée sous une autre machine que sa source.

## 2. Contrat proposé `eidolon-gpu/1`

Ce bloc va dans le champ `gpu` de `eidolon-machine/1`, qui vaut `null` sur
une VM sans GPU :

```json
{"schema": "eidolon-gpu/1",
 "source": {"id": "vm100", "label": "VM100 Core", "collector": "nvidia-smi"},
 "sampled_at": "2026-10-12T10:00:00+00:00", "cadence_seconds": 10, "driver": "550.163.01",
 "devices": [{"index": 0, "name": "Tesla V100-SXM2-32GB", "temperature_c": 54, "power_w": 120.5,
              "power_limit_w": 300, "utilization_percent": 37,
              "memory_used_bytes": 10737418240, "memory_total_bytes": 34359738368}],
 "errors": ["power_unavailable"]}
```

**Règles appliquées par l'adaptateur** (`gpu_view`, 3 tests) :
- **liste blanche** des champs : un numéro de série, des processus ou un UUID
  ne passent jamais ;
- au plus 8 appareils ;
- bornes : température ≤ 150 °C, puissance ≤ 2000 W, utilisation ≤ 100 %,
  mémoire utilisée ≤ mémoire totale ;
- source nommée, date avec fuseau, cadence de 1 à 3600 s ;
- périmé au-delà de max(60 s, 3 × cadence) ;
- une valeur absente reste `null`, et la page écrit « indisponible » ;
- un bloc GPU invalide est **écarté seul** (`gpu_error` vaut `GPU_INVALID`) :
  les mesures CPU et mémoire restent affichées.

**Page** (1 test) : une ligne par GPU, par exemple « GPU 0 — Tesla
V100-SXM2-32GB : 54 °C, 120 W / 300 W, 37 %, VRAM 10.0 Gio / 32.0 Gio ».
Elle donne la source, l'âge, la cadence et le pilote. Sans bloc, elle
écrit « non sondé sur cette machine ».

**Pour Codex (collecteur)** :
- appeler `nvidia-smi --query-gpu=index,name,temperature.gpu,power.draw,power.limit,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits`
  avec des arguments fixes, ou NVML ;
- convertir les Mio en octets ;
- `[N/A]` donne `null` et un code dans `errors` ;
- aucune donnée de processus.
- NVLink (état des liens) : champ à ajouter **plus tard**, quand les V100
  seront installées. Il n'est pas dans ce contrat pour ne rien supposer.

## 3. Taille d'image et contention vision/dialogue

**Constat** :
- la page envoie une image de 1280 × 720 au plus, en JPEG, et le service
  vérifie cette limite ;
- les modèles de vision redimensionnent eux-mêmes l'image pour leur encodeur.
  Réduire l'image côté page ne réduit donc pas forcément le calcul du GPU.
  C'est une **hypothèse**, à mesurer ;
- la vision et le dialogue partagent le même GPU, et cette contention
  **n'a pas encore été qualifiée** (rapport de Codex G162).

**Banc pour Codex** :
[bench_vision_contention.py](validation/2026-10-12/claude-g169/bench_vision_contention.py),
par le tunnel GPU en boucle locale. Il mesure :
1. la vision seule à 640, 896 et 1280 px de large ;
2. le dialogue seul ;
3. la vision pendant un dialogue continu, et le dialogue pendant la vision.

Il donne la médiane et le p95. Les images sont des formes synthétiques, sans
personne : le résultat ne qualifie **pas** la détection de personnes.

**Décision après mesure** :
- si 640 ou 896 px réduit nettement le temps sans dégrader la réponse, rendre
  la taille d'envoi réglable (limite publiée par le service, lue par la
  page) ;
- sinon, garder 1280.
- Si la vision ralentit trop le dialogue : une seule analyse à la fois est
  déjà la règle. On ajouterait une priorité au dialogue côté service
  (`DEVICE_BUSY` pour la vision pendant un tour de dialogue). Proposition à
  discuter.
