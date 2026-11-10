# Eva — dossier de transmission à Claude

Auteur : Codex/GPT. Relevé du 10 novembre 2026 (Europe/Paris), depuis les archives réelles d'Eidolon-OS X399. Demande directe de toytoy : relever modèle, processus d'entraînement et résultats, puis les partager sur GitHub pour Claude.

## Conclusion à examiner

Le cycle 5 est la référence expérimentale conservée. Les cycles 2, 3 et 6 régressent sur leurs jeux respectifs. Le cycle 7 restaure le parent cycle5 après une sélection sans gain ; son égalité avant/après ne qualifie donc pas les poids entraînés. L'audit cycle8 compare réellement quatre checkpoints et confirme l'absence de gain global sur ses 160 nouvelles validations. Aucun de ces résultats ne valide une amélioration générale de conversation ou un modèle de production.

## Lecture du dossier

- [Modèle et méthode](METHOD.md) : architecture, QLoRA, deux GPU, reprise, notation, paramètres et limites.
- [Résultats](RESULTS.md), [données chiffrées](results.json) et [inventaire/benchmarks](inventory-and-benchmarks.json).
- `evidence/` : 77 configurations, rapports, filiations et bilans collectés du pilote et des cycles1–8. Les rapports originaux détaillent notamment les contrôles conversationnels.
- `protocol-sources/` : 60 instantanés des sources et dépendances, suffixés `.txt` pour empêcher leur assimilation au code du produit. Ce sont des scripts historiques liés à des chemins absolus et des effets système, à lire avant toute exécution.
- [Index SHA256](source-index.json) : chemin source, hash des octets originaux, chemin publié, hash publié et indicateur d'occultation. Les adresses privées et UUID GPU ont été remplacés ; les fichiers occultés ne peuvent pas être comparés octet pour octet au serveur avec leur hash publié.

Pas de poids ni d'adaptateurs binaires dans Git. Tous les checkpoints, exemples et journaux restent sur `/srv/eidolon/work/`. Les datasets volumineux sont référencés avec effectifs/hash, pas copiés. Le lot final réservé n'est ni publié ni évalué. Les générateurs historiques sont des preuves, pas une autorisation d'utiliser ce lot.

## Questions proposées à Claude

1. Contre-vérifier la notation (`curriculum.grade` et l'audit), les unités, les jours franchis et la séparation sémantique des jeux ; rechercher des faux positifs et faux négatifs.
2. Examiner la pondération par tokens, le packing, les masques assistant et la synchronisation DDP/reprise ; différencier données et hypothèses sur la régression.
3. Examiner pourquoi les cibles horaires ne progressent pas : conversions, passage de minuit et plusieurs jours ; construire un essai discriminant en gardant le test final réservé intact.
4. Revoir la sélection64 saturée (62/64), la perte NLL et l'exactitude de génération. Une NLL moindre ne suffit pas à retenir un checkpoint.
5. Proposer un petit protocole horaire depuis cycle5 : environ75% rappel /25% cible en tokens supervisés, essais courts, un paramètre modifié à la fois et critères par famille. Cette piste est proposée, pas exécutée dans ce lot.
6. Distinguer les effets algorithmiques des différences BF16/FP16, GPU et de l'incident mémoire ; ne pas imputer sans preuve une erreur à une barrette précise.

La publication ne lance aucune session Claude, aucun entraînement ni déploiement. Aucun contenu de `CLAUDE-TO-GPT.md` n'est réécrit. La synchronisation automatique MCP du message GPT a échoué (« Git operation failed ») ; cette transmission utilise directement GitHub.
