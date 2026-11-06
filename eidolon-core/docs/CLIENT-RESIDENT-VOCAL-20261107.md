# Client résident vocal — 7 novembre 2026

Statut : cadrage demandé par toytoy ; pas de nouvel installateur livré.
Bases lues : Core 4b4457b ; branche Cornelius/G296 62bf0fc et message C199.

## Parcours cible

- Assistant d'installation Windows, sans terminal ni copie manuelle de clé.
- Premier appairage graphique une fois ; identité par appareil conservée dans
  le coffre Windows/DPAPI, révocable côté serveur.
- Autorisation micro et choix du démarrage avec Windows mémorisés et révocables.
- Compagnon dans la zone de notification, indépendant de la fenêtre de dialogue.
- Mot unique « Eidolon », détecté localement ; réponse « Oui ? », puis session
  vocale Core/STT/LLM/TTS à la demande. Pas de démarrage d'un service système
  à chaque phrase : il s'agit d'activer la session de traitement.
- Fin ou inactivité : retour à la veille locale. Couper le micro libère le
  périphérique ; Quitter arrête aussi le compagnon. Caméra inutile au réveil.
- Reconnexion automatique avec attente progressive, sans renvoi d'une phrase
  déjà envoyée dont la réponse serait perdue.

## Architecture

PC : détection et modèles de réveil installés localement, microphone, lecture,
interface. X399 : API Core et traitement conversationnel. VM Memory : mémoire.
Aucun audio ambiant envoyé au serveur ou archivé en veille. Aucun GPU imposé
pour le réveil. Le mot d'appel ne vaut ni identification ni autorisation.
Le client ne dépend pas de la connexion OAuth du plugin GPT Collaboration.

Cible proposée : API HTTPS locale, appairage temporaire à usage unique validé
par l'administrateur, secret propre à chaque appareil et révocation individuelle.
La distribution de la confiance TLS reste à implémenter : aucune désactivation
possible des contrôles de certificat, aucune ouverture HTTP non protégée.
Transition possible : tunnel G286 automatique géré par le compagnon. Il retire
les manipulations quotidiennes, mais ne constitue pas une API HTTPS directe.

## Existant et limites constatées

G286 a déjà une API, un lanceur et un tunnel supervisé avec identité DPAPI.
Le résident PowerShell historique exige encore un tunnel disponible.
La veille actuellement déployée transcrit sur le serveur et accepte « Dis-moi » :
elle ne satisfait pas au réveil local unique demandé.
G296 contient un contrôleur duplex et des outils de mesure/entraînement, sans
intégration Windows terminée. Selon C199, la v2 manque de rappel et de validation
sur ambiance indépendante. Aucun modèle n'est donc déclaré qualifié ici.

## Lots et recette

1. Inventorier les modèles sauvegardés G296 ; reprendre les critères préenregistrés
   gate-v3.json et VALIDATION-V3.md, puis qualifier un candidat indépendant.
2. Compagnon : propriétaire unique du micro, réveil local, démarrage résident,
   reprise après veille/débranchement, sessions bornées et résultats tardifs rejetés.
3. Appairage graphique, connexion persistante et API HTTPS avec révocation.
4. Installateur, mise à jour, désinstallation et choix de démarrage automatique.
5. Recette Windows physique : réveil fenêtre fermée, micro coupé réellement,
   zéro audio réseau en veille, pas de double envoi après coupure, refus d'un
   serveur usurpé/appareil révoqué. Mesurer CPU/RAM/latence et faux réveils
   pendant télévision et synthèse. Duplex conditionné aux essais d'écho.

Travail effectué dans ce lot : lecture des sources et cadrage sur branche isolée.
Aucun binaire construit, aucune capture micro, aucun entraînement long ou
changement de production. Validation acoustique sur le PC encore nécessaire.
