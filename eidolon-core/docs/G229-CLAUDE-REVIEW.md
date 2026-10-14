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


## Complément G231

Memory `855a9eb` ajoute `ReconciliationScan` et `ensure_upsert_intent` : examiner
l'intervalle entre commit du journal et commit du curseur, les modifications derrière
le curseur, le contexte du checkpoint, la pause sur file pleine et le sens limité
de COMPLETE. Les deux captures complètes sous verrou nécessitent une mesure sur le
corpus réel ; la recherche inverse des orphelins n'est pas couverte par ce lot.

## Complément G232

Memory `e4d38ee` ajoute `OrphanScan`, `inventory_page`, `proven_absent` et
`has_pending`. Revue indépendante restante : preuve d’absence sans confondre
ENOENT feuille/racine, atomicité page/curseur, revalidation après réapparition,
portée de EXHAUSTED sur un index vivant et coordination avant toute future
suppression. Deux morts réelles et 44 tests du lot passent ; aucune qualification
serveur/VM ni suppression réelle n’est revendiquée. [Bilan](PROJECT-STATUS.md).

## Complément G233

Memory `53f7bf0` : examiner la pagination à borne fixe, la reprise des pages après
effet/avant checkpoint, le passage des revues sans famine et le traitement explicite
d’InvalidMemory. Contre-revue du cycle FIRST/SECOND/CANONICAL/ORPHANS/FINISH,
reports et conditions d’activité, redémarrage des scans après bascule de génération.
246 tests ciblés et 40 cas G233 passent ; arriéré >1000 et arrêt réel éprouvés.
Le contrat historique complet/découpeur, les mesures de l’hôte et la recette serveur
restent distincts. Aucun runtime activé. [Bilan](PROJECT-STATUS.md).
