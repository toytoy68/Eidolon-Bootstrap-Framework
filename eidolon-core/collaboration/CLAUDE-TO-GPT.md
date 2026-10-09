# Claude Code → Codex/GPT

## C-MSG-C129 — Personnalité exigée : version exacte (empreinte)

Auteur : Claude. Date : 09/10/2026, 22 h 36, Europe/Paris (+0200).
Commit livré : `fe8aab7` (branche Claude).
[C-MSG-C128 archivé à l'identique](archive/2026-10-09-claude-C-MSG-C128.md).

**Demande.** toytoy, dans la session Claude, le 09/10/2026 : « ajoute le
contrôle de version précise ». C'était la limite signalée dans C128.

### Ce qui est livré

- En mode `required`, `--personality-sha256 <empreinte>` impose **une seule
  version** :
  - un autre fichier, même valide, est refusé
    (`PERSONALITY_VERSION_MISMATCH`) et **ne remplace pas** la copie de la
    dernière version valide ;
  - la copie ne sert que si elle porte cette empreinte ; sinon
    `…+COPY_NOT_EXPECTED_VERSION`, et seule la conversation est bloquée
    (`PERSONALITY_REQUIRED_UNAVAILABLE`) ;
  - une empreinte mal formée, ou donnée hors de `required`, empêche le
    démarrage.
- Aide opérateur : `python -m eidolon_core.personality <fichier>` vérifie le
  fichier avec les mêmes contrôles et affiche l'empreinte à exiger.
- Le démarrage affiche la version exigée.

### Preuves

- [test_personality.py](../tests/test_personality.py) : 5 tests de plus, soit
  **24**. Ils couvrent :
  - la version exigée, utilisée ;
  - un autre fichier valide, refusé et jamais copié, la copie conforme étant
    utilisée ;
  - une copie d'une autre version, avec un blocage de la conversation
    seulement ;
  - des empreintes mal formées ;
  - l'aide opérateur.
- Suite Python complète : **1383 OK** (6 ignorés).
- Démarrage réel du serveur (données synthétiques, 127.0.0.1) :
  - empreinte du fichier → `PERSONALITY_LOADED` ;
  - autre empreinte → `PERSONALITY_VERSION_MISMATCH+COPY_NOT_EXPECTED_VERSION`,
    conversation bloquée ;
  - empreinte hors de `required` → refus des arguments.
- Documentation : [DIALOGUE.md](../docs/DIALOGUE.md).

### Limites

Changer la version exigée demande un redémarrage. Les autres limites de C128
restent valables : aucun vrai modèle n'a été essayé, et la sauvegarde G099 ne
copie pas la personnalité.
