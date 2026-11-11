# G314 — C313 reproduit : fin de chaîne et budget réel d'E4a

Auteur : Codex/GPT. Date :11/11/2026, Europe/Paris.
Base examinée :`667c57a61bcf7bb306755dece7d7788adc560073`, branche`feat/eidolon-core-v0.1`.
Revue C313 relayée par toytoy ; lot CPU pris et livré. Aucun entraînement ni génération GPU.

## Ce qui a été reproduit

Le script Claude `eva_hybrid_analysis.py` a été copié sans modification depuis C313, puis exécuté avec Python isolé sur le rapport serveur original G312.
SHA256 du script :`815fe673c5c6f10be0214c50e1e76ae3c05d6083f1e5b234cf4fb98d3d6e315c`.
[Sortie complète](analysis-original.json), [script Claude inchangé](eva_hybrid_analysis.py.txt), [empreintes serveur](review-saved.json) et [correspondance des fichiers publiés](source-index.json).

| Indicateur sur320cibles | Parent | Step204 |
|---|---:|---:|
| Réponse finale juste | 86 | 56 |
| Entier de conversion présent | 300 | 303 |
| Entier du total présent | 297 | 299 |
| Total présent mais réponse fausse | 211 | 245 |
| Tokens générés moyens | 63,5 | 92,3 |

Les37pertes sont retrouvées, dont28 où conversion et total attendus sont présents.
**Correction de mon interprétation G312 :** l'exemple de conversion erronée illustrait une faute locale, sans établir une dégradation agrégée des conversions. Les indicateurs de présence de C313 ne montrent pas cette dégradation générale ; la fragilité principale reste l'exploitation finale du total.
Ces indicateurs détectent un entier dans le texte, pas la validité sémantique de toute l'étape. Le mot « présent » est plus précis que « calcul prouvé juste ».

## Soustraction : opération correcte, réponse finale incorrecte

Les40réponses contenant une soustraction littérale `N −1440 =R` contiennent42opérations (deuxréponses en contiennent plusieurs).
**42/42 soustractions arithmétiquement correctes**, mais **0/40 réponses finales justes**.
[Audit étroit des soustractions et exemples](subtraction-audit.json).

Exemple :`1652 −1440 =212` est juste et donne03:32, mais Eva annonce0jour au lieu de1.
Autre exemple :`844 −1440 =−596` est une soustraction juste, mais elle est appliquée inutilement et interprétée comme un passage au jour suivant.

La colonne « justes » de C313 compte la réponse finale. Elle ne signifie pas que la soustraction elle-même est fausse.
Cette nuance renforce le diagnostic : soustraire fonctionne ici ; choisir quand soustraire, exploiter le signe, compter les jours et reconvertir restent mal coordonnés.
La regex complémentaire ne valide que les soustractions littérales entières, pas une chaîne entière.

## Budget réellement observé d'E3-204

Tokenisation refaite sur CPU avec le tokenizer local, le même chat-template, le SYSTEM et le masquage assistant d'E3 ; aucun modèle chargé.
Les408packs et60109tokens supervisés par passage sont retrouvés.
[Audit des tokens](token-budget-audit.json).

| Population | Exemples/passage | Tokens supervisés/passage | Sur2passages terminés |
|---|---:|---:|---:|
| Tous les horaires (101rappels+68cibles) | 169 | 28487 | 56974 |
| Rappel nonhoraire | 709 | 31622 | 63244 |
| Total | 878 | 60109 | 120218 |

Part **de tous les horaires :47,392237%** des tokens supervisés.
Les21,253057% du manifeste historique sont la part du seul groupe68cibles, pas celle des169horaires.
Budget complet2passages :1756présentations,816packs de512,4packs/miseàjour globale,204misesàjour,344968tokens nonpadding.
Pour E4a,204misesàjour identiques ne suffisent pas à revendiquer une dose identique si les nouvelles réponses changent les longueurs et le packing.

## E4a proposé, pas encore lancé ni construit comme trainer

E4a est le prochain essai que je recommande, avant E4b : il examine l'hypothèse diversité/répétition sans changer simultanément LR et méthode de résolution.

1. **Départ et comparaison.** Repartir du parent cycle5, LRmax3e-6, même calendrier102pas répété deuxfois, mêmes deuxV100200W, précision/LoRA et pondération par tokens inchangées. Step204 est le comparateur issu d'E3, jamais le point de départ d'E4a.
2. **Données.**338problèmes horaires distincts par paire(départ,durée), pas seulement338paraphrases. Rappel nonhoraire identique àE3, y compris ses répétitions. Mêmes générateur, format de réponse, proportions jours/frontières/plages/gabarits ; ne pas ajouter enmême temps les exercices atomiques d'E4b.
3. **Dose.** Préparer et publier les comptes avant lancement : tokens horaires/nonhoraires, total, longueurs, ordre,408packs/passage et102misesàjour/passage. Chercher des remplacements appariés par longueur tokenisée et strate afin de préserver la dose. Si l'égalité est impossible, annoncer le compromis avant l'essai ; ne pas modifier silencieusement plusieurs variables pour obtenir204pas.
4. **Exclusions.** Dédupliquer contre données, sondes, sélection et rapports déjà utilisés à partir des listes d'exclusion disponibles. Le test final réservé reste nonlu et nonutilisé. Geler graines, fichiers etSHA avant toute optimisation.
5. **Évaluation.** Parent/E3-204/E4a au même harnais lot16 déjà qualifié, mêmes GPU/IDs/lots. Le jeuG312 reste une comparaison exploratoire connue. Ajouter un jeu neuf figé avant l'entraînement si l'on veut mesurer une généralisation indépendante, évalué sur les trois candidats ; ne pas le présenter comme le jeu final réservé.
6. **Décision.** Jour0≥parent−1 etacquis≥25/32 sont des garde-fous, pas une preuve de gain. Publier justesse globale, strates, gains/pertes appariés, troncatures etcanaris. Un mieux face au204 qui reste inférieur auparent ne suffit pas à retenir le candidat. Aucune promotion automatique.

Une variante plus stricte à discuter consiste à garder le premier passage identique àE3 et remplacer seulement les169horaires du deuxième passage, pour concentrer la différence au moment de la répétition. C'est une proposition de contrôle, pas une modification décidée du protocole de Claude.
Un seul essai favorable resterait compatible avec l'hypothèse diversité ; il ne démontrerait pas que la répétition était l'unique cause. Le tirage de nouveaux exemples, la dose effective et la variabilité numérique doivent rester explicites.

## Deux métriques à ajouter, avec définition précise

**NLL numérique :** annoter les spans des résultats intermédiaires et finaux calculés dans les cibles générées par oracle, avec leur rôle (conversion,total,reste,jours,HH:MM). Ne pas définir les chiffres calculés par une soustraction d'ensembles de caractères ou de nombres présents dans la question : une bonne réponse peut réutiliser une valeur d'entrée.
Aligner les spans sur les offsets du tokenizer et publier tokens inclus/exclus aux frontières, couverture parétape, moyenne pondérée et moyenne parproblème.
La NLL numérique reste teacher-forced : elle mesure la vraisemblance des nombres justes sous un contexte cible, pas une preuve autonome de calcul réussi en génération.

**Hybrides :** distinguer débutDépart, fragments d'opérations, structure partielle/complète et invariants réellement contrôlés. Une regex stricteA/Bà0 ne démontre pas que toutes les réponses sont sans structure ; un préfixe ne prouve pas la chaîne.
Définition exploratoire possible : commence parDépart mais ne satisfait pas la chaîne complète vérifiée par un parseur ; publier séparément les nonparsables et les erreurs arithmétiques, de conversion, de branchement et de comptejours. Ne pas transformer automatiquement un nonparsable en raisonnement faux.

## État conservé

DossierCPU :`/srv/eidolon/work/eva-review-c313-20261111-G314`.
Le script Claude reste intact, aucune source de son dépôt réécrite.
Aucun optimizer/backward, génération GPU, service d'entraînement, nouveau suivi, changement de pilote, WOL, reboot ou extinction.
E4a/E4b ne sont pas lancés ; le parent cycle5 reste la référence. Eidolon Inference est hors de ce lot.
