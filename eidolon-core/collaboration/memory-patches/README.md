# Patchs Claude pour Eidolon Memory Engine (G178)

Claude a reçu l'accord de toytoy pour travailler dans Memory (12/10/2026, vers 14 h 20).
Sa session peut **lire** le dépôt `toytoy68/Eidolon-Memory-Engine`, mais pas y pousser :
l'attache en écriture a été refusée par les permissions de la session. Les commits
sont donc livrés ici sous forme de patchs `git format-patch`, à appliquer par Codex
ou à pousser dès que l'accès en écriture est accordé.

**Base** : `f7136239b702c70b9c0021f57a27208075fd79f3` (base Memory de G178).

```sh
git checkout -b claude/memory-g178 f7136239b702c70b9c0021f57a27208075fd79f3
git am /chemin/vers/eidolon-core/collaboration/memory-patches/0001-*.patch   # puis les suivants, dans l'ordre
python3 -m pytest -q tests
```

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0001 | A5-02 : politique de passage v3, contexte gauche et marqueurs de négation signalés | 2 024 tests Memory réussis ; sonde d'audit du 05/10 : « Ne pas acheter la V100 cette semaine. » complet |
