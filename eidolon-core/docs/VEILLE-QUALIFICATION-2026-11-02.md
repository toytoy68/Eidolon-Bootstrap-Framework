# Veille : preuves temporelles et reprise des sessions — 2 novembre 2026

Base Core `04c384ddad2fb18f61afbd490ea0f913e7d0b509`, Memory
`0691e68b452fb79c671ab10b9a6c054a67e6d4d3`. Branche isolée
`codex/veille-evidence-session-20261102`. Aucune fusion ni modification de
production. La X399 est restée éteinte ; les inférences synthétiques ont utilisé
l'Ollama existant de VM100, dans des états de conversation temporaires.

## Changements retenus

- Quatre tests de vraie restauration SQLite signée : propriétaires A/B,
  idempotence, révocation, rotation et refus de changement de liaison de profil.
- Deux tests de traversée disque Memory → HTTP en boucle locale → validation
  Core → prompt. Dates présentes et absentes sont conservées, sans les inventer.
- Le banc G294 accepte maintenant des notes structurées avec temporalité et
  provenance, tout en gardant ses anciennes paires `[id, texte]`. Une liste
  explicite de champs interdit d'injecter une réponse attendue dans les preuves.
- Le calcul des scores reconnaît « ne peux donc pas affirmer », sans revenir au
  défaut ancien qui acceptait toute phrase contenant « pas ». Sept tests de
  métadonnées et de notation couvrent ces changements.
- Deux jeux de six cas, réponses brutes, résultats et essai de consigne rejeté
  sont versionnés. Les réponses attendues ne sont pas envoyées au modèle.

Le correctif de transmission des dates Hindsight
[`7b46a07`](https://github.com/vectorize-io/hindsight/commit/7b46a07c82f997903230f0fb33deafe9dfd2e22b)
et les corrections de reprise Hermes
[`10d34c5`](https://github.com/NousResearch/hermes-agent/commit/10d34c53d9678e9a8e6ce9887b598136a663298c)
ont motivé les scénarios. Aucun code de ces projets n'a été copié.

## Tests exécutés

Sur le code final : **123 tests réussis, 34 sous-tests, 13 ignorés**, 32,29 s.
Les 13 ignorés appartiennent à l'ancienne suite `test_backup_restore.py`, dont
la classe exige `age` absent du conteneur. Les quatre nouveaux scénarios de
restauration utilisent une vraie signature OpenSSL et **ont tous été exécutés**.
Ce résultat n'est pas une nouvelle exécution de la suite Core complète.

Python 3.12, pytest 9.2.0, PyYAML 6.0.3, qdrant-client 1.15.1, Memory présent
sur PYTHONPATH. Commande depuis `eidolon-core/` :

```bash
python -m pytest -q -ra tests/test_veille_session_restore.py \
  tests/test_veille_temporal_bridge.py tests/test_veille_holdout_metadata.py \
  tests/test_beta_runtime_g270.py tests/test_bridge_memory.py \
  tests/test_memory_bridge_boundary.py tests/test_conversation_api.py \
  tests/test_backup_restore.py tests/test_claude_holdout_g294.py \
  tests/test_claude_evidence_g294.py tests/test_dialogue.py tests/test_dialogue_profiles.py
```

Neutraliser expérimentalement `_own` fait échouer le test de restauration
(lecture inter-client acceptée à tort). La mutation n'est pas conservée.
La restauration porte sur les conversations, pas sur un instantané global
incluant anciennes clés et autorisations. Aucun webhook ni reboot matériel testé.

## Inférences réelles : le prompt seul ne suffit pas

Modèle configuré existant : **gemma3:4b**, Ollama, température 0, seed 42,
num_ctx 8192, num_predict 512, think false, délai maximal 120 s,
max_prompt_bytes 24000. Empreinte du fichier de configuration privé :
`4ab421fe6292a08dfd858188895f645c490eac8f424ebea9a5bc191ad095ae21`.
Ni poids, ni configuration de service, ni mémoire réelle modifiés.

62 réponses générées : six cas de diagnostic, 22 G294 de référence, puis les
mêmes six cas, six cas supplémentaires figés avant cet essai et 22 G294 avec une
consigne candidate. Les sources sont fournies au banc : **la recherche Memory
elle-même n'est pas mesurée ici**. Le chemin est ConversationAPI → Dialogue →
ChatDialogueModel → décision Core. Pas de personnalité privée chargée dans le banc.

| Jeu | Référence | Consigne candidate | Lecture |
|---|---:|---:|---|
| Six cas temporels/sujet | 3/6 | 3/6 | Réponses identiques, aucun gain. |
| G294, 22 cas | 15/22 | 15/22 | Un gain sur une prévision de prix, mais régression de `action-request` : refus au lieu d'une proposition. |
| Six cas supplémentaires | Non exécuté | 3/6 automatique | Un refus correct sur conflit est mal reconnu : 4/6 après lecture manuelle. Ce n'est pas une comparaison avant/après. |

Les scores sont des contrôles automatiques de contenu, pas un taux universel de
vérité. La première notation des six cas donnait 2/6 : une abstention correcte
avec « donc » était rejetée. Les **mêmes réponses sauvegardées**, renotées après
correction, donnent 3/6 ; aucune amélioration du modèle n'est attribuée à ce calcul.
Un autre faux négatif demeure dans le jeu supplémentaire : « Je ne peux pas en
retenir un poids certain » exprime correctement l'incertitude. Les résultats
bruts sont conservés, sans adapter les réponses attendues aux sorties.

Trois défauts confirmés à la lecture des six cas :

1. Le fait est daté du **2 juillet**, le propos du **3 juillet**, l'import du
   **21 octobre** ; le modèle répond **3 juillet** malgré la date d'observation.
2. Une source non datée dit « hier » ; le modèle transforme sa date d'import
   **21 octobre** en date de réservation. La date réelle n'est pas établie.
3. La question porte sur **Zoé** ; la réponse cite une inscription de **Mila**
   sans expliquer que l'information demandée manque.

**Décision : consigne candidate non retenue.** Elle reste uniquement dans
[`prompt-candidate-not-adopted.patch`](veille-20261102/prompt-candidate-not-adopted.patch)
pour rendre l'expérience reproductible. `src/eidolon_core/dialogue.py` est
identique à la base dans cette proposition. Une seule exécution par condition :
aucune estimation statistique ni promesse de gain de latence.

## Suite technique

Priorité : sélectionner et contrôler le sujet, la preuve et les dates avant
génération. Formaliser la date du propos original pour les archives ; ne pas
assimiler import, observation et événement. Préparer un accès historique explicite
avec portée et droits : actuellement `BetaRuntime.recall_for` et le bridge restent
opérationnels au temps présent. Un futur garde-fou doit être évalué sur ces cas,
les 22 G294, des paraphrases supplémentaires et des contrôles négatifs, sans
accepter une citation seulement parce que son identifiant existe.

Reproduction, avec une configuration locale de modèle et un nouveau fichier sortie :

```bash
PYTHONPATH=src python tools/evaluation/dialogue_holdout_g294.py \
  --model-config /path/private-model.json \
  --cases tools/evaluation/veille_temporal_20261102.json --out /path/new-report.json
```

Les réponses sont dans `docs/veille-20261102/`. Le rapport transversal des cinq
projets est dans `toytoy68/Eidolon`, branche `research/veille-open-source-2026-11-02`.
