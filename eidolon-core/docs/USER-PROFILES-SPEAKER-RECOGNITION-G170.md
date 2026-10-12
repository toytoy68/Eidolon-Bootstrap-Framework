# G170 — Profils utilisateur et reconnaissance du locuteur

Décision utilisateur : 12 octobre 2026, 11 h 49 Europe/Paris.
Base : 7e3245f3fe3daa07a56f7044de88042803c8aa41.
Statut : demandé, planifié ; implémentation et recette ouvertes.

## Trois profils prévus

Un administrateur et deux utilisateurs casual. Les noms et alias réels sont
dans un plan privé sur la VM, hors Git. Les fixtures publiques utiliseront des
noms fictifs. Aucun compte actif ni gabarit biométrique créé dans ce lot.
Casual signifie utilisateur standard sans gestion des comptes, secrets,
services, déploiements ou politique de sécurité. Les permissions des outils
restent contrôlées côté serveur. Aucun droit sudo implicite pour admin.

La reconnaissance du locuteur est distincte du STT Whisper et du TTS Piper.
Voix et visage doivent proposer le même profile_id stable, sans exiger les
deux capteurs. La détection de présence actuelle n'identifie personne.
Un texte tel que « je suis admin » ne prouve jamais une identité.

## Sessions, droits et mémoire

Séparer identité reconnue, profil confirmé, clé du terminal et permissions.
La biométrie sert à proposer un profil et personnaliser ; elle ne crée pas
une session authentifiée, ne change pas un rôle et ne déverrouille pas les
souvenirs privés à elle seule. Garder une connexion manuelle sans capteur et
une authentification explicite pour les actions sensibles.

Isoler conversations, souvenirs, préférences et caches par profil. Au
changement, annuler les réponses en vol, vider le contexte précédent et
empêcher une réponse tardive ou un TTS de divulguer son contenu. Un terminal
appairé partagé ne suffit pas à identifier la personne qui l'utilise.
Appliquer le périmètre mémoire côté serveur en lecture ET écriture ; aucun
profile_id provenant du navigateur ou du LLM ne constitue une autorisation.
Le lien familial ne crée pas de partage automatique. Admin n'obtient pas
implicitement les conversations privées des autres. Le corpus existant reste
non attribué tant que sa migration n'est pas définie explicitement.
Coordonner Memory Engine avant modification de son contrat. Ne pas déduire
de restrictions d'âge non demandées.

## Enregistrement et états

Enregistrement guidé local sur PC avec chaque personne présente et volontaire,
capture visible et arrêt disponible. Profil utilisable sans biométrie.
Photos, audio et gabarits hors Git et hors chat, stockage privé, effacement
et réenregistrement possibles. Pas de conservation indéfinie des prises brutes
par défaut. Enrôlement lié à un profil confirmé.

Sortie : proposition datée, modalité, score propre au moteur ; ce score n'est
pas une probabilité d'identité. États explicites : inconnu, ambigu, voix trop
courte, silence, plusieurs personnes, périmé et moteur indisponible. Seuils
à mesurer, pas de valeur arbitraire. Désaccord voix/visage : ambigu, sans
changement automatique de profil. Aucun souvenir privé pour un inconnu.
Choix des moteurs locuteur/visage encore ouvert : examiner sources officielles,
licences des poids/code, ressources et essais avant adoption. Aucun modèle
nouveau installé. Le LLM visuel ne suffit pas à prouver une identité.

## Lots et recette

- G170-A : stockage privé, schéma et import explicite du plan ; migration sur copie.
- G170-B : sessions, rôles et isolation mémoire/historique/cache.
- G170-C : moteur locuteur, enrôlement et états inconnu/ambigu/indisponible.
- G170-D : liaison voix/visage et fraîcheur, sans élévation de privilèges.
- G170-E : UI des profils, capture, effacement et réenregistrement.
- G170-F : tests synthétiques puis PC avec les personnes et capteurs réels.

Recette : faux positifs/rejets, bruit, distance, voix enregistrée diffusée,
TTS d'Eidolon, silence, paroles simultanées et contention STT/vision/dialogue.
Vérifier refus d'élévation casual vers admin par texte/voix/photo/profile_id,
isolation lors de réponses tardives, suppression effective des gabarits et
connexion manuelle sans capteurs. Les mocks ne qualifient pas les personnes.
Coordonner les modules partagés avec les travaux communication G164–G169.

## Livraison de préparation

Plan privé : profile-plans/household-profiles-v1.json sous eidolon-beta de
l'opérateur ; fichier 0600, dossier 0700. Schéma de plan
eidolon-user-profile-plan/1, statut PLANNED_NOT_ACTIVE ; aucun importeur
Runtime encore implémenté. Aucun jeton créé, permission changée ou service
redémarré. Ce document et les tâches ne lancent aucune session d'agent.

## Première brique G170-A — validateur livré le 12/10/2026

`profile_plan.validate_profile_plan()` valide strictement le plan préparatoire
et retourne des données immuables. Trois profils, un admin, deux casual ;
identifiants uniques, aliases normalisés sans collisions, aucun champ secret,
rôle inconnu ou activation accepté. Résumé de diagnostic sans identités.
12 tests synthétiques réussis et validation du fichier privé réel sans
affichage de ses noms. Aucune entrée/sortie dans ce module, aucune permission
Runtime accordée. Import transactionnel, sessions et isolation mémoire
restent à implémenter ; le plan privé est toujours PLANNED_NOT_ACTIVE.
