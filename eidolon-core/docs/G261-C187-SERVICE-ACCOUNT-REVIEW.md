# Relecture C187 — compte de service Memory

Codex/GPT, 15 octobre 2026. Proposition Claude `0a0f897` lue ; Memory `a0cc112` inspecté. **Recommandation favorable au compte dédié ; unité proposée non déployable en l'état.** Adoption et activation restent distinctes, aucune VM modifiée.

## Blocage réel : le verrou est ouvert en écriture

`ContextualRecall.recall()` acquiert `exclusive_write()` sur persistent et, s'il existe, threads. `core/persistence.py` ouvre `.write.lock` en `a+b` même quand le fichier existe. Le montage `ReadOnlyPaths=/var/lib/eidolon-memory/canonical` interdit cet open. Précréer le verrou ne suffit donc pas. Le module `services/memory_bridge.py` documente déjà cette limite.

Sonde locale synthétique : véritable backend et ContextualRecall ; seule l'ouverture en écriture sous la racine temporaire est remplacée par `OSError(EROFS)`. Le rappel échoue avec errno 30 sur `memory/persistent/.write.lock`, mode `a+b`, dans les deux cas verrou préexistant/absent. Ce test reproduit l'appel incompatible, pas un vrai montage systemd. Aucun test chmod sous root ne constitue une preuve de droits du compte cible.

La construction du backend prépare aussi `history/pending-delete`. Préparer la disposition complète avant un service readonly, et vérifier les autres constructeurs, reste nécessaire.

## Ajustements avant recette

- Le compte système non root, code/venv root-owned et données privées hors du home personnel réduisent les droits du pont. L'administrateur conserve naturellement son pouvoir via sudo ; le compte ne protège pas contre root.
- Le `--root` du pont contient **`memory/persistent` et `memory/history`**. La copie doit préserver cette structure ; ne pas confondre racine du corpus et répertoire persistent.
- Le jeton reste accessible au processus par son environnement. Un EnvironmentFile root 0600 protège le fichier, pas le secret contre le service qui doit l'utiliser. Pont et worker au même UID ne constituent pas une isolation complète entre processus ; les restrictions systemd restent propres à chaque unité.
- Un lecteur et un écrivain doivent rester coordonnés sur **le même verrou**. Déplacer seulement le verrou du pont créerait une course. Étudier un emplacement commun d'état, ou la lecture d'un verrou préexistant sur Linux, avant de changer le contrat global.
- Ne pas ouvrir tout le canon en écriture dans l'unité pour masquer ce blocage. Ne pas adopter maintenant un second compte ou une nouvelle politique sans besoin démontré.
- Le préflight compare le propriétaire au compte de service attendu explicitement configuré. Le UID effectif du contrôleur de recette n'est pas nécessairement ce propriétaire ; il ne doit pas définir implicitement la politique.

## Suite attribuée

G262-1 à 6 préparent préflight, inventaire readonly, prototype de verrou, comparaison de copies, revue d'unité et cache hors ligne. G262-10 consolide les preuves et décisions avant activation. L'installateur effectif et la migration attendront la décision utilisateur et la résolution du verrou. Les scénarios existants, droits et journal de production ne sont pas modifiés par cette revue.
