# G276 — rapport unique de recette VM, 16 octobre 2026

La première passe réelle est exécutée sur Core et Memory. Le tunnel GPU, initialement inaccessible, est rétabli après le redémarrage effectué par toytoy. Une inférence réelle réussit. **La recette complète reste INCOMPLETE : un défaut bibliothèque est reproduit et le déploiement des services G275 n'est pas encore qualifié.**

Bases exactes : Core `278e551b3413fbd8ebef6bdff7401f7f9cbf2c44`, Memory `b36ada1ff4f505fa2c5d2778f74f3b0c836d2f4c`. Python 3.13.5 sur les deux VM. Essais sous toytoy, UID 1000, dans des sources et environnements Python isolés. Aucun corpus personnel utilisé comme fixture, aucun modèle téléchargé, aucune fusion main ni relance du benchmark G182.

## Résultats exécutés

| Contrôle | Résultat | Portée |
| --- | --- | --- |
| Core, socle G269 avec `-W error` | 12 PASS | Maintenance, intégration Memory synthétique et intégrité du dossier |
| Memory, socle G269 avec `-W error` | 37 PASS | Runtime d'index, passages Qdrant en mémoire, remember |
| Core, sélection G269–G275 disponible | 105 PASS, 1 FAIL, 1 avertissement | Suite isolée ; défaut détaillé ci-dessous |
| Memory, sélection G269–G275 disponible | 47 PASS | Suite isolée, inclut les 37 tests du socle |
| Memory, serveur Qdrant réel 1.15.4 jetable | 19 PASS en 58,44 s | Transport, reprise, crash et rappel ; aucun serveur de production utilisé |
| Stockage canonique installé | READY, 0 problème, 0 avertissement | Vérification non destructive avec le code G275 sous le compte du service |
| Tunnel Core → Memory | 401 sans token, 400 avec token et requête volontairement invalide | Raccordement et authentification établis sans consulter un souvenir personnel |
| Précontrôle Core sur l'état installé | PASS | Aucun serveur lancé, ni port libre, navigateur ou audit complet de base validé par ce contrôle |
| Tunnel Core → Ollama distant | Actif, HTTP 200 | Après redémarrage utilisateur de l'hôte configuré 192.168.1.135 |
| Inférence réelle distante | Réponse RECETTE_OK, 5,833 s, 5 tokens générés | Modèle configuré `gemma4:12b`, contexte 2048, plafond 32 tokens, message synthétique |
| Sauvegarde et restauration | 6 fichiers identiques par SHA-256 | Corpus synthétique arrêté seulement ; ne constitue pas la sauvegarde du corpus privé |
| Readonly sur copie restaurée | Écriture refusée, rappel synthétique réussi | UID 1000, fichiers appartenant à root et non inscriptibles ; rappel lexical, aucun résultat sémantique revendiqué |
| Remember | Aperçu, application, rejeu identique et conflit vérifiés | Un seul souvenir synthétique UNVERIFIED ; aucune écriture sur le corpus privé |

Les suites se recouvrent : ne pas additionner les nombres pour annoncer un total de tests distincts. Le serveur Qdrant jetable utilise le binaire épinglé par le workflow existant, archive SHA-256 `8d0f3af71b4606581c6d4d943c0763aa7f368a7ee801b2f01e16ab2376e8f363`.

## Écarts constatés

**G276-F01 — bibliothèque, priorité P2, ouvert.** Le test `test_large_file_changed_during_scan_preserves_previous_generation[rewrite]` échoue : une réécriture à taille identique d'un fichier de plus de 4 Mio n'est pas détectée si mtime et ctime restent identiques. Une sonde sur 100 écritures rapides dans `/tmp`, puis 100 sur le disque du dossier de recette, constate 100 signatures temporelles inchangées dans chaque série. Le test est sensible à la granularité effective du système de fichiers ; le défaut de garantie est réel. Les fichiers concernés sont exclus de l'extraction et n'ont pas d'empreinte de contenu : aucun ancien extrait n'a été observé réutilisé comme actuel. La contre-vérification G275 ne suffit donc pas à garantir toute modification concurrente sur ces VM. Aucun changement de test pour masquer l'échec, ni correctif applicatif déployé dans ce lot.

**Environnements corrigés dans la recette.** L'environnement de développement Memory ne contenait pas `qdrant_client`, celui du service Core ne contenait pas pytest. Des venv dédiés ont été créés avec pytest 9.1.1, qdrant-client 1.15.1 et PyYAML. Les premiers essais créaient des fichiers inscriptibles par le groupe, refusés par les protections JSON/configuration. La reprise avec `umask 077` rétablit les contrôles concernés. Les essais initiaux restent consignés. La suite large Core émet un avertissement attendu lors de la fabrication volontaire d'un ZIP à noms dupliqués ; elle a été relancée sans `-W error`. Le socle prescrit a été vérifié séparément avec `-W error`, sans exclusion.

**GPU.** Le tunnel échouait avec « No route to host ». Il est redevenu actif après le redémarrage signalé par toytoy. L'inférence réelle utilise le modèle déjà présent, digest `6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`. Ollama indique ensuite 1 083 829 124 octets de VRAM pour ce modèle ; cela ne prouve pas un chargement intégral sur GPU, ni les budgets et arbitrages de la file GPU. Le pilote NVIDIA local à Core reste indisponible ; ce n'est plus un obstacle à l'inférence distante.

## État installé et suite prioritaire

Les dépôts sont synchronisés ; les services Core/Memory n'ont pas été redémarrés par cette recette. Leurs processus ont été lancés avant la synchronisation. La configuration observée reste celle du socle historique : pont Memory avec reranker, sans `--index-config`, et API Core sans `--beta-runtime` ni file GPU configurée. Les tests de composants ne valent donc pas validation de tous les parcours installés.

1. Traiter G276-F01 et contre-vérifier la bibliothèque sur les systèmes de fichiers réels ; préciser la garantie des fichiers exclus de l'extraction.
2. Constituer et vérifier une sauvegarde arrêtée des états privés réels ; contrôler le compte de service, les chemins et les permissions avant le basculement G275. Les sauvegardes déjà présentes n'ont pas été requalifiées.
3. Raccorder et qualifier l'index de passages avec modèle d'embedding épinglé et alias de recette, puis les profils, tokens lecture/écriture, activité inter-VM et maintenance. Les 19 tests Qdrant ne remplacent pas cette intégration.
4. Vérifier les services après redémarrage contrôlé, le dialogue de bout en bout, les budgets GPU et le rollback sur copie.
5. Terminer les parcours PC, micro, webcam, voix, résident Windows et décision humaine finale. Aucun de ces parcours n'est marqué PASS ici.

Les preuves publiques sont [Core](core-evidence.json), [Memory](memory-evidence.json), [résultats des 50 cas](results.json) et [contrôle de complétude](results-check.json). Les journaux complets et environnements restent sur chaque VM dans le dossier privé de recette G276. Les contenus de conversations, les tokens et le corpus privé ne sont pas publiés.
