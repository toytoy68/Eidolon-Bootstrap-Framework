> Vue actualisée après les cinq compléments : [BACKLOG-BETA-ACTUEL-G273.md](BACKLOG-BETA-ACTUEL-G273.md). Ce document conserve le constat G272.

# Backlog bêta actuel — G272, 15 octobre 2026

Cette vue rapproche les livraisons G269–G272 du besoin serveur/PC. La TODO longue
conserve l’historique : une ancienne case ouverte ne suffit pas à conclure qu’une
fonction actuelle est absente. Inversement, une simulation ou un contrat ne vaut
pas une qualification installée. Les options de brainstorming ne sont pas toutes
des fonctionnalités adoptées.

## Ordre de priorité

| Priorité | Travail restant | État logiciel / dépendance | Critère de sortie |
| --- | --- | --- | --- |
| P0 | Compte C187, chemins, droits, inventaire VM100/VM110/PC | Décision d’exploitation et machines | Inventaire signé par l’opérateur ; accès minimaux vérifiés sous le vrai UID |
| P0 | Sauvegarde complète et restauration sur copie | Outils de copie et reprise prêts ; plusieurs magasins distincts | V02/V12/G18, reçus et quotas réconciliés, aucun état vivant écrasé |
| P0 | Profils réels et secrets distincts, appairages et tunnels | Liaison clé/profil et isolation livrées ; aucun compte activé | Deux profils testés en refus croisé puis trois configurations privées validées |
| P0 | Qdrant/Ollama/SearXNG/NAS réels et corpus de recette | Raccordements livrés, modèles/digests et ressources à relever | Rappel/citations, erreur franche, quotas, passages sync et fichiers validés |
| P0 | Windows/WebView2, micro/caméra/haut-parleurs | Binaire G270 qualifié en CI ; UI G272 qualifiée séparément | Permissions, fermeture tardive, redémarrage et appareils réels testés |
| P0 | Endurance, limites de maintenance, latences et mémoire | Garde d’activité et seuils configurables prêts | Mesures réelles et seuils approuvés, rollback reproduit |
| P1 | Modèles voix/visage, calibration, retrait et conservation des gabarits | Enrôlement et comparaison au profil connecté livrés G272 ; poids réels non qualifiés | G15–G17, précision mesurée, aucune autorisation fondée sur la ressemblance |
| P1 | Reconnaissance de plusieurs personnes et changement explicite de session | Pas livré par la comparaison mono-profil ; contrat d’identité et politique à arrêter | Protocole d’authentification, révocation et anti-usurpation défini puis testé |
| P1 | Synchronisation automatique des bibliothèques PC/NAS | Import ponctuel livré ; service de surveillance/import absent | Racines, rythme, doublons, suppressions, versions, budgets et consentement définis ; reprise durable testée |
| P1 | Rétention coordonnée / nettoyage multi-magasins | Copie et conservation explicites disponibles ; suppression automatique absente | Politique par type de donnée, sauvegardes et preuves protégées ; aperçu vérifiable avant toute suppression |
| P1/P2 | Médias/GPU avancés, partage VRAM, longue vidéo et galerie | Contrats/adaptateurs/worker présents ; moteurs/poids réels et arbitrage ressources à qualifier ou compléter | Moteurs retenus, budgets mesurés et scénarios VM/PC reproductibles |
| P2 | Mobile, robotique, OS/DARME et autres extensions de la vision | Chantiers distincts, non nécessaires au premier périmètre bêta serveur/PC | Périmètre adopté et critères propres avant développement |

Les P1 d’automatisation, identité multipersonne et rétention contiennent encore du
**développement**, pas seulement des essais VM. Ils ne sont pas déclarés bloqués
techniquement par l’absence de VM : leurs politiques et leur périmètre doivent
être fixés avant d’introduire des effets automatiques. Le présent lot clôt les
parcours explicites préparables avec les contrats actuels, pas toute la vision
historique. La bêta de base peut garder l’identité biométrique désactivée.

## Éléments désormais développés hors VM

- G269 : runtime d’index, passages et mémorisation avec aperçu ; dossier et rollback.
- G270 : chat vers Memory, isolation des profils appairés, activité entre VM,
  maintenance, passages incrémentaux, SearXNG/HTTPS, fichiers et résident Windows.
- G271 : diagnostic de configuration et de fichiers privés sans démarrage.
- G272 : extraction PC/NAS PDF/Office/texte, provenance et reçus paginés ; analyse
  et mémorisation distinctes ; enrôlement volontaire et comparaison du profil
  connecté ; fermeture des capteurs et invalidation des réponses tardives ; copie
  arrêtée des états privés avec refus de réattribution des droits.

## Rapprochement de l’historique

G262 a été reçu via C188 et intégré G267 ; G264/G266 via C189/C190 et G268 ; C191 et
Memory 0067 via G269. Ces demandes ne sont plus « en attente de réception ».
Le dernier message Claude observé reste C191. Les dix contre-revues G270 restent
publiées ; leur existence ne prouve pas une exécution ou une nouvelle réponse.

G170-A/B/F : liaison par clé et tests d’isolation disponibles, activation humaine
et qualification matérielle ouvertes. G170-E : UI d’enrôlement optionnelle livrée,
prise réelle et trois profils non qualifiés. G170-C/D : moteurs raccordables et
comparaison propre profil disponibles ; reconnaissance multipersonne non livrée.
G184 demeure un registre préparé, sans migration automatique de comptes actifs.
G182 : journaux à récupérer avant reprise, aucune relance dans cette séance.

Le [rapport unique](../weekend/2026-10-17/RAPPORT-UNIQUE.md) contient les révisions
et les campagnes effectivement exécutées. Les 44 preuves PC/VM du dossier restent
NOT_RUN jusqu’à exécution et observation réelles.
