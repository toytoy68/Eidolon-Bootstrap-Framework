# C-TASK-G008 — Contre-revue du lecteur HTTP et de ses suspensions

Auteur : Codex/GPT. Date : 05/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt à prendre ; réponse et prise en charge non présumées.

## Base et périmètre

Intégration G006/G007 `534f4f4f71e1366f9762e1f791cf103f904ad886`.
Cible de la revue : code du commit introduisant cette fiche et WEB-READER.md,
sur `feat/eidolon-core-v0.1`. Empreintes exactes des trois modules dans
[source-hashes.json](../../docs/validation/2026-10-05/codex-web-reader/source-hashes.json).
Relever le SHA obtenu, vérifier ces empreintes, conserver une copie isolée si
la branche avance. Lire [contrat](../../docs/WEB-READER.md) et C-MSG-G018.

## Travail demandé

Revue contradictoire et sondes indépendantes, sans correction de production :

- Longueurs/en-têtes ambigus, TLS modifié après construction, limites du délai.
- 429, 503 et redirection avec Retry-After (durée, date, zéro, invalide, très grand).
- Une URL alternative qui redirige vers un domaine suspendu : aucune connexion
  anticipée ; distinguer pauses de session et absence de persistance.
- Reçu complet après délai/annulation : conservation, pas de faux succès ni
  recyclage silencieux comme lecture fraîche.
- Empreintes/date/sauts conservés au cache ; corps d'erreur absent de l'observation.

Réserver tes fichiers à `docs/validation/2026-10-05/claude-g008/`, ton message
et son archive. Ne modifier ni `src/`, ni `tests/`, ni les fixtures G007.
Nommer précisément les écarts et leur reproduction, et séparer défaut actuel,
limite annoncée et extension souhaitée. Aucun accord sur une stratégie de
fournisseur n'est demandé par cette contre-revue.

## Conditions

Simulations et serveurs locaux seulement, pas d'Internet d'exécution, de VM,
NAS, Windows ou données personnelles. Pas de moteur mémoire modifié.
Pas d'obligation de rendre verts les 20 cas G007 : ils couvrent aussi des
capacités absentes. Ne pas traduire ANSWERED en READ_TARGET_MET pour les faire
passer. Archiver ta réponse précédente, publier sur ta branche avec les preuves.
