# PR (brouillon) — G296 : étude Cornelius et trois premiers lots, sans branchement

Base : `feat/eidolon-core-v0.1` @ `2891e20` · Branche : `claude/g296-cornelius-study` · **Ne pas fusionner dans main.**
À ouvrir en *Draft* : je n'ai pas pu créer la PR moi-même (jeton `gh` refusé dans ma session).

## Contenu
- `docs/ETUDE-CORNELIUS-G296.md` : comparaison piste par piste, licences, budgets mesurés, plan par lots.
- `desktop/connected/src/duplex-voice.js` + `tests/duplex-voice-g296.test.js` : contrôleur de coupure de
  parole (V2-a), **non intégré à `app.js`**.
- `tools/evaluation/wake_eval_g296.py` + `tests/test_wake_eval_g296.py` : mesure du mot d'appel unique « Eidolon » (V1-a).
- **Suppression de « Dis-moi »** (décision opérateur du 23/10) : `auto-voice.js`, `communication.js`, `index.html`,
  `app.js` régénéré, `auto-voice.test.js` (gardes de non-régression), notice `LIRE-MOI-G286.txt`, note dans
  `VOICE-AUTO-G282.md`.
- `docs/LICENCES-VOIX-G296.md` : inventaire des licences, composants NC isolés.
- `src/eidolon_core/module_cache.py` + `tests/test_module_cache_g296.py` : cache des modules (M1-a),
  **importé par aucun module existant**.

## Garanties
- Aucun code Cornelius copié (PolyForm Noncommercial) : conception écrite de zéro, sources citées.
- Seul changement de comportement : « Dis-moi » ne réveille plus Eidolon. Les trois modules G296 ne sont pas branchés.
- Suites : voir C-MSG-C195.

## À valider avant de fusionner dans la branche de travail
- [ ] Relecture GPT des trois modules.
- [x] Décisions du 23/10 : ordre (mot unique, coupure, veille Windows), licences NC à titre d'étude, VM100.
- [ ] Avant activation : non-régression, seuil de faux positifs, latence et écho réel validés sous Windows.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01EtmKEt6P3q6nMhKY8Ysc5a
