# C-TASK-G012 — Consommateur du protocole de reconnexion dans le prototype

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt après G013 ; G009 reçu dans 111da40 pendant ce lot.
Prendre connaissance de G023 et ne pas recréer une interface parallèle.

## Base concrète

[Contrat C-008a](../../docs/CLIENT-SYNC.md), version eidolon-client-sync/1.
La cible est le commit introduisant cette fiche, base antérieure e25cd2a.
[Empreintes](../../docs/validation/2026-10-06/codex-client-sync/source-hashes.json),
[trace réelle sur données synthétiques](../../docs/validation/2026-10-06/codex-client-sync/demo.json).
Relever ton SHA et garder une copie si la branche avance. La trace contient des
UUID/heures d'un essai ; ni agent ni équipement réel n'est identifié par ces champs.

## Livrable demandé

Un consommateur JavaScript pur (par exemple sync-state.js) dans desktop/prototype/,
avec tests Node sans dépendance distante, puis branchement sur les scénarios du
prototype autonome G009. Il reçoit des enveloppes JSON locales ; aucun fetch
vers Core, aucune authentification feinte ni commande réelle. Le paquet Python
reste serveur POSIX : ne pas l'importer dans le futur client Windows.

Conserver séparément état affiché, curseur d'événements, références déjà reçues
et connectivité locale. Une capture plus récente remplace la vue de mission ;
les événements servent d'historique, pas à modifier la capture. Une réponse
répétée ou tardive ne crée ni mission, ni action, ni notification supplémentaire.
Une réponse à une ancienne requête ne fait pas reculer le curseur actif. Les séquences de mission peuvent sauter à cause d'autres
missions : pas de test de contiguïté +1 comme dans le serveur simulé G009.
Séquences/révisions limitées aux entiers exacts JS (Number.isSafeInteger).
Accepter action_view=null : une mission text.stats n'a pas de proposition.
Les noms MISSION_RUNNING/EFFECT_VERIFIED sont internes à G009 ; ne pas les
inventer à partir des références d'événements de client-sync/1.

Scénarios et assertions indépendantes :

1. Reconnexion après progression : pages récupérées sans dépasser la taille
   annoncée, doublons dédupliqués par store_id/mission_id/sequence.
2. Capture en avance sur la page (as_of_sequence > cursor.sequence) : ne pas
   sauter les pages restantes ; ne pas rejouer le passé sur l'état courant.
3. Réponses reçues hors ordre : la plus ancienne ne remplace pas la vue récente.
4. Annulation demandée à révision inchangée : visible grâce à as_of_sequence,
   mais pas affichée comme CANCELLED avant capture correspondante.
5. RESET_REQUIRED : expliquer historique/base changé ; rechargement explicite,
   aucune relance de mission ni accord implicite. Curseur de mauvaise mission
   ou version inconnue rejeté, aucune capture prétendument réussie.
6. Déconnexion : dernier état connu daté, aucune affirmation que Core continue
   réellement, pas de file d'actions envoyée automatiquement au retour.
7. PENDING/APPROVED/USED, effet UNKNOWN et revue : garder les axes séparés.
   Le présent protocole ne fournit pas les paramètres d'approbation et n'autorise
   jamais l'exécution ; tout bouton sensible reste simulé/inactif selon scénario.
8. Texte et métadonnées rendus comme données, jamais interpolés comme HTML
   exécutable ni interprétés comme instructions ; préférer textContent.

Ne pas déduire santé serveur/micro/caméra depuis observed_at. Silence et
fermeture restent sans décision. Préciser la politique de rétention des
références d'événements dans le prototype ; éviter une liste RAM infinie.
Émettre des fixtures avec les cas manquants et les étiqueter comme dérivées,
jamais comme des sorties Core réellement observées. Garder la fixture originale.

## Preuves et frontières

Documentation de lancement/états dans le prototype, tests avec résultats dans
`docs/validation/2026-10-06/claude-g012/`. Si captures ou essais navigateur
possibles, préciser environnement et actions vérifiées ; sinon le signaler.
Node qui valide un reducer ne qualifie pas un rendu Windows, tray ou notification.
Commit séparé et réponse signée/archivée selon le protocole.

Ne pas modifier src/, tests/ Python, contrats ou preuves Codex, ni maquettes
archivées. Signaler un défaut du contrat avec une sonde distincte, sans changer
les états pour rendre l'interface artificiellement verte. Aucun déploiement,
VM/NAS/Windows réel, GPU, réseau externe ou donnée personnelle.
