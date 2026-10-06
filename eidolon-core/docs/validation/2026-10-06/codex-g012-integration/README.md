# Revue G012 — consommateur client-sync/1

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Livraison Claude examinée :
`cc9a64bda4d9fd619cf25cf8607230d31ae3d7da`, sur base `1489898`.
Sources et tests lus dans une copie isolée ; prototype intégré intact comme
candidat local avec les trois écarts ouverts ci-dessous. Aucun transport ajouté.

## Vérifications exécutées

Depuis eidolon-core/, Node 24.19.0/Linux :

```sh
node --test desktop/prototype/tests/model.test.js desktop/prototype/tests/commands.test.js desktop/prototype/tests/sync.test.js
node docs/validation/2026-10-06/codex-g012-integration/probe.cjs
PYTHONPATH=src python docs/validation/2026-10-06/codex-g012-integration/build_core_fixture.py
```

[42 tests de logique réussis](node-tests.txt). Les 58 tests annoncés par Claude
incluent 16 tests UI que Codex n'a pas exécutés dans ce lot. Aucune validation
Windows ou navigateur réel par Codex. [Empreintes](source-hashes.json).

La [sonde](probe.cjs) vérifie la présence des défauts à cette révision, **pas leur
correction** ; elle devra échouer après réparation. [Résultat](probe-result.json).
La [capture hors catalogue](core-unsupported.json) vient d'un vrai Runtime local
sur demande synthétique, sans outil exécuté. Le script Python régénère une
capture équivalente avec d'autres identifiants/dates. Les deux autres sondes
emploient la trace G012 et un état dérivé explicitement construit.

## Écarts reproductibles, confiés à G016

| ID | Constat | Attendu |
| --- | --- | --- |
| G012-01 | Core émet objective_kind=null pour une demande hors catalogue, BLOCKED/CLARIFICATION ; validateEnvelope retourne INVALID_MISSION | Afficher cette capture valide sans inventer d'objectif |
| G012-02 | Après RESET_REQUIRED, un DELTA tardif de même époque fait passer la vue de séquence 1 à 11 pendant que reset reste en attente | Geler la vue et le curseur jusqu'au rechargement explicite ; traiter aussi SNAPSHOT tardif et resets concurrents |
| G012-03 | REVIEW_REQUIRED + cancel_requested=true affiche seulement « Annulation demandée — pas encore confirmée » | Garder la revue/effet inconnu comme état principal et la demande d'annulation comme information secondaire |

G012-03 concerne la priorité du libellé (reproduite). Le texte de sync-view
« attendre la capture CANCELLED » est aussi à corriger (lecture du code) :
une annulation n'efface pas la revue et n'annonce pas une future clôture certaine.
Ces défauts de prototype n'accordent aucune autorisation à Core et ne constituent
pas une exécution réelle. Ils empêchent de qualifier le client comme conforme.

La suggestion Claude from_sequence/from_event_count reste ouverte ; aucun
changement du protocole serveur livré ici. Le gel lors du reset peut être
réparé côté client sans cette extension. G014/G015 restent des contre-revues
séparées de C-008b et C-008c, pas une nouvelle tâche de raccordement réseau.
