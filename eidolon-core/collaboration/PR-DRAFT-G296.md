# PR (brouillon) — G296 : étude Cornelius et trois premiers lots, sans branchement

Base : `feat/eidolon-core-v0.1` @ `2891e20` · Branche : `claude/g296-cornelius-study` · **Ne pas fusionner dans main.**
À ouvrir en *Draft* : je n'ai pas pu créer la PR moi-même (jeton `gh` refusé dans ma session).

## Contenu
- `docs/ETUDE-CORNELIUS-G296.md` : comparaison piste par piste, licences, budgets mesurés, plan par lots.
- `desktop/connected/src/duplex-voice.js` + `tests/duplex-voice-g296.test.js` : contrôleur de coupure de
  parole (V2-a), **non intégré à `app.js`**.
- `tools/evaluation/wake_eval_g296.py` + `tests/test_wake_eval_g296.py` : mesure des mots d'appel (V1-a).
- `src/eidolon_core/module_cache.py` + `tests/test_module_cache_g296.py` : cache des modules (M1-a),
  **importé par aucun module existant**.

## Garanties
- Aucun code Cornelius copié (PolyForm Noncommercial) : conception écrite de zéro, sources citées.
- `app.js` inchangé (`build.js --check`) ; aucun fichier existant modifié hors documentation et canal.
- Suites : voir C-MSG-C195.

## À valider avant de fusionner dans la branche de travail
- [ ] Relecture GPT des trois modules.
- [ ] Décision toytoy : ordre des lots V1-b/V2-b, données d'entraînement des mots d'appel (licences NC-SA).
- [ ] Mesures PC du §6 de l'étude avant tout branchement.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01EtmKEt6P3q6nMhKY8Ysc5a
