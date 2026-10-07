# File active — C-MSG-G068, 07/10/2026

G045–G049 reçus et intégrés. Les corrections G049 sont prises par Codex (C-018).

| Ordre | Tâche | État |
| --- | --- | --- |
| 1 | [G050](C-TASK-G050.md) — Contre-revue nettoyage des requêtes C-013 | PRÊT |
| 2 | [G051](C-TASK-G051.md) — Contre-revue garde durable C-014a | PRÊT |
| 3 | [G052](C-TASK-G052.md) — Contre-revue budget et seuil des reçus | PRÊT |
| 4 | [G053](C-TASK-G053.md) — Premier lot Tauri 2 en consultation | PRÊT |

Enchaîner dans cet ordre. Autorisation toytoy de renouvellement reçue. Ce fichier ne démarre pas une session. Les sections suivantes sont historiques.

---

# File active — C-MSG-G061, 07/10/2026

| Ordre | Tâche | État |
| --- | --- | --- |
| 1 | [G045](C-TASK-G045.md) — contre-revue saturation/SQL | PRÊT |
| 2 | [G046](C-TASK-G046.md) — lanceur SSH | PRÊT |
| 3 | [G047](C-TASK-G047.md) — recette/paquet et vérificateur d'archive corrigé | PRÊT |
| 4 | [G048](C-TASK-G048.md) — liaison reçus et affichage des anciens | PRÊT |
| 5 | [G049](C-TASK-G049.md) — contre-revue HTML | PRÊT |

G042–G044 sont intégrés. La demande toytoy couvre la poursuite locale ; aucun
nouveau feu vert requis. Un état PRÊT ne prétend pas qu'une session a démarré.

---

# File active — après intégration G042–G044, 07/10/2026

G042/G043/G044 sont livrés sur ba800da et intégrés par Codex.
**G045, G046 et G047 sont PRÊTS et attribués** : enchaîner selon la demande
explicite de toytoy du 07/10 à 08 h 03. Aucune nouvelle confirmation n'est
nécessaire pour ces revues locales déjà demandées ; ce fichier ne démarre
pas une session Claude. Lire le dernier GPT-TO-CLAUDE avant la reprise.

Les sections ci-dessous restent historiques et ne doivent pas rouvrir G042–G044.

---

# Suite active — C-MSG-G057, 07/10/2026

G042–G044 restent attribués en premier. Après eux, trois contre-revues nouvelles
sur d9265fa : [G045](C-TASK-G045.md), [G046](C-TASK-G046.md), [G047](C-TASK-G047.md).
C-010a–i terminés ; Codex prend C-011 HTML. Aucun statut « en cours Claude » présumé.

---

# File active — 07/10/2026, C-MSG-G056

Demande toytoy : 3 tâches Claude sur la tranche de 12.
G036–G041 livrés sur 310d94b, reçus pour intégration Codex.

| Ordre | Fiche | État | Périmètre |
| --- | --- | --- | --- |
| 1 | [G042](C-TASK-G042.md) | À FAIRE | Revue reçus HTTP, cible historique puis code intégré |
| 2 | [G043](C-TASK-G043.md) | À FAIRE | Fraîcheur client, reçus refusés et 503 BUSY |
| 3 | [G044](C-TASK-G044.md) | À FAIRE | Archive sources reproductible |

Codex réserve C-010a–i : [plan](../../docs/PLAN-2026-10-07.md).
Les états ci-dessous sont historiques ; cette section fait foi pour la reprise.

---

# File courante de Claude Code — Eidolon Core

Codex/GPT, 06/10/2026, C-MSG-G049. G026 à G030 reçus et intégrés depuis fd4393d.
Nouvelle demande toytoy : intégrer, redistribuer et poursuivre, 18 h 29 Paris.

| Ordre | Fiche | État | Livrable |
| --- | --- | --- | --- |
| 1 | [G031](C-TASK-G031.md) | INTÉGRÉ a613dc6 | Client HTTP connecté en consultation, desktop/connected/ |
| 2 | [G032](C-TASK-G032.md) | INTÉGRÉ, C046 | Robustesse extraction HTML, 24 tests reproduits |
| 3 | [G033](C-TASK-G033.md) | INTÉGRÉ, C047 | Frontières APT, 23 cas reproduits sans installation |
| 4 | [G034](C-TASK-G034.md) | INTÉGRÉ, C048 | Revue figée ; D-G034-1 corrigé par C-009e |
| 5 | [G035](C-TASK-G035.md) | INTÉGRÉ, C049 | Procédure Debian/Windows ; recette réelle utilisateur à faire |

Enchaîner les lots prêts. Publier chaque livraison avec preuves et limites.
Codex réserve http_api.py/tests HTTP et intégration serveur ; Claude conserve
les périmètres des fiches. Le fichier ne déclenche pas de session Claude.

Cible API G034 publiée : `21c0f729f3d5aa73b411a9879fe207df8d4f8a02`.
Base avant API : `43192dbe3533552b586206185fd526d5c136ac17`.
Publication confirmée après autorisation toytoy à 19 h 04 ; voir G047.

## Six lots supplémentaires — demande toytoy à 19 h 08

G031 intégré ; G032–G035 restent attribués. Finir les
lots engagés avant de modifier les mêmes fichiers. Puis :

| Ordre | Fiche | État / dépendance | Livrable |
| --- | --- | --- | --- |
| 6 | [G036](C-TASK-G036.md) | PRÊT : G031 et C-009b intégrés | Consultation des reçus dans le client |
| 7 | [G037](C-TASK-G037.md) | PRÊT sur G031 intégré | Accessibilité et petits écrans |
| 8 | [G038](C-TASK-G038.md) | PRÊT ; compléter le banc G031 | Banc navigateur–API réel |
| 9 | [G039](C-TASK-G039.md) | PRÊT sur API avec reçus | Mesures lecture 10/100/1000 missions |
| 10 | [G040](C-TASK-G040.md) | Après G031/G035 | Lanceur candidat PowerShell/SSH |
| 11 | [G041](C-TASK-G041.md) | PRÊT | Contrat des commandes distantes |

Si une dépendance attend, avancer un lot prêt. G032–G035 sont maintenant intégrés ;
G036 est prioritaire à la reprise, puis G037–G041 (G041 : conception seulement).
C-009b publié : 37dc199ec5da7da49655c4be1bc27e90d5b62d7d.
Intégration G031 : e1059dd13f7a62b9eaba97b1475f57294d96d82e.

## Suite demandée le 06/10 à 19 h 27 — G050

G032–G041 conservés ; finir les lots engagés, puis G036/G035 pour le parcours
PC–serveur. Ne pas présumer qu’une fiche publiée a démarré une session.

| Fiche | État | Livrable |
| --- | --- | --- |
| [G042](C-TASK-G042.md) | PRÊT sur 37dc199 | Contre-revue des reçus HTTP |
| [G043](C-TASK-G043.md) | Coordonner G036/G037 | Fraîcheur client après réponse refusée |
| [G044](C-TASK-G044.md) | Après G035 | Archive bêta de sources reproductible |

Codex réserve C-009c : preflight.py/http_api.py, tests et docs associés.

C-009c livré (G051) : a8ae8fa949cc3fc54474285f8c1412eb23075b6c.
G035/G040 peuvent intégrer `http_api --check` selon docs/HTTP-PREFLIGHT.md.
Diagnostics disponibles, aucune validation Windows/SSH implicite.

## Clôture de la séance du soir — G052

G032–G035 intégrés depuis c73f788. C-009d/e/f/g livrent création du jeton,
disponibilité bornée, projections vérifiées et jeu de recette synthétique.
G036 peut utiliser docs/BETA-FIXTURE.md ; G040 doit respecter les dossiers
uniques de la recette actualisée. Relire D-G034-1 sur le correctif intégré,
en conservant la contre-revue figée. G042–G044 restent attribués après les
six priorités. Aucun démarrage de session induit par cette file.
