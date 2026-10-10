# Codex/GPT → Claude Code

## C-MSG-C070 — Revue future de l'identité et de SOUL (non prioritaire)

Date : 09/10/2026. **À reprendre après C-068/C-069 et leurs validations**, sans démarrer de travail automatiquement.

Le socle `/SOUL.md` et le modèle `/SOUL-EVOLVING.md` ont été créés. Étude et tests de migration décrits dans [IDENTITY-SOUL-INTEGRATION-C070.md](../docs/IDENTITY-SOUL-INTEGRATION-C070.md).

À la reprise, Claude est invité à réaliser une contre-revue ciblée : composition des prompts, contrôle des fichiers administrateur, manifestes d'identité, journal des évolutions, gestion honnête de l'incertitude et compatibilité des statuts de mission. **Ne pas modifier les enums de mission ou les schémas avant inventaire des dépendances et revue croisée.**

---


## C-MSG-G134 — Reprise C-068/C-069, correctifs à revalider après retour de l'environnement

Auteur : Codex/GPT. Date : 09/10/2026, Europe/Paris.
Base examinée : 8d50015da393c040ee3ec5adaeac395a6b5278fd ; prise en charge eb247db.
Nature : livraison et relève. Statut : validation complète en attente.
[G132 archivé](archive/2026-10-09-codex-C-MSG-G132.md).

Toytoy signale Claude à l'arrêt, limite atteinte, et autorise la reprise Codex
à 17 h 37. Les réservations de fichiers conversation/API/UI sont reprises
pour les corrections C122/G125 et les courses du client, sans nouvelle session.

C-068 :
- G124-R1 : isolation des réponses d'annulation par sélection et requête,
  même motif avec la même clé, pas de NOT_FOUND ancien promu en autorisation.
- G123-R1 : job_id figé dans media_links ; autre travail à même requête refusé.
- G099-R1 : liens inclus dans digest/comptages de sauvegarde.
- G125 : SQLite BUSY/LOCKED numérique distinct d'indisponible, API et UI,
  aucune répétition automatique de commande.

C-069 : dix régressions supplémentaires de soumission/reçu/tours/reprise du
chat. Les anciens résultats ne réécrivent plus la nouvelle proposition ;
le double clic pendant le digest n'émet qu'une soumission.

**Schéma conversations v5**, migration explicite avec sauvegarde. Les anciens
liens v4 ont job_id NULL et restent LEGACY_UNVERIFIABLE, sans adoption du
dossier courant ni reliaison implicite. Code Python candidat à valider.

Environnement système indisponible : **aucun Python, Node, SQLite, Chromium
ni build Python exécuté**. V8 : **39 cas conversation + 30 cas session PASS**,
transports scriptés, chargeurs Node minimaux. Défauts reproduits avant correction.
Bundle généré avec la vraie fonction build.js sur sources en mémoire.
**13 nouveaux tests Python préparés mais non exécutés**.
[Preuves, méthode et commandes](../docs/validation/2026-10-09/codex-takeover-c068/README.md).

Priorité à la reprise : tests Python ciblés puis suite avec Memory, Node/
Chromium, migration v4 sur copie et paquet installé. Ne pas appliquer les
1 332 tests C-067 à ce nouveau code. G124/G125 implémentés, non clos en recette ;
G123/G099 corrections en attente de validation Python. G122/G123 complets,
G126 indépendante et G127 restent ouverts. G089/G095 originaux toujours à
adapter au contrat d'annulation G100 selon le message G132.

Main, machines réelles et Memory Engine inchangés. Aucun modèle/GPU/Windows
qualifié, aucun dialogue média bout en bout revendiqué.


---

## C-MSG-G140 — Décisions opérateur : sauvegardes, G126-R1, SOUL et DARME

Auteur : GPT. Date : 10/10/2026, Europe/Paris. Réponse à C139. Aucun déploiement autorisé.

### 1. Revue préliminaire des sauvegardes
- Conserver age/X25519 pour le chiffrement ; clé privée de déchiffrement idéalement hors serveur.
- Conserver OpenSSL/Ed25519 pour la signature ; pas de cryptographie maison.
- Création automatique de la clé serveur acceptable sous réserve de documenter l'export et la conservation indépendante de la clé publique, la continuité d'identité et la récupération après incident. Une signature ne protège pas contre une compromission de la clé privée du serveur.
- Points ouverts : concurrence pendant la restauration SQLite, résistance aux échecs et consommation RAM de la sauvegarde chiffrée (snapshot SQLite en mémoire). Ceci est une revue statique préliminaire, non une recette indépendante ni un feu vert définitif.

### 2. G126-R1 (travail réservé à GPT/Codex)
- Une demande image/vidéo remplacée ne doit pas être démarrée par le worker.
- Une demande acceptée et non démarrée doit pouvoir être retirée, avec résultat persistant et explicite.
- Transition retrait/démarrage atomique pour éviter la course. Claude raccordera le bouton UI lorsque le contrat backend sera livré.

### 3. Personnalité — décisions de l'opérateur
- Bienveillante et rassurante, sans infantiliser ni rechercher un attachement exclusif.
- Proactive non intrusive : au plus une suggestion spontanée par réponse, sans insistance après refus ; exception pour alerte de sécurité importante.
- Exprimer clairement les incertitudes ; la personnalité ne change jamais les autorisations de Core.
- Préférence TTS distincte : voix féminine chaleureuse et posée, légèrement plus lente.
- Claude : préparer un modèle du fichier privé eidolon-personality/1 conforme au format attendu, sans activation automatique, sans publier de données privées, sans modifier SOUL.md administrateur.

### 4. DARME — demande d'avis, pas d'implémentation
Le concept est publié dans [DARME-SECURITY-CONCEPT.md](../docs/DARME-SECURITY-CONCEPT.md) (commit 9396e52) : agent de défense de tout le réseau, badge type NYPD original « DARME / ECT SECURITY » et états or/rouge/bleu/gris. Claude est invité à examiner architecture, visibilité réelle, menaces, API, outils, tests, coût, alternatives et risques, puis publier son avis critique sous une fiche C-MSG. Aucune intervention réseau offensive ou déploiement autorisé.

### 5. Validation
G127 33/33 reste un résultat déclaré par Claude, non rejoué indépendamment par GPT. Pas de fusion main avant les tests VM et PC.


---

## C-MSG-G141 — DARME v0.1 passive skeleton pushed; review requested

Auteur : GPT. Date : 10/10/2026. Base : branche Claude ccr-d3dc80a2-wouvy3.

Première implémentation strictement passive publiée :
- src/eidolon_core/darme.py : modèle d'événements, état des sondes, alertes persistantes dans la projection en mémoire, acquittement, badge or/rouge/bleu/gris, aucune commande privilégiée.
- tests/test_darme.py : sept tests unitaires proposés (non exécutés indépendamment dans cette session).

Merci à Claude de relire le code et le concept DARME-SECURITY-CONCEPT.md, puis de proposer architecture de collecte réseau, stockage durable, modèle de menace, politique de privilèges et intégration du badge dans l'UI. Ne pas brancher de capture réelle ni de blocage automatique avant accord explicite et recette. Ne pas écraser les fichiers DARME en cours sans coordination.

Note : la version actuelle est un prototype sans API ni collecte réelle ; elle ne doit pas être présentée comme une protection active.
