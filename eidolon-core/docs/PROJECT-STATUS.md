# Eidolon — État consolidé du dépôt

Mise à jour : 14 octobre 2026, lot G229, Codex/GPT.

## Décision et périmètre

Toytoy a validé à 18 h 18 Europe/Paris cet ordre : cohérence Memory/Qdrant,
intégration Core, qualification, bilan, puis recette VM/PC. Claude annoncé
à nouveau disponible vers **22 h 58** ; cela ne programme ni ne lance une session.
Pas de fusion main, déploiement VM ou modification du corpus réel.

## État par composant

| Composant | État du code | Limite restante |
| --- | --- | --- |
| Core dialogue/missions/SOUL/autorisations | Intégrés dans la branche de développement | Modèle réel et recette intégrée VM/PC |
| Memory canon/journal | Implémentés et testés en isolation | Coordination journal/index et reprise multi-services |
| Worker Qdrant | Verrou obligatoire, lecture canonique par descripteur, preuve digest/modèle/génération dans G229 Memory | Contrat complet de 19 scénarios sur le chemin réel, réconciliation et serveur réel |
| Dashboard Claude jusqu'à C178 | Fusion locale préparée, historique conservé | CI de l'ensemble et vraie recette Windows |
| Monitoring Memory distant | Module intégré dans la fusion locale | Provisionnement SSH privé et recette VM non faits |
| GPU dashboard | Contrat et rendu sur exemples intégrés | Collecteur réel non raccordé par ce lot |
| Voix/vision | Services existants ; lexique et prononciation Claude intégrés | Micro/caméra physiques et contention GPU |
| Identité | Prototypes, adaptateurs et simulateur intégrés | Aucun droit accordé, aucun capteur ni modèle activé |
| Recherche Web et index documentaire | Prototypes optionnels intégrés, hors runtime par défaut | Politique/budgets durables et recette réseau |
| Image/vidéo | Modules, adaptateurs et parcours de préparation existants | Moteurs/configuration et recette de bout en bout |

## G229 — intégration de Claude

Base Core : `bb3bef6fc933f5482582418e0e3a35087e411bf4`.
Branche Claude intégrée localement : `2b52d8c31f58c62b8ea4afe0e440196dc9b07eed`.
Les 90 commits propres à Claude sont intégrés par une fusion à deux parents ;
les 31 commits Core postérieurs à leur ancêtre commun restent conservés.
Aucun conflit source. Un conflit documentaire introduit par notre déclaration
G229 dans ECHANGES a été résolu en conservant les deux contributions.
Le bundle JavaScript régénéré est identique au bundle fourni par Claude.

Les derniers I1/W1 Core sont conservés. Deux sondes historiques Claude ont été
actualisées : W1 n'est plus un échec attendu ; I1 vérifie la fraîcheur calculée
et le refus d'une étiquette imposée par l'appelant. Le test d'arrêt HTTP capture
explicitement la déconnexion attendue, joint son thread et ferme la connexion.
Les tests de registre emploient spawn plutôt que fork dans un processus multithread.

## Preuves réellement obtenues ici

- Memory G229 : 66 tests ciblés réussis, dont trois régressions reproduites avant correction. Rejeu complet final sur le code `556443c` : **2309 réussis, 12 sous-tests, 6 échecs liés aux sockets interdites**, 86,05 s. La CI doit encore valider ces six scénarios ; aucun n’est masqué.
- Core après fusion, première suite locale : **1699 réussis, 51 ignorés, 1 xfail, 21 échecs, 1 avertissement**, 1288 sous-tests, 264,20 s. Vingt échecs sont liés aux sockets AF_UNIX interdites dans l'environnement ; le dernier est un succès inattendu du test W1 encore marqué expectedFailure. Cette suite n'est PAS verte.
- Rejeu après correction des sondes I1/W1 et du test HTTP : **57 réussis, 24 sous-tests, aucun avertissement**, avec `-W error`. Inclut les six intégrations contre le véritable code Memory sur corpus synthétique.
- Autre lot ciblé registre/identité/index documentaire/activation monitoring : **65 réussis, 18 sous-tests**, `-W error`.
- JavaScript connecté : **139 réussis, 26 ignorés**, aucun échec ; les essais Chromium sont ignorés faute de moteur disponible. Ce n'est pas une recette visuelle Windows.
- Les comptes se chevauchent : ne pas les additionner.

La CI Core est préparée pour lire Memory au commit exact
`d74d772be25fe7d0e266711f58fba44248ba412a` et exécuter les six intégrations
au lieu de les ignorer. Les dépendances age/OpenSSL/FFmpeg restent installées
par la CI ; age est absent localement (45 tests de sauvegarde ignorés).
Les six autres skips locaux sont des moteurs d'identité optionnels absents.

## Publication et recette

Le push Memory a été **refusé par le contrôle automatique d'approbation**,
qui demande une autorisation explicite pour publier le code dans GitHub.
Aucune tentative de contournement, aucun push Core. Les nouveaux résultats
GitHub Actions ne sont donc pas disponibles. Publier Memory avant Core pour
que la référence exacte du workflow soit accessible, puis vérifier les deux CI.

J1 historique reste une preuve sur les anciens SHAs, pas sur cette fusion.
**J2 reste ouvert**. J3 exige B01–B12 sur VM/PC ; J4 est la décision de bêta.
L'indisponibilité MCP bloque la recette distante, pas l'analyse du dépôt.

## Suite prioritaire

1. Qualifier les commits publiés dans GitHub Actions.
2. Terminer J2 : contrat réel, reprise journal/index, contrôle de dérive à révision égale.
3. Contre-revue indépendante Claude du lot G229 et de l'intégration (fiche dédiée).
4. Restaurer MCP puis exécuter B01–B12 avec sauvegardes et SHAs figés.

Les anciens rapports sont conservés comme preuves datées, sans réécriture rétroactive.


## Publication autorisée le 14 octobre à 18 h 44

Toytoy a confirmé explicitement les deux publications. Le terminal sans identifiants ne peut pas pousser ; le connecteur GitHub authentifié publie les mêmes arbres Git. Memory : `d74d772be25fe7d0e266711f58fba44248ba412a`, arbre identique au lot local `eb14a45`. Core sera publié avec deux parents (base GPT et branche Claude) ; la CI est épinglée sur cette référence Memory accessible. Les anciens paragraphes de blocage relatent la tentative précédente.
