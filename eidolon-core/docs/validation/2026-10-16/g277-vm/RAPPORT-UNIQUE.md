# Eidolon — rapport unique G277

16 octobre 2026, contrôles jusqu’à 20 h 25 Europe/Paris. Autorisation : exécuter la suite de la recette VM et fournir le client Windows.

## Résultat

**Réserve bloquante relevée au dernier essai :** le rappel direct retrouve la note synthétique, mais la question longue via le chat produit une réponse hors cible et aucune citation au format attendu. Le contrôle V07 est FAIL ; la qualité du rappel conversationnel doit être corrigée avant de considérer les réponses mémoire fiables.

Le serveur est raccordé pour un premier essai PC : dialogue distant, profil `toytoy`, mémoire avec écriture confirmée, index sémantique, lecture d’un dossier de recette, import DOCX et maintenance planifiée. Les services ont été redémarrés et les reçus/historiques conservés. La bêta complète reste **INCOMPLETE** : la recette matérielle Windows et plusieurs raccordements fonctionnels restent ouverts. Ce rapport ne transforme pas les tests unitaires en validation de ces parcours réels.

Code installé : Core `58dbd825a18ab829b8b3acde1218256603c67d1e`, Memory `fd53ce6afa78f26ad0d79642242b69177326f17c`. Publication sur les branches de développement existantes, sans fusion main. Les commits documentaires suivants ne changent pas ces versions de code. Aucun benchmark G182 relancé.

## Corrections et contre-vérification

- Bibliothèque : détection des modifications rapides de même taille malgré des métadonnées identiques sur les VM. Double empreinte bornée des documents exclus de l’extraction ; budget supplémentaire de 32 Mio. Au-delà, diagnostic explicite `FILE_TOO_LARGE_CONTENT_UNVERIFIED` sans bloquer les autres fichiers.
- Configuration JSON Core/Memory et prototype : comparaison de deux lectures bornées, indépendante de la précision mtime/ctime.
- Inventaire de copie : empreintes répétées, relecture finale et contrôle des chemins après parcours. L’arbre doit rester arrêté ; aucun snapshot atomique n’est revendiqué.
- Maintenance : l’heure de validation est prise **après** réception de l’activité distante, au démarrage et pendant la synchronisation. Avant correction, une réponse fraîche était refusée comme future. Régression reproduite et corrigée sans tolérance arbitraire sur les horloges.

Suites complètes exécutées sur les VM : **Core 2 299 réussis, 18 ignorés, 1 328 sous-tests ; Memory 3 157 réussis, 26 ignorés, 3 xfail, 12 sous-tests**. Core comporte un avertissement attendu de fixture ZIP. Après le dernier correctif maintenance : **14 tests ciblés réussis**, dont deux scénarios de réponse réseau datée pendant la requête. La suite complète n’a pas été relancée après ce dernier correctif limité ; l’exécution réelle systemd a été vérifiée deux fois. Un dernier défaut de génération a ensuite été reproduit : le schéma autorisait une réponse contenant une proposition, refusée par Core (`MODEL_OUTPUT_INVALID`). Le schéma est désormais séparé en deux branches conformes au contrat, sans assouplir le parseur. **55 tests ciblés de dialogue/conversation et 58 sous-tests réussis** ; diagnostic sur le modèle réel passé de refus à `VALID`. La suite complète n’a pas été relancée après ces deux correctifs ciblés. Les 19 tests Qdrant natif de G276 restent une preuve antérieure distincte.

Les échecs intermédiaires sont conservés dans les journaux privés : collecte initiale trop large des archives documentaires, umask de fixtures, clone Git nécessaire aux tests de packaging et défauts réels de détection des changements. Les tests concernés ont été corrigés ou exécutés dans leur environnement requis, sans masquer les limites restantes.

## Sauvegardes et retour arrière

Sauvegardes effectuées services arrêtés, puis restaurées dans une copie et comparées : chemins, contenus, modes, UID/GID. Sources inchangées.

| VM | Sauvegarde privée | Entrées | SHA-256 du tar |
|---|---|---:|---|
| Core | `/var/backups/eidolon/g277-20261016-core/snapshot.tar` | 50 | `bc192fce232d058b6f6a5c28811e4c2265b1599864ffd4d15ac767cd2396a84c` |
| Memory | `/var/backups/eidolon/g277-20261016-memory/snapshot.tar` | 604 | `47e33975180b55f8f6a905ccb6af931d27b15cd0995a3656d26096d918ff3983` |

Le corpus actif est une **nouvelle copie liée à `toytoy`**, dans `/home/toytoy/eidolon-beta-memory/toytoy`. L’ancien corpus `/home/toytoy/eidolon-corpus-factual-v2-test` est conservé. Les environnements précédents et unités d’origine sont conservés ; les changements API/pont passent par des drop-ins `50-g277.conf`.

Retour arrière opérateur : arrêter le timer puis les services concernés ; sauvegarder d’abord l’état courant et le nouveau souvenir avec ses reçus ; retirer les drop-ins G277 après examen ; revenir aux versions/configurations consignées dans les sauvegardes ; contrôler le stockage puis redémarrer. Restaurer un corpus uniquement dans une **nouvelle copie** et réconcilier les écritures postérieures. Ne pas écraser l’état actif avec le snapshot antérieur. La restauration des sauvegardes a été vérifiée ; un retour complet de l’application vers l’ancienne version n’a pas été exécuté.

## Services actifs

| Hôte | Raccordement vérifié |
|---|---|
| Core `192.168.1.101` | API loopback 8767, communication 8766, supervision 8768, profil `toytoy` et client `pc-toytoy-g277` |
| GPU `192.168.1.135` | Ollama distant via tunnel Core 11435, `gemma4:12b`, inférence réelle et dialogue réussis |
| Memory `192.168.1.110` | Pont loopback 18765 avec jetons lecture/écriture séparés ; reranker CPU existant conservé |
| Memory | Qdrant natif 1.15.4, HTTP 26333/gRPC 26334 uniquement loopback, service activé |
| Memory → Core | Embedding `qwen3-embedding:0.6b` via SSH 11435 → Core 11434 ; activité via SSH 8767 → Core 8767 |
| Memory | Timer de maintenance activé, prochaine fenêtre observée le 17/10 à 04 h Europe/Paris |

Un compte SSH technique `eidolon-embedding` limite les destinations à l’embedding et à l’activité ; aucun shell, mot de passe ou écoute distante autorisé. Empreinte hôte épinglée. Services applicatifs sous le compte existant `toytoy`, configurations privées et clés non publiées. L’API n’est pas exposée directement au LAN.

Index reconstruit sur la copie : **189 éléments**, puis **190 après le souvenir synthétique de recette**, politique incrémentale copy-on-write. Rappel réel : `INDEX_SNAPSHOT_MATCH`, empreinte canonique identique, balise `AZUR-277` retrouvée une fois, statut `UNVERIFIED`, fraîcheur `CANONICAL_AT_READ`. L’élément retourné n’a pas d’`excerpt_reference` ; la validation complète des citations/paraphrases/hors-sujet reste ouverte.

La maintenance reçoit bien l’activité de Core, sous les restrictions systemd installées. Deux exécutions réelles terminées avec succès : `DEFERRED`, raisons `OUTSIDE_WINDOW` et `ACTIVITY_RECENT`. Fenêtre 04–08 Europe/Paris, inactivité et ancienneté du démarrage de 30 min, charge normalisée ≤ 0,7. Le premier cycle nocturne n’a pas encore été observé ; la synchronisation manuelle a réussi. L’activité mesure les requêtes Core, pas le clavier des autres applications du PC.

## Parcours réels vérifiés

- Stockage actif : `READY`, zéro anomalie/avertissement, sous `toytoy`.
- Dialogue distant : réponse `ANSWER` en 11,487 s ; rejeu identique sans nouvel appel au modèle.
- « Retenir ceci » : aperçu, confirmation, reçu `COMMITTED`, rejeu identique ; réutilisation de la même requête avec un contenu différent refusée en 409.
- Après redémarrage API, communication, supervision et pont : reçu et historique identiques ; réponse rejouée sans nouvel appel modèle.
- Jetons pont distincts : lecture utilisée en écriture, écriture utilisée en lecture et jeton invalide tous refusés en 401.
- Lecture UTF-8 du dossier synthétique `recette` réussie ; traversée et lien symbolique refusés (503 générique).
- Import DOCX synthétique : `EXTRACTED_NOT_REMEMBERED`. Document avec macros refusé en 400. Aucune mémorisation implicite de l’extraction.

Les preuves diffusables sont dans `core-evidence.json` et `results.json`. Les journaux détaillés restent sur chaque VM sous `/home/toytoy/eidolon-recette-g276-20261016`, avec réponses privées séparées. Ni secrets ni contenus personnels ne sont inclus dans ce rapport.

Dernier parcours API après correction du schéma : `ANSWER`, mémoire envoyée (5 éléments, `INDEX_SNAPSHOT_MATCH`), rejeu sans appel supplémentaire. Cependant, la réponse ne contient pas la balise attendue et ne porte aucune citation reconnue. Le modèle s’appuie sur une autre note ; cet essai **ne valide pas** le rappel conversationnel. Il reste nécessaire d’isoler sélection/reranking et génération sur un jeu de questions de recette ; aucun réglage opportuniste ni benchmark G182 n’a été lancé.

## PC : fichiers prêts

Le `.exe` G270 est conservé, SHA-256 `3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`. Il charge l’interface actuelle servie par Core. Pas de nouveau build Windows revendiqué.

Décompresser `eidolon-pc-g277.zip` dans un dossier du Bureau ; ouvrir `Eidolon-tunnel.cmd`, récupérer la clé comme expliqué dans `LIRE-MOI.md`, puis ouvrir `Lancer-Eidolon.cmd`. **Le lanceur passe le port 8767** : un double-clic direct sur l’ancien EXE utilise 8765. La clé privée reste sur le serveur et n’est pas dans le ZIP. Les anciennes clés ne sont pas révoquées, mais seul le nouveau client est associé au profil actif ; utiliser la clé `pc-toytoy-g277` indiquée dans le guide.

## Reste à valider, par priorité

1. **Essai PC connecté** : SSH, WebView2, clé, dialogue, rappel, confirmation et redémarrage du client ; pertes réseau et rejeu. Je n’ai pas de contrôle du PC Windows dans cette session.
2. **Défaut V07 et recette serveur restante** : corriger la réponse mémoire hors cible constatée, puis premier cycle nocturne et reprise, indisponibilité réelle Qdrant/embedding sans fallback, qualité du rappel et citations, retour applicatif ancienne version sur copie. Les réussites ciblées et la sauvegarde restaurée ne suffisent pas à fermer ces critères globaux.
3. **Périmètre personnel à raccorder** : chemins NAS/PC à sélectionner, serveur SearXNG et Internet à configurer ; second profil réel à définir avant la validation d’isolation. Le profil actuel a Internet désactivé et seulement le dossier synthétique `recette` autorisé.
4. **Windows et matériel** : résident/démarrage, micro, haut-parleurs, webcam, permissions refusées, arrêt des captures, mise à l’échelle, session prolongée, concurrence CPU/RAM/VRAM. Aucune validation physique n’est déduite des tests Linux.
5. **Identité et exploitation avancée** : modèles/calibration réels et enrôlement volontaire, rotation/révocation des sessions, bibliothèque sur les vrais dossiers et conservation, budgets GPU mesurés. Aucune capture biométrique ni purge n’a été faite.
6. **Go/no-go humain** sur le périmètre réellement vérifié. La matrice conserve les critères incomplets : ce déploiement permet de commencer les essais PC, il ne clôt pas la recette complète de bêta.
