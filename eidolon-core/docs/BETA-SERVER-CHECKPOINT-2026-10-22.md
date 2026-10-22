# Bêta serveur sans PC — point de recette du 22 octobre 2026

Statut : **recette partielle**, aucune validation globale de la bêta. Périmètre VM100 Core et VM110 Memory uniquement. Aucun test ni changement sur Windows, micro, caméra ou client PC.

## Vérifications exécutées

- VM100 et VM110 : aucun service systemd signalé en échec lors du contrôle ; les deux machines sont démarrées.
- VM100 : `eidolon-core-api`, `eidolon-memory-tunnel`, `eidolon-darme`, `eidolon-darme-ssh`, `eidolon-comm` et `ollama` actifs.
- VM110 : `eidolon-memory-bridge`, `eidolon-qdrant-beta`, `eidolon-dashboard`, `eidolon-collaboration`, `cloudflared`, collecteurs DARME et tunnels d'activité/embeddings actifs.
- Core checkout : `648192a` sur `feat/eidolon-core-v0.1` ; Memory checkout : `deda5b6`. Arbres Git locaux sans changements signalés au contrôle.
- Recette Core `python -m eidolon_core.beta_check --web-root desktop/connected` : **24/24 PASS**, fixtures synthétiques isolées.
- Recette Core `--profile research-archives` : **25/25 PASS**, fixtures synthétiques isolées.
- HTTP Core réel sur `127.0.0.1:8767` : page `/` répond 200 ; `/v1/health` sans jeton refuse 401 ; avec jeton privé 0600, réponse `eidolon-http-read/1`, `read_only`, `authorizes_execution=false`. Aucun secret consigné.
- VM110 : `services.memory_bridge --check-storage --read-only-storage` sur le stockage bêta canonique : `READY`, `issues=0`, `warnings=0`, `read_only_locks=true`.
- DARME sur VM100 : badge rouge, visibilité partielle, 1 alerte non acquittée, ingestion non suspendue, SSH sain ; `security_telemetry_installed=false`.

## Limites et blocages

1. Les recettes Core sont **synthétiques** : pas de preuve d'inférence LLM réelle, de rappel inter-VM sourcé, d'absence de mutation du corpus lors du rappel, ni de scénario de panne/reprise réel.
2. `pytest` absent des venv de service Core et Memory. L'appel aux tests ciblés Core échoue avant collecte (`No module named pytest`) ; aucun téléchargement ou installation n'a été tenté sur ces environnements. Prévoir environnement de test isolé pré-équipé.
3. L'alerte DARME restante n'est pas encore identifiée ; `security-telemetry` est déclarée absente. Déterminer si c'est une exclusion explicite acceptable en bêta ou une lacune bloquante.
4. Pas de sauvegarde/restauration sur copie, de tests de permissions multi-profils, de test de charge/endurance, ni de validation PC.
5. Services `active` ne signifie pas flux de bout en bout validé.

## Suite recommandée hors PC

- P0 : exécuter les suites de tests sur un environnement **isolé** et épinglé, sans installer pytest dans les venv de production.
- P0 : recette de rappel Core → Memory sur corpus de test non sensible, preuve de référence, refus des inconnus et absence de mutation canonique.
- P0 : vérifier sur copies isolées sauvegarde/restauration, reprise sans double effet et permissions refusées.
- P0 : qualifier l'alerte DARME et la source de télémétrie manquante ; ne pas acquitter sans analyse.
- P1 : mesurer latence, RAM, CPU, VRAM, consommation et endurance, après preuve fonctionnelle.

Aucun service n'a été redémarré ni modifié dans cette session. Aucun scénario destructif ou d'intrusion n'a été lancé. La recette PC reste explicitement différée.
