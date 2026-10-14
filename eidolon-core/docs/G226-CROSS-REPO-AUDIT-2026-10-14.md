# G226 — Audit transversal code et architecture (14 octobre 2026)

Statut : revue statique ciblée des branches Core et Memory et lecture des résultats GitHub Actions. **Pas un audit exhaustif de chaque fichier ni une recette VM.** Aucune modification de production.

## Preuves de référence

- Core : CI run 38531549417, SHA 366ecce8, 1660 PASS, 6 SKIP, 5 warnings.
- Memory : CI run 38565669688, SHA 24081e4, 2300 PASS et 19 PASS sur le worker expérimental ; Qdrant run 38565669677, 46 PASS.
- Les commits postérieurs à ces SHAs doivent être qualifiés séparément.

## Défauts et risques classés

### P0 — Blocages avant déploiement du worker

**F01 — Verrou canonique optionnel** (Memory `core/indexing/worker_upsert.py`).
`apply_upsert(..., canonical_root=None)` emprunte explicitement la voie sans verrou. Un appelant de production mal configuré pourrait indexer pendant une modification Markdown. Le verrou ne couvre que les écrivains coopératifs. **Correction :** API de production séparée exigeant une racine et un verrou commun ; voie non verrouillée limitée aux tests.

**F02 — Confirmation Qdrant insuffisante pour la cohérence complète** (`qdrant_index.py:revision_for`, `worker_upsert.py`).
Le read-back vérifie identité et numéro de révision, pas une empreinte du contenu indexé. Deux contenus différents avec la même révision restent indiscernables. Le journal SQLite n'est pas avancé atomiquement avec Qdrant. **Correction :** inclure empreinte canonique et identité de génération dans le payload, comparer lors du read-back, puis transition journal sous protocole de reprise explicite.

**F03 — TOCTOU du lecteur Markdown** (`worker_canonical.py`).
`has_symlink_component`, `is_file` et `read_bytes` sont des opérations distinctes. Une substitution entre les contrôles peut modifier le fichier lu. Le verrou coopératif réduit le risque, mais pas les écrivains externes. **Correction :** lecture via descripteur avec `O_NOFOLLOW`, vérifications `fstat`, et contraintes sur les répertoires parents.

**F04 — Worker expérimental distinct du chemin Qdrant réel** (`worker.py`, `worker_upsert.py`).
Les 19 scénarios testent `IndexWorker` expérimental, alors que l'upsert Qdrant utilise une autre API. **Correction :** exécuter le même contrat de sécurité contre un adaptateur du chemin réel, puis recette isolée crash/replay.

### P1 — Fiabilité et sécurité applicative

**F05 — Sentinelle ABSENT par identité d'objet** (`reconcile_plan.py`).
`ABSENT` est la chaîne `"ABSENT"` et le code utilise `is ABSENT`. Une chaîne égale mais construite séparément peut ne pas être le même objet : classification ambiguë ou accès erroné à `.revision`. **Correction :** type enum/sentinelle unique validée à l'entrée ; ne jamais traiter une chaîne arbitraire comme une preuve d'absence.

**F06 — Détection de dérive basée seulement sur révision** (`reconcile_plan.py`).
La réconciliation manifeste compare `indexed.get(id)` à `current.revision` sans empreinte indexée. Une corruption à révision identique peut passer inaperçue. **Correction :** comparer revision + digest et génération, puis programmer un rebuild si l'état est inconnu.

**F07 — Budget Web : horloge validée à la réservation mais pas à la clôture** (Core `web_budget.py`).
`reserve` rejette NaN/infini ; `finish` enregistre `float(self.clock())` sans vérification de finitude. **Correction :** fonction d'horloge centralisée et tests de clôture.

**F08 — DNS : plafond de huit threads mais saturation durable possible** (Core `web_transport.py`).
Le sémaphore limite les threads bloqués, ce qui évite leur accumulation ; si les huit résolveurs ne terminent jamais, les nouvelles requêtes restent refusées jusqu'à libération des slots. **Correction :** supervision de santé, métriques de saturation et résolveur isolé/annulable si nécessaire.

**F09 — Contrat du bridge Memory encore dépendant du contexte** (Core `memory_bridge_client.py`, `memory.py`).
Le transport valide l'enveloppe, puis `validate_context` vérifie les données. La recette réelle Core ↔ Memory (6 tests Core ignorés) reste à effectuer. **Correction :** tests d'intégration authentifiés, dégradation, taille limite, timeout et provenance.

### P2 — Couverture et exploitation

**F10 — Visibilité opérationnelle partielle** (DARME, Web, VM).
DARME n'est pas un IDS/EDR, les états INDEX_* ne sont pas tous issus d'une télémétrie Qdrant réelle, et l'accès MCP/VM n'est pas qualifié. **Correction :** diagnostics de bout en bout, sauvegarde/restauration, alerte sur états inconnus.

## Ordre de correction proposé

1. F01/F02/F03/F04 : worker de production verrouillé, empreinte et read-back, lecteur sécurisé, contrat 19 scénarios sur le même chemin.
2. F05/F06 : sentinelle d'absence typée et cohérence index digest+revision.
3. F07/F08 : horloge Web, saturation DNS et tests.
4. F09/F10 : recette Core ↔ Memory ↔ PC et observabilité.

## Conclusion

Les tests actuels valident beaucoup de composants, mais ne prouvent pas l'atomicité Markdown ↔ SQLite ↔ Qdrant ni la résilience de l'ensemble déployé. **J2 reste bloqué pour la production** tant que F01–F04 ne sont pas corrigés et testés. Pas de fusion main, aucune suppression automatique.
