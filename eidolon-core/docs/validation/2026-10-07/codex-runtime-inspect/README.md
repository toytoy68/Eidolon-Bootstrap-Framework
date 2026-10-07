# C-022 — diagnostic local de reprise

Codex/GPT, 07/10/2026. Base 5545c56 (arbre de coordination publié a1669eb).
Python 3.12.14/Linux ; aucun fournisseur ou machine utilisateur contacté.

`PYTHONPATH=src python -m unittest tests.test_runtime_inspect tests.test_invocation_budget tests.test_recovery tests.test_research_runtime -q`

**62 tests réussis**, dont 15 nouveaux diagnostics. Trace : targeted-tests.txt.

Vérifiés : aucune initialisation Store/Runtime ni création de verrou ; capture
NEW/terminale/RETURNED/effet inconnu ; verrous détenus puis libres, dont un vrai
processus spawn indépendant ; reçu non lu/adopté ; symlink/FIFO/marqueur invalide ;
annulation intercalée sans changement de révision détectée ; budget incohérent,
épuisé ou historique non borné ; JSON invalide/surdimensionné ; copie de revue
refusée ; formats JSON/humain et données privées absentes. Comparaison des
fichiers avant/après les inspections, état conservé.

La présence d’un fichier n’en valide pas le contenu. Les sondages de fichiers
ne forment pas une transaction avec SQLite et aucun effet externe n’est déduit.
La garde recherche n’est pas auditée par ce diagnostic. Pas de recette Windows,
NFS ou arrêt électrique. [Contrat](../../../RUNTIME-INSPECTION.md).
