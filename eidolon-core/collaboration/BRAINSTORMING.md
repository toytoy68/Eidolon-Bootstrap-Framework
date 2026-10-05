# Brainstorming — Eidolon Core

Contributions initiales : Codex/GPT, 05/10/2026, Europe/Paris,
base `62da8f8d0146b4d60ae891c31238af88803296aa`.
Ces pistes sont **des propositions**, pas des décisions attribuées à toytoy ou
à Claude. Le [cadrage utilisateur](../docs/CADRAGE-DECISIONS-2026-10-05.md) et la
[TODO](../TODO.md) restent les références de périmètre et de travail.

## C-BRAIN-001 — Réussir la mission, pas seulement le plan

Statut : PROPOSÉ. Auteur : Codex/GPT. Lien : C-001, C-REV-001.

Besoin : détecter un plan techniquement valide qui ne répond pas à la demande.
Option A : catalogue restreint de types de mission avec critères déterministes
(sources requises, cible, état attendu, artefact). Option B : critères libres
proposés par le modèle puis approuvés. A est plus facile à vérifier mais plus
limité ; B couvre davantage de demandes, avec un risque d'objectif mal défini.

Proposition GPT : commencer par A pour les scénarios A–D, prévoir une sortie
« clarification nécessaire » pour le hors-catalogue. Essai discriminant : un
plan `text.stats` valide doit échouer au critère d'une mission « vérifier un
service », même si ses statistiques sont correctes.

Contribution Claude : non reçue. Décision : ouverte.

## C-BRAIN-002 — Connecteurs réseau et fichiers Windows

Statut : PROPOSÉ. Auteur : Codex/GPT. Liens : C-002, C-003, C-003W.

Besoin : accès Internet, Memory Engine, NAS et fichiers du PC depuis Core serveur.
Option A : capacités nommées derrière un catalogue de cibles et un connecteur
Windows local ; transport choisi par service. Option B : outil HTTP/SSH générique
avec règles de filtrage détaillées. A explicite mieux les permissions et les
preuves métier ; B facilite les premières intégrations mais expose plus de
paramètres dangereux et complique la vérification.

Proposition GPT : contrat de capacités commun avec adaptateurs spécifiques,
en séparant Web public, LAN et fichiers. Le protocole Windows reste ouvert.
Comparer lecture directe d'un partage et connecteur dans la session selon
authentification, droits effectifs, fichiers à la demande, performances et
gestion du PC hors ligne. Essai : même mission de lecture sur ressource NAS
et Windows simulée, refus hors périmètre, source/version conservées.

Contribution Claude : non reçue. Décision : ouverte.

## C-BRAIN-003 — Approbations et reprise d'un échec partiel

Statut : PROPOSÉ. Auteur : Codex/GPT. Liens : C-005, C-006.

Besoin : approuver une action concrète et reprendre Y sans rejouer X. Le runtime
actuel conserve les preuves mais considère FAILED terminal. Option A : nouveau
parcours de tentative lié à la même mission, avec validation des étapes acquises.
Option B : mission successeur référençant explicitement les résultats précédents.
A est plus naturel côté utilisateur ; B conserve simplement l'immuabilité du
résultat terminal, mais complexifie la lecture du suivi.

La proposition reste en attente sans expiration automatique ; une autorisation
technique devenue périmée ou inapplicable exige une nouvelle décision, pas une
suppression de la proposition. Un appel dont l'effet est inconnu ne redevient
jamais « à refaire » par une simple approbation générale.

Essai discriminant : X vérifié, Y interrompu après envoi ; revue puis reprise
de Y seulement. Un changement de cible ou de paramètres invalide l'autorisation
antérieure. Comparer traces et ergonomie des deux options avant choix.

Contribution Claude : non reçue. Décision : ouverte.
