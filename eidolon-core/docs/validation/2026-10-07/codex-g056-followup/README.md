# C-024 — adoption mesurée de la proposition G056

Codex/GPT, 07/10/2026. Base intégrée 3e97f1f, arbre publié 0e0b5d9.
Le diff de Claude est adapté dans Runtime/Store : lecture SQL des seules
réservations, validation d’identité en entrée ; aucun schéma ou index ajouté.
La vérification relit toujours tous les ordinaux, limites et le nombre attendu.
Aucun cache ni point de contrôle incrémental ne masque les anciennes lignes.

## Banc reproduit ici

Le banc G056 est exécuté successivement, sans chevauchement entre les deux
variantes : sources avant depuis une archive propre 8c5f649, puis sources
modifiées. Python 3.12.14/Linux, historiques artificiels de trois événements
par invocation, même environnement. `before.txt` et `after.txt`.

| Réservations | Avant, médiane | Après, médiane |
| --- | --- | --- |
| 64 | 0,73 ms | 0,31 ms |
| 256 | 2,12 ms | 0,69 ms |
| 1024 | 8,03 ms | 2,80 ms |
| 4095 | 38,23 ms | 9,48 ms |
| 4095, quatre processus | 37,4–46,5 ms/appel | 9,8–11,0 ms/appel |

Les six altérations isolées restent `INVOCATION_BUDGET_INVALID`. Un retrait
cohérent compteur+événement reste accepté : limite déjà documentée, inchangée.
À 64, le gain absolu reste faible ; les gros historiques bénéficient le plus
de cette réduction. Aucun temps cumulé réel d’une mission 4096 appels n’a été
mesuré, ni qualification de performances sur VM/Windows.

Le lecteur de diagnostic C-022 est aussi précisé : un détail de réservation
valide dépassant sa borne 16 Kio est `UNAVAILABLE`, sans budget restant affiché,
plutôt que déclaré corrompu. Le moteur d’exécution ne reçoit pas cette borne.

Validation ciblée : voir `targeted-tests.txt`. Suite budget, inspection et
missions recherche, données synthétiques. Les preuves Claude restent intactes.
