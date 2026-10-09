# C-TASK-G073 — Contre-revue de `qualification-check` (C-035)

Claude, 08/10/2026. Base : `0de804d` (src figé). Cible : `qualification.py`,
`qualification_io.py` et la commande CLI, sans modification.

```sh
python3 probes_g073.py <src figé>     # code 1 si une attente échoue → probes.txt (≈ 10 s)
```

Méthode :

- Chaque cas applique **une seule** modification à la fixture conforme.
- Le cas passe par la vraie CLI, dans un sous-processus surveillé par un
  *audit hook* Python : tout `connect`/`bind` de socket, toute ouverture en
  écriture, tout `mkdir`/`rename`/`remove` est relevé.
- On relève aussi : le code de sortie, le verdict sur stdout (ou son absence),
  le code d'erreur sur stderr, les octets et le mtime du rapport avant/après, et
  la non-création du `--state` passé.
- Ce n'est pas une copie de `tests/test_qualification.py` : les cas visent le
  contrat CLI/fichier et les limites croisées.

**Résultat : 40/40 attentes, et 1 écart à la documentation (G073-1).**

## Confirmé

- **Codes de sortie** : 0 `PASSED_SCOPE`, 2 `INCOMPLETE`, 3 `REJECTED`, sur les
  trois fixtures du dépôt.
- Les erreurs de fichier ou de structure donnent 2 avec stdout **vide** et un
  code constant sur stderr, comme documenté. Il faut donc lire stdout pour
  distinguer « incomplet » d'« illisible ».
- **Cas croisés** :
  - cas manquant → `INCOMPLETE` ;
  - `executed` incohérent, cas en double, origine mélangée (cas ou mesure),
    critères postérieurs au début → `REJECTED` ;
  - fuseaux différents comparés correctement, dans les deux sens ;
  - seuils modifiés sans recalcul de l'empreinte → `REJECTED`. Avec recalcul →
    `PASSED_SCOPE` : **limite documentée** (cohérence ≠ authenticité).
- **Limites** : mesure exactement au seuil (`<=` et `>=`) → acceptée ; 1500,0000001
  pour un seuil `<= 1500` → `REJECTED` ; mesure `null` → `INCOMPLETE`.
- **Types** : booléen `true`, entier de 400 chiffres, unité incohérente (mesure ou
  seuil), `error_rate > 1`, champ `validated` et horodatage sans fuseau →
  `REPORT_MALFORMED`. Le suffixe `Z` est accepté.
- **JSON** : clé dupliquée, `NaN`, BOM, UTF-16, imbrication > 8 →
  `REPORT_MALFORMED` ; 2 Mio → `REPORT_TOO_LARGE`.
- **Fichiers** : FIFO (sans blocage) et dossier → `REPORT_NOT_REGULAR` ; lien
  final et fichier absent → `REPORT_UNAVAILABLE`.
- **Course** : une réécriture de même taille pendant la lecture → `REPORT_CHANGED`.
- **Isolation** : sur les 40 cas, aucun socket, aucune écriture, `--state` jamais
  créé, rapport inchangé, ni trace Python ni chemin dans stderr.
- **Sortie humaine** : un saut de ligne, ESC ou BEL placé dans `scope.statement`
  est neutralisé : aucune ligne `[OK]` forgée.
- **Drapeaux** : `authorizes_execution` et `telemetry_authenticated` restent
  `false` ; `report_sha256` est bien l'empreinte des octets lus.

## Écart

- **G073-1 (faible) — critères fixés au même instant que le début de l'essai.**
  - Cas : `criteria.fixed_at = run.started_at` (`2026-10-05T15:00:00+02:00`
    dans les deux champs).
  - Documentation : « `fixed_at` doit **précéder** `started_at` », donc `REJECTED`.
  - Observé : `PASSED_SCOPE`, parce que le code teste `fixed > started`.
  - Cette ligne vient de **mon** module d'origine (G002) ; Codex ne l'a pas
    modifiée.
  - Correctif minimal proposé : `fixed >= started` → `CRITERIA_AFTER_RUN`, plus
    un test. Une égalité de seconde ne prouve pas que les seuils précédaient les
    premières observations. À défaut, corriger la documentation en « au plus
    tard au début ».

## Limites

- Un verdict cohérent n'authentifie jamais les mesures, comme documenté.
- L'audit hook voit les opérations Python, pas les appels système d'une
  extension C.
- Essais en root, sur système de fichiers local.
