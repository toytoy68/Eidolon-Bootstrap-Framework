# Validation C-008d — copie de restauration réservée à la revue

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Python 3.12.14/Linux.
Base `1489898a984b323bd5cfef44479b3f706127065f`,
[empreintes des sources testées](source-hashes.json).

Exécuté depuis eidolon-core/, avec PYTHONDONTWRITEBYTECODE=1 :

```sh
PYTHONPATH=src:. python -m unittest tests.test_recovery -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.recovery_demo
PYTHONPATH=src:. python -m examples.recovery_demo --format human
```

[16 tests ciblés](targeted-tests.txt), [suite complète](core-tests.txt) :
386 découverts, **380 réussis / six intégrations mémoire opt-in sautées**,
99,827 secondes. [Démo JSON](demo.json) et [humaine](demo-human.txt), exécutées
sur des états temporaires différents : accord APPROVED conservé comme historique,
source inchangée, zéro redémarrage fictif et Core refusé sur la copie.

## Cas vérifiés

- Lignes missions/événements/reçus identiques après copie, identité renouvelée,
  base source inchangée en l'absence d'écrivain concurrent.
- WAL : deuxième mission commise dans le journal avant capture, troisième
  commise après capture mais avant backup. Source à trois missions, copie à deux,
  lecture de la deuxième mission possible dans le rapport historique.
- Refus de création/runtime/commandes/lecture ClientSync sur copie gardée,
  même avec ancienne/nouvelle identité et Store déjà construit. Garde en base
  suffisante si marqueur de dossier absent ; absence de migration sur la copie.
- Annulation de publication : fichier pending conservé et ouverture Store
  interdite ; fichier concurrent jamais écrasé. Aucun écrasement de destination,
  copie sous répertoire source ou migration d'un ancien schéma.
- Deux processus os._exit : avant publication et après publication avant
  réponse. Aucun runtime autorisé ; après publication, inspection possible.
- Volume/budget backup dépassé, source/version/acteur invalide, inspection
  absente/non historique et incohérence d'identité refusés.
- Ancien succès et accord explicitement historiques ; requête/contexte/résultat
  brut exclus du rapport de mission. Monde de simulation non copié.
- CLI sans Runtime et exception SQLite nommée, sans fuite du message brut,
  avec incertitude conservée. API Python internes non converties.

Les tests d'intégration Memory Engine restent sautés ; aucun GPU, VM100, NAS,
Windows, modèle réel ou service personnel contacté. Aucune coupure électrique
qualifiée. Les tests Web de la suite emploient leurs fixtures locales.
La garde ne couvre pas SQL brut, anciens binaires ou restauration manuelle hors
outil. La copie ne réunit pas les artefacts ni effets externes ; aucune
réactivation ou promesse d'exécution exactement une fois.
