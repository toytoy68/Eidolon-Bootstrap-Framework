# G244 — Fraîcheur du rappel visible dans Core, 15 octobre 2026

Codex/GPT. Base Core 32de23354b72bb0fc79885ac84d5819020a97d70.
Pin Memory : 22f6a70e674da1b9c3291806e7d9d88cf1da779b, code G242/G243.

Le diagnostic `index_status` traverse le rappel, le bridge, le prompt et le
contexte affiché de la réponse. Le contrat Core vérifie les états, motifs,
génération et cohérence des digests. Un statut absent ou nul reste compatible
avec les fournisseurs lexicaux/anciens ; une déclaration incohérente rend la
mémoire indisponible pour le tour, sans arrêter le dialogue.

La note de contexte accepte un champ optionnel `memory_index` uniquement quand
la mémoire a effectivement été transmise au modèle. INDEX_STALE et
INDEX_UNVERIFIED rendent le contexte partiel, même avec zéro extrait. Une
mémoire exclue pour budget ne peut pas prétendre avoir transmis son diagnostic.
Les historiques sans ce champ restent valides.

L'interface PC affiche, selon le cas :

- « des changements de mémoire ne sont pas encore reflétés dans l’index » ;
- « la mise à jour complète de l’index mémoire n’a pas pu être vérifiée ».

Le prompt précise qu'un rappel vide n'est jamais une preuve d'absence dans la
mémoire, que le rappel est borné, et qu'un digest concordant n'établit ni vérité
factuelle ni pertinence sémantique. Ce sont des instructions, pas une validation
du comportement d'un modèle réel. Les citations restent limitées aux extraits
réellement transmis.

## Validation exécutée

28 nouveaux tests Python : validation, dialogue avec zéro extrait, mémoire
invalide, budget et intégration du vrai code Memory/Qdrant local. Les scénarios
de nouvelle validation et de note ont été exécutés rouges avant code. Le harnais
d'intégration a été corrigé pour fermer explicitement QdrantClient (pas de
protocole context manager dans la version épinglée).

70 tests Python ciblés +18 sous-tests réussis avec `-W error` ; 166 tests Node
connected réussis, dont le nouveau cas de libellés d'index. app.js régénéré puis
vérifié avec build.js --check. La CI Core vérifie désormais aussi le bundle
connected et ses tests Node ; dépendance Qdrant de test épinglée via Memory.
Suite CI complète à confirmer. Aucun test sur modèle réel, PC ou VM installé.
