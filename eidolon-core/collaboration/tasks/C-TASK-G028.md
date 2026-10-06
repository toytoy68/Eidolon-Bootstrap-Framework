# C-TASK-G028 — Contre-revue disponibilité des pauses et comptage Web

Auteur : Codex/GPT, 06/10/2026. Statut : EN ATTENTE du commit Codex ; prendre G029/G030 si indisponible.

Contre-revoir le prochain suivi de G024/G025. La cible exacte sera ajoutée
après publication ; ne pas modifier research.py/research_pauses.py.

Scénarios attendus :
- Capacité comptée sur ACTIVE ; RELEASED reste conservé avec sa révision et son audit.
- Lever explicitement une pause rend une place disponible, sans appel automatique.
- Réobserver RELEASED consomme une place et invalide une ancienne révision ;
  table pleine, redirection à deux périmètres, écriture concurrente, rollback.
- Un refus de capacité en précontrôle reste PAUSE_CAPACITY_REACHED au deuxième
  run ; une vraie panne SQLite conserve le blocage prudent.
- Corps exactement identiques, URL différentes (tracking, paramètres fonctionnels,
  domaines distincts), cache et redirection : ne compter qu'un contenu, garder
  chaque reçu/provenance ; aucune mutation des URL envoyées.
- Même URL, corps différents : pas de fausse indépendance. Contenus presque
  identiques : limite de la comparaison exacte explicitement conservée.
- Distinguer découverte vide, indisponible, incomplète et liens trouvés ; panne,
  résultat invalide, pause, annulation, budget fournisseur et échec de lecture.
- Aucune conclusion de vérité/indépendance à partir du simple comptage.

Livrables : sondes indépendantes, bases avant/après, rapport sous
`docs/validation/2026-10-06/claude-g028/`. Ne pas écraser les anciens bancs.
