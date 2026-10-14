# G229 — Contre-revue préparée pour le retour de Claude

Auteur : Codex/GPT, 14 octobre 2026. Disponibilité annoncée par toytoy : vers 22 h 58 Europe/Paris.
Fiche de travail ; aucune session démarrée et aucune réponse présumée.

## Périmètre prioritaire

1. Memory G229 : essayer de falsifier la preuve du point à révision égale ; tester changement d'alias, digest, modèle, génération et absence de preuve historique. Vérifier le compromis de confidentialité du SHA des octets du fichier canonique complet, conservé uniquement dans le nouvel upsert vérifié.
2. Lecteur canonique : substitutions fichier/répertoire pendant l'ouverture et la lecture, FD correctement fermés, pas de suivi de symlink/FIFO. Examiner les limites avec un écrivain non coopératif.
3. Verrou : vérifier que tout appel public d'upsert exige la racine. Étendre au vrai chemin les scénarios concurrence/crash/accusé perdu des 19 tests expérimentaux, sans les affaiblir.
4. Reprise : proposer puis qualifier une transition de journal après preuve canon/index complète, en conservant l'incertitude après crash. Aucun nettoyage/suppression automatique.
5. Fusion Core : contre-vérifier I1/W1 conservés, modules C149–C178, monitoring distant/GPU non activés, tests historiques attendus actualisés et absence de perte des changements GPT.
6. Qualification : examiner les logs CI sur les SHAs effectivement publiés ; distinguer les limitations locales AF_UNIX, age, Chromium et les vrais défauts. Ne pas attribuer une recette VM aux tests isolés.

Les résultats locaux et blocages sont dans PROJECT-STATUS.md et le rapport G229 Memory.
Publication autorisée et effectuée : Memory `d74d772`, Core `ff0b65e` (deux parents, C178 conservé). Les commits documentaires ultérieurs ne changent pas le code testé.


## Complément G230

Memory `180f3a7` ajoute `worker_journal.py` et `ChangeJournal.advance_verified`.
La contre-revue doit examiner la clôture après accusé perdu, le fsync avant récupération
INTENT, la comparaison complète de la ligne SQLite et les limites de coordination
avec les écrivains de droits/alias. Le contrat historique de 19 scénarios reste distinct.
