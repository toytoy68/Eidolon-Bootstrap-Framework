# C-TASK-G061 — Contre-revue des diagnostics C-022/C-025

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Base publiée : `9709dece29fa6815ad93301d3edc7a2887c5d736`.
Lire le dernier GPT-TO-CLAUDE et les contrats RUNTIME-INSPECTION/RECOVERY-REVIEW.

## Périmètre

Rapport et sondes dans `docs/validation/2026-10-07/claude-g061/` seulement.
Pas de modification des sources Core ou du client. Après G057–G060, ou si un
lot précédent est bloqué par une dépendance non disponible.

Vérifier indépendamment les frontières suivantes, sur états synthétiques :

- runtime-inspect : état absent, capture concurrente, verrou détenu par un
  autre processus puis libéré, reçu présent mais non vérifié, RETURNED après
  interruption ; aucun lancement, création ou mutation SQLite/fichier.
- Budget invalide/exhaustion/ancien sans limite, événement trop grand pour
  l’audit borné ; aucune autorisation de reprise ni résultat privé exporté.
- recovery-inspect : rapport ancien sans capture_semantics, métadonnées
  contradictoires, JSON malformé/dupliqué/non fini, limites de volume/nombre/SQL.
- CLI JSON/humain et codes de sortie, copies qui restent REVIEW_ONLY, absence
  de rapport partiel présenté comme une inspection complète.

Distinguer correction de diagnostic et contournement effectif du Runtime.
L’actor/reason d’une copie de revue sont des annotations locales, pas un export
anonymisé. Une réécriture SQL cohérente ou l’absence d’effet externe ne sont
pas démontrables par ces diagnostics. Tester les promesses documentées.

## Livraison

Commit distinct, base exacte, sondes autonomes, résultats et sévérités justifiées.
Distinguer tests exécutés et conclusions par lecture. Aucun main, déploiement,
VM utilisateur, fournisseur réel ni modification Memory Engine. La demande de
toytoy autorise cette suite locale sans nouveau feu vert ; le fichier ne démarre
pas une session Claude.


## Complément G080 — consultation CLI C-027

Base additionnelle publiée : `53ece44ae9b44e31d0bbaef8a57be762926f8f60`.
Les diagnostics initiaux peuvent rester sur 9709dec. Sur cette nouvelle base,
contre-vérifier client-missions/client-snapshot/client-poll : fichier courant
préservé, schéma ancien/table requise manquante refusés sans migration, état
bêta incomplet refusé, pagination/reset inchangés. Comparer aussi état absent,
copie historique et capture sous écrivain concurrent sur corpus temporaire.
Les protocoles n’ont pas changé ; aucune modification Core demandée.
