# Consultations CLI strictement en lecture seule — C-027

Codex/GPT, 07/10/2026. Base locale ae24135, équivalent publié 5b465532.
La préparation du parcours opérateur C-026 a révélé deux mutations :
[sondes avant correction](before.txt). Même une liste sur schéma courant
changeait les octets SQLite ; une capture sur table command_receipts absente
la recréait. Cause : construction du Store, PRAGMA et migration additive.
Aucun modèle ni outil exécuté par ces consultations.

Les trois branches client-missions/client-snapshot/client-poll passent maintenant
au ReadOnlyStore existant de l’API. Pas de nouveau protocole ni changement de
curseur ; état ancien, incomplet ou de restauration refusé avant consultation.
Le comportement d’initialisation des autres commandes reste hors de ce lot.

[59 tests ciblés réussis](targeted-tests.txt), dont six nouveaux : absence de
Store/Runtime, comparaison de tous les fichiers source octet pour octet,
absence de création sur dossier manquant, refus de schéma ancien/table absente,
refus du marqueur bêta et format humain. Les tests existants de pagination,
capture/poll et restauration passent également. Corpus temporaires seulement.

```sh
PYTHONPATH=src:. python -m unittest tests.test_cli_readonly tests.test_client_sync tests.test_mission_list tests.test_recovery -v
```

Le délai SQL est coopératif ; les limites de projection des protocoles existants
restent applicables. Pas de nouvelle garantie sur I/O physique, NFS, rollback
cohérent ou ancien binaire. Aucun serveur utilisateur ni changement Memory Engine.
