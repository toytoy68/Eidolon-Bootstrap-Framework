# Dashboard et contexte d'activité — propositions Codex

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Statut : **PROPOSÉ — à comparer aux études Claude G076/G077, choix toytoy ouvert**.
Base technique relue : 6f46219, client connecté, projection `client_sync`, catalogue
d'archives et propositions d'outillage C-BRAIN-G012. Ce document ne déploie rien.

## Direction d'ensemble

Conserver l'inspiration Jarvis et le wallpaper Eidolon : fond sombre, accents
bleus, panneaux lisibles, animation discrète. Le E bleu reste l'icône de
l'application Windows. Pour l'interface principale, je propose une présence
visuelle plus petite que le contenu, réglable et compatible avec mouvement réduit.
Le but est de voir rapidement ce qu'Eidolon fait, ce qui attend toytoy et où
se trouvent les preuves ; aucune jauge décorative ne doit ressembler à une mesure.

Deux compositions à comparer :

| Option | Point fort | Limite | Essai utile |
| --- | --- | --- | --- |
| Conversation centrale, missions à droite | Naturelle pour l'assistant quotidien et la voix future | Un chat long peut cacher un blocage important | Retrouver une mission bloquée depuis une conversation de 30 échanges |
| Missions centrales, conversation en panneau | Très claire pour superviser plusieurs travaux | Moins accueillante pour une question rapide | Poser une question puis suivre trois tâches sans changer plusieurs fois de vue |

Préférence Codex : conversation centrale en usage courant, vue Missions dédiée
pour la supervision ; partager les mêmes données et composants d'état entre ces
vues. Pour la bêta actuelle de consultation, garder Missions fonctionnelle au
premier plan : le chat généraliste n'est pas encore branché. Une maquette peut
montrer la cible future en la nommant comme telle. G076 doit challenger cette
préférence ; aucune refonte de l'interface de Claude n'est faite ici.

## P9 — Une page d'accueil qui répond à trois questions

Proposition : afficher « Ce qui est en cours », « Ce qui attend ton attention »
et « Derniers résultats ». Chaque carte ouvre la mission correspondante et garde
son état daté. Le compteur d'attention distingue décision attendue, information
manquante et effet à vérifier ; un bouton d'accord ne doit pas apparaître pour
un modèle indisponible. La simple présence d'une mission RUNNING dans une vieille
capture ne suffit pas à afficher une animation d'exécution vivante.

Dans la fenêtre compacte, ne montrer qu'une mission sélectionnée, un compteur
d'attention et la connexion. Les détails sont accessibles à la demande. En mode
lecture seule actuel, les libellés restent des consultations, pas des commandes.

## P10 — Carte de reprise expliquée

Exemple futur : « Tu travaillais sur la recette V100. Dernier résultat conservé :
configuration conforme. Étape proposée : lancer les quatre cas de recette. »

La carte doit montrer séparément : dernier fait observé, date, mission liée,
raison de la suggestion et action proposée. Fermer l'application ou détecter la
présence ne lance pas l'étape suivante. Si la mission a un effet inconnu, proposer
la consultation des preuves, pas le bouton Réessayer. Si elle est déjà terminée
ailleurs, rafraîchir puis supprimer la suggestion.

Premier essai proposé : déclaration manuelle « reprendre ce projet » avec lien
vers une mission. Cela teste l'utilité de la carte avant d'installer un collecteur
d'activité. Le contexte automatique pourra ensuite alimenter la même carte.

## P11 — Contexte d'activité progressif, collecté sur le poste

| Niveau proposé | Contenu | Utilité | Compromis |
| --- | --- | --- | --- |
| Manuel | Projet actif choisi, mission, note courte | Simple, explicite, utile tout de suite | Demande une action de l'utilisateur |
| Métadonnées locales | Application au premier plan, début/fin, projet associé ; domaine d'onglet si module autorisé | Suggestions de reprise et regroupement d'activité | Classification imparfaite ; noms/titres peuvent déjà révéler des informations |
| Contenu enrichi ciblé | Texte/document choisi explicitement pour une tâche | Meilleure compréhension d'un travail précis | Collecte plus sensible, volumes et droits supplémentaires |

Préférence Codex : commencer par manuel, puis métadonnées minimales opt-in,
avec bascule visible et arrêt immédiat. Éviter le polling de captures d'écran
comme mécanisme initial. Des événements au changement d'activité et à la veille
suffisent pour éprouver le besoin. La capture du contenu n'est pas nécessaire
pour prouver qu'une application était active.

Proposition d'événement minimal : version, identifiant, poste, session locale,
instant observé, type d'activité, application, projet choisi ou suggéré, expiration,
origine et confiance de l'association. Ne pas confondre horloge du poste et heure
de réception serveur ; traiter doublons, retard et changement de session.
Le titre complet et l'URL avec paramètres ne sont pas nécessaires au premier lot.
Une observation de fenêtre n'est ni une identité utilisateur authentifiée,
ni une instruction, ni une preuve que la personne lit effectivement le contenu.

Rétention à comparer, non adoptée : petit journal local roulant de 24 heures,
effaçable, puis conservation durable seulement des résumés utiles explicitement
retenus selon la politique mémoire. Variante : session uniquement, sans stockage
au redémarrage, plus discrète mais moins utile après reboot. Tester les deux sur
une journée synthétique avant de fixer durées, limites d'événements et volume.
Le poste partagé et le mode privé doivent interrompre/filtrer la collecte ; un
événement reçu après désactivation ne réactive jamais celle-ci.

Core utilise le contexte pour une suggestion. Memory Engine reste la source
canonique de la mémoire durable ; ne pas y déverser un flux brut d'applications,
ni écrire directement dans ses fichiers depuis le connecteur Windows. Le contrat
d'ingestion d'un éventuel résumé devra être vérifié avec le moteur avant codage.

## P12 — Panneau d'outils utile par mission

Prolongement de [C-BRAIN-G012](2026-10-08-agent-toolbox.md), sans nouvel outil adopté.
Pour chaque outil : où il s'exécute, s'il est disponible, ce que cette mission
peut en faire et le dernier résultat. Le bouton « détails » donne sources,
durée, erreurs et limites. Une installation d'outil ne vaut pas autorisation.
Éviter une liste de cinquante outils dans chaque prompt ; montrer le sous-ensemble
nécessaire à la mission et garder le registre comme contrat commun.

Premier parcours proposé : retrouver une source mémoire → relire son document
ou message complet → calculer sur les données nécessaires → produire un rapport
avec références. Il donne un usage concret aux trois profils proposés
(documentaliste, analyste, diagnostic) sans imposer plusieurs agents concurrents.
Un agent séquentiel et deux outils bien qualifiés peuvent démontrer ce parcours.

Point mémoire déjà reproduit : un extrait exact peut perdre la négation située
à sa gauche ; deux versions d'une conversation peuvent répéter le même message.
La carte Source devrait signaler extrait/réserve/version, offrir le retour au
message complet quand un contrat de lecture fiable existe, et ne pas afficher deux
occurrences comme deux confirmations indépendantes. En attendant, la limite doit
rester visible dans le rapport. Aucun correctif du Memory Engine n'est inclus ici.

## Ce que le serveur sait déjà exposer

| Élément d'interface | Donnée actuelle vérifiée dans le code | Travail restant |
| --- | --- | --- |
| Mission et progression | id, status, phase, progress.completed/total, objective_kind, outcome_status | Composition visuelle et essai utilisateur ; total peut être inconnu |
| Dernier état reçu / historique | Capture client-sync, événements datés et curseur | Conserver l'indication de fraîcheur en toute vue |
| Demande d'annulation | cancel_requested | Commande distante et identité réelle encore hors client de consultation |
| Décision et effet | action_view, reçu historique et receipt_binding | Parcours d'action réel distinct ; accord et effet ne se confondent pas |
| Archives de recherche | Projection authentifiée C-030, métadonnées bornées | Raccordement client G066 en file Claude |
| Chat libre et réponse détaillée sourcée | Pas dans la projection de consultation | Contrat et API dédiés ; ne pas élargir la projection par copie du contexte brut |
| Outils/agents disponibles | Registre Python existant, pas d'API de catalogue général | Proposition C-BRAIN-G012 et définition des droits |
| GPU, VRAM, température | Pas de télémétrie live fournie par cette API | Collecteur, origine, horodatage et état périmé à qualifier |
| Activité PC, présence, micro/caméra | Pas de collecte branchée | Connecteur local, activation choisie, état matériel observé et vie privée |

## Ordre recommandé et critères de décision

1. **Avant la recette bêta** : garder visibles fraîcheur, missions bloquées et
   résultats vérifiés ; terminer G066 ; préparer la recette modèle reproductible.
2. **Prochaine tranche proposée** : carte de reprise manuelle et premier parcours
   documentaire avec sources complètes, après choix des contrats nécessaires.
3. **Ensuite** : contexte d'activité minimal et télémétrie système ; enfin voix,
   présence et appareils selon le besoin réel et les tests du connecteur.

Essais discriminants : lien coupé avec une mission affichée RUNNING ; deux sources
de même message ; changement de fenêtre sans changement de projet ; veille puis
reconnexion à un autre Store ; source hostile demandant un outil ; arrêt de la
collecte alors que des événements sont en transit. Réussite : aucun état inventé,
aucune reprise/collecte réactivée par le seul contexte, et la personne retrouve en
quelques actions la preuve et la prochaine étape. Mesurer les usages ; aucun gain
de productivité ni consommation n'est chiffré avant essai.

Avis Claude à recevoir dans ses propres fichiers. La boîte à outils conserve ses
colonnes Claude/choix ouvertes ; cette note n'anticipe pas l'arbitrage de toytoy.
