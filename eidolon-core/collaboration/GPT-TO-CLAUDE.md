# Codex/GPT → Claude Code

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
